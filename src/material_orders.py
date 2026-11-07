import datetime
import json
import os
import re
import sqlite3
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from src.config_loader import CONFIG
from src.project_paths import get_app_directory

import pymupdf
from PIL import Image, ImageDraw


def _app_data_dir():
    if sys.platform == "win32":
        base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base_dir = os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base_dir, "LeprendiX")
    os.makedirs(path, exist_ok=True)
    return path


def _settings_path():
    return os.path.join(_app_data_dir(), "dgkp_settings.json")


def _load_dgkp_settings():
    path = _settings_path()
    if not os.path.isfile(path):
        return {"phone": "", "signature": ""}
    try:
        with open(path, "r", encoding="utf-8") as settings_file:
            data = json.load(settings_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"DGKP-Einstellungen konnten nicht gelesen werden: {error}") from error
    return {
        "phone": str(data.get("phone") or ""),
        "signature": str(data.get("signature") or ""),
    }


def _save_dgkp_settings(phone, signature):
    settings = {"phone": phone.strip(), "signature": signature}
    path = _settings_path()
    temporary_path = f"{path}.tmp"
    with open(temporary_path, "w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, ensure_ascii=False, indent=2)
    os.replace(temporary_path, path)


def validate_material_order_template(template_path):
    template_path = os.path.abspath(template_path)
    if not template_path.lower().endswith(".pdf") or not os.path.isfile(template_path):
        raise ValueError("Bitte wählen Sie eine vorhandene PDF-Datei aus.")
    try:
        document = pymupdf.open(template_path)
        page_count = document.page_count
        document.close()
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(f"Die PDF-Druckvorlage konnte nicht gelesen werden: {error}") from error
    if page_count < 1:
        raise ValueError("Die PDF-Druckvorlage enthält keine Seiten.")
    return template_path


def _find_template():
    template_path = CONFIG.get("MATERIAL_ORDER_TEMPLATE", "")
    if not template_path:
        raise FileNotFoundError(
            "Materialbestellungen sind gesperrt. Bitte wählen Sie im Setup "
            "oder in der Patientenakte eine Druckformular-PDF aus."
        )
    if not os.path.isabs(template_path):
        template_path = os.path.join(get_app_directory(), template_path)
    if not os.path.isfile(template_path):
        raise FileNotFoundError(
            "Die konfigurierte Druckformular-PDF wurde nicht gefunden. "
            "Bitte wählen Sie eine neue Datei aus."
        )
    return validate_material_order_template(template_path)


def ensure_material_orders_table(database_path):
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                prescription_date TEXT NOT NULL,
                insurance TEXT NOT NULL,
                insurance_other TEXT NOT NULL DEFAULT '',
                patient_vsnr TEXT NOT NULL DEFAULT '',
                patient_first_name TEXT NOT NULL,
                patient_last_name TEXT NOT NULL,
                patient_postal_code TEXT NOT NULL DEFAULT '',
                patient_city TEXT NOT NULL DEFAULT '',
                patient_street TEXT NOT NULL DEFAULT '',
                insured_vsnr TEXT NOT NULL DEFAULT '',
                insured_first_name TEXT NOT NULL DEFAULT '',
                insured_last_name TEXT NOT NULL DEFAULT '',
                cost_exempt INTEGER NOT NULL DEFAULT 0,
                prescription_fee_exempt INTEGER NOT NULL DEFAULT 0,
                diagnosis TEXT NOT NULL DEFAULT '',
                products TEXT NOT NULL,
                follow_up INTEGER NOT NULL DEFAULT 0,
                dgkp_phone TEXT NOT NULL DEFAULT '',
                template_page INTEGER NOT NULL,
                form_number TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patienten(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_material_orders_patient_created "
            "ON material_orders(patient_id, created_at DESC, id DESC)"
        )


def get_patient_material_orders(database_path, patient_id):
    ensure_material_orders_table(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, created_at, prescription_date, products, template_page,
                       form_number, pdf_path
                FROM material_orders
                WHERE patient_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (patient_id,),
            ).fetchall()
        ]


def open_material_order_pdf(pdf_path, parent):
    if not pdf_path or not os.path.isfile(pdf_path):
        messagebox.showerror(
            "Materialbestellung",
            "Die gespeicherte Verordnung wurde nicht gefunden.",
            parent=parent,
        )
        return
    try:
        if sys.platform == "win32":
            os.startfile(pdf_path)
        elif sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", pdf_path])
        else:
            import subprocess

            subprocess.Popen(["xdg-open", pdf_path])
    except OSError as error:
        messagebox.showerror(
            "Materialbestellung",
            f"Die Verordnung konnte nicht geöffnet werden:\n{error}",
            parent=parent,
        )


class DgkpSettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("DGKP-Stammdaten")
        self.geometry("620x520")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")
        self.transient(parent)
        self.grab_set()
        self.signature_path = ""
        self._strokes = []
        self._current_stroke = []

        try:
            settings = _load_dgkp_settings()
        except RuntimeError as error:
            messagebox.showerror("DGKP-Stammdaten", str(error), parent=self)
            settings = {"phone": "", "signature": ""}

        self.phone_var = tk.StringVar(value=settings["phone"])
        self.signature_path = settings["signature"]

        content = tk.Frame(self, bg="#f0f0f0", padx=18, pady=14)
        content.pack(fill="both", expand=True)
        tk.Label(
            content,
            text="DGKP-Stammdaten",
            font=("Segoe UI", 17, "bold"),
            fg="#000000",
            bg="#f0f0f0",
        ).pack(anchor="w", pady=(0, 12))
        tk.Label(
            content,
            text="SV-ID und Name sind auf der ÖGK-Vorlage bereits fix eingedruckt.",
            font=("Segoe UI", 11),
            fg="#000000",
            bg="#f0f0f0",
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))
        tk.Label(
            content,
            text="Telefon-/Handy-Nr.",
            font=("Segoe UI", 11, "bold"),
            fg="#000000",
            bg="#f0f0f0",
        ).pack(anchor="w")
        ttk.Entry(
            content,
            textvariable=self.phone_var,
            style="Material.TEntry",
        ).pack(fill="x", ipady=4, pady=(4, 14))
        tk.Label(
            content,
            text="Unterschrift (mit Maus oder Touchpad zeichnen)",
            font=("Segoe UI", 11, "bold"),
            fg="#000000",
            bg="#f0f0f0",
        ).pack(anchor="w")
        self.signature_canvas = tk.Canvas(
            content,
            width=570,
            height=190,
            bg="white",
            highlightthickness=1,
            highlightbackground="#555555",
        )
        self.signature_canvas.pack(fill="x", pady=(5, 6))
        self.signature_canvas.bind("<Button-1>", self._begin_stroke)
        self.signature_canvas.bind("<B1-Motion>", self._draw_stroke)

        if self.signature_path and os.path.isfile(self.signature_path):
            tk.Label(
                content,
                text="Eine gespeicherte Unterschrift ist vorhanden. Zeichnen Sie neu, um sie zu ersetzen.",
                font=("Segoe UI", 10),
                fg="#000000",
                bg="#f0f0f0",
            ).pack(anchor="w")

        button_frame = tk.Frame(content, bg="#f0f0f0")
        button_frame.pack(fill="x", pady=(12, 0))
        ttk.Button(button_frame, text="Leeren", command=self._clear_canvas).pack(side="left")
        ttk.Button(button_frame, text="Abbrechen", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(button_frame, text="Speichern", command=self._save).pack(side="right")

    def _begin_stroke(self, event):
        self._current_stroke = [(event.x, event.y)]
        self._strokes.append(self._current_stroke)

    def _draw_stroke(self, event):
        if not self._current_stroke:
            self._begin_stroke(event)
            return
        previous = self._current_stroke[-1]
        current = (event.x, event.y)
        self.signature_canvas.create_line(
            previous[0],
            previous[1],
            current[0],
            current[1],
            fill="#111111",
            width=3,
            capstyle=tk.ROUND,
            smooth=True,
        )
        self._current_stroke.append(current)

    def _clear_canvas(self):
        self.signature_canvas.delete("all")
        self._strokes.clear()
        self._current_stroke.clear()
        self.signature_path = ""

    def _save(self):
        try:
            if self._strokes:
                image = Image.new("RGBA", (1140, 380), (255, 255, 255, 0))
                draw = ImageDraw.Draw(image)
                for stroke in self._strokes:
                    scaled_points = [(x * 2, y * 2) for x, y in stroke]
                    if len(scaled_points) == 1:
                        x, y = scaled_points[0]
                        draw.ellipse(
                            (x - 3, y - 3, x + 3, y + 3),
                            fill=(15, 15, 15, 255),
                        )
                    else:
                        draw.line(
                            scaled_points,
                            fill=(15, 15, 15, 255),
                            width=6,
                            joint="curve",
                        )
                self.signature_path = os.path.join(
                    _app_data_dir(),
                    "dgkp_signature.png",
                )
                bounds = image.getbbox()
                if bounds:
                    padding = 12
                    bounds = (
                        max(0, bounds[0] - padding),
                        max(0, bounds[1] - padding),
                        min(image.width, bounds[2] + padding),
                        min(image.height, bounds[3] + padding),
                    )
                    image = image.crop(bounds)
                image.save(self.signature_path)

            if not self.signature_path or not os.path.isfile(self.signature_path):
                messagebox.showwarning(
                    "DGKP-Stammdaten",
                    "Bitte zeichnen Sie zuerst eine Unterschrift.",
                    parent=self,
                )
                return
            _save_dgkp_settings(self.phone_var.get(), self.signature_path)
        except OSError as error:
            messagebox.showerror(
                "DGKP-Stammdaten",
                f"Einstellungen konnten nicht gespeichert werden:\n{error}",
                parent=self,
            )
            return
        self.destroy()


class MaterialOrderDialog(tk.Toplevel):
    INSURANCE_OPTIONS = ("ÖGK", "SVS", "BVAEB", "Andere")

    def __init__(self, parent, database_path, patient, template_path, output_dir):
        super().__init__(parent)
        self.database_path = database_path
        self.patient = patient
        self.template_path = template_path
        self.output_dir = output_dir
        self.result = False

        self.title("Neue Materialbestellung")
        self.geometry("780x760")
        self.minsize(700, 620)
        self.configure(bg="#f0f0f0")
        self.transient(parent)
        self.grab_set()
        self._build_form()

    def _build_form(self):
        style = ttk.Style(self)
        style.configure("Material.TCheckbutton", font=("Segoe UI", 11))
        style.configure("Material.TEntry", font=("Segoe UI", 11))
        style.configure("Material.TCombobox", font=("Segoe UI", 11))
        main = tk.Frame(self, bg="#f0f0f0", padx=18, pady=14)
        main.pack(fill="both", expand=True)
        tk.Label(
            main,
            text="Neue Materialbestellung",
            font=("Segoe UI", 17, "bold"),
            fg="#000000",
            bg="#f0f0f0",
        ).pack(anchor="w", pady=(0, 10))

        try:
            settings = _load_dgkp_settings()
        except RuntimeError as error:
            messagebox.showerror("Materialbestellung", str(error), parent=self)
            settings = {"phone": "", "signature": ""}
        self.settings = settings

        settings_frame = tk.Frame(main, bg="#f0f0f0", padx=10, pady=8)
        settings_frame.pack(fill="x", pady=(0, 8))
        tk.Label(
            settings_frame,
            text="DGKP: 168513 - Hager Birgit",
            font=("Segoe UI", 11, "bold"),
            fg="#000000",
            bg="#f0f0f0",
        ).pack(side="left")
        ttk.Button(
            settings_frame,
            text="DGKP-Einstellungen",
            command=self._edit_settings,
        ).pack(side="right")

        self.insurance_var = tk.StringVar(
            value=self._normalized_insurance(self.patient.get("krankenkasse"))
        )
        self.insurance_other_var = tk.StringVar(
            value=""
            if self.insurance_var.get() != "Andere"
            else str(self.patient.get("krankenkasse") or "")
        )
        self.prescription_date_var = tk.StringVar(
            value=datetime.date.today().strftime("%d.%m.%Y")
        )
        patient_vsnr = str(self.patient.get("versicherungsnummer") or "").strip()
        if not patient_vsnr and self.patient.get("geburtsdatum"):
            birth_date = str(self.patient["geburtsdatum"])
            try:
                patient_vsnr = datetime.date.fromisoformat(birth_date).strftime("%d.%m.%Y")
            except ValueError:
                patient_vsnr = birth_date
        self.patient_vsnr_var = tk.StringVar(value=patient_vsnr)
        self.patient_last_name_var = tk.StringVar(
            value=str(self.patient.get("nachname") or "")
        )
        self.patient_first_name_var = tk.StringVar(
            value=str(self.patient.get("vorname") or "")
        )
        self.postal_code_var = tk.StringVar(value=str(self.patient.get("plz") or ""))
        self.city_var = tk.StringVar(value=str(self.patient.get("ort") or ""))
        street = " ".join(
            part
            for part in (
                str(self.patient.get("strasse") or "").strip(),
                str(self.patient.get("hausnummer") or "").strip(),
                str(self.patient.get("adresszusatz") or "").strip(),
            )
            if part
        )
        self.street_var = tk.StringVar(value=street)
        self.different_insured_var = tk.BooleanVar(value=False)
        self.insured_vsnr_var = tk.StringVar()
        self.insured_last_name_var = tk.StringVar()
        self.insured_first_name_var = tk.StringVar()
        self.cost_exempt_var = tk.BooleanVar(value=False)
        self.fee_exempt_var = tk.BooleanVar(value=False)
        self.follow_up_var = tk.BooleanVar(value=False)

        form_container = tk.Frame(main, bg="#f0f0f0")
        form_container.pack(fill="both", expand=True)
        form_canvas = tk.Canvas(
            form_container,
            bg="#f0f0f0",
            highlightthickness=0,
        )
        form_scrollbar = ttk.Scrollbar(
            form_container,
            orient="vertical",
            command=form_canvas.yview,
        )
        form_canvas.configure(yscrollcommand=form_scrollbar.set)
        form_canvas.pack(side="left", fill="both", expand=True)
        form_scrollbar.pack(side="right", fill="y")
        form = tk.Frame(form_canvas, bg="#f0f0f0")
        form_window = form_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind(
            "<Configure>",
            lambda _event: form_canvas.configure(
                scrollregion=form_canvas.bbox("all")
            ),
        )
        form_canvas.bind(
            "<Configure>",
            lambda event: form_canvas.itemconfigure(form_window, width=event.width),
        )
        self._field_row(form, 0, "Versicherungsträger", [
            ("Krankenkasse", self.insurance_var, 16, self.INSURANCE_OPTIONS),
            ("Sonstige Kasse", self.insurance_other_var, 24, None),
        ])
        self._field_row(form, 1, "Patient", [
            ("VSNR", self.patient_vsnr_var, 18, None),
            ("Nachname", self.patient_last_name_var, 20, None),
            ("Vorname", self.patient_first_name_var, 20, None),
        ])
        self._field_row(form, 2, "Adresse", [
            ("PLZ", self.postal_code_var, 10, None),
            ("Ort", self.city_var, 20, None),
            ("Straße und Hausnummer", self.street_var, 32, None),
        ])

        ttk.Checkbutton(
            form,
            text="Versicherte Person ist nicht der Patient",
            variable=self.different_insured_var,
            command=self._toggle_insured_fields,
            style="Material.TCheckbutton",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 2))
        self.insured_frame = tk.Frame(form, bg="#f0f0f0")
        self.insured_frame.grid(row=4, column=0, columnspan=4, sticky="ew")
        self._field_row(self.insured_frame, 0, "Versicherte Person", [
            ("VSNR", self.insured_vsnr_var, 18, None),
            ("Nachname", self.insured_last_name_var, 20, None),
            ("Vorname", self.insured_first_name_var, 20, None),
        ])
        self._toggle_insured_fields()

        exempt_frame = tk.Frame(form, bg="#f0f0f0")
        exempt_frame.grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))
        for text, variable in (
            ("Kostenanteilsbefreiung", self.cost_exempt_var),
            ("Rezeptgebührenbefreiung", self.fee_exempt_var),
            ("Folgeverordnung", self.follow_up_var),
        ):
            ttk.Checkbutton(
                exempt_frame,
                text=text,
                variable=variable,
                style="Material.TCheckbutton",
            ).pack(side="left", padx=(0, 12))

        self.diagnosis_var = tk.StringVar(value=str(self.patient.get("diagnose") or ""))
        self._field_row(form, 6, "Diagnose", [
            ("Diagnose", self.diagnosis_var, 70, None),
        ])

        tk.Label(
            form,
            text="Verordnung / Produkt (bei jeder Bestellung neu eingeben)",
            font=("Segoe UI", 11, "bold"),
            fg="#000000",
            bg="#f0f0f0",
        ).grid(row=7, column=0, columnspan=4, sticky="w", pady=(10, 4))
        self.products_text = tk.Text(
            form,
            height=5,
            wrap="word",
            font=("Segoe UI", 12),
            bg="white",
            fg="black",
            relief="sunken",
        )
        self.products_text.grid(row=8, column=0, columnspan=4, sticky="ew")

        previous = self._get_previous_products()
        tk.Label(
            form,
            text=f"Letzte Bestellung (nur als Hinweis): {previous or 'Noch keine Bestellung'}",
            font=("Segoe UI", 10),
            fg="#555555",
            bg="#f0f0f0",
            justify="left",
            wraplength=720,
        ).grid(row=9, column=0, columnspan=4, sticky="w", pady=(4, 8))

        self._field_row(form, 10, "Verordnungsdatum", [
            ("Datum (TT.MM.JJJJ)", self.prescription_date_var, 16, None),
        ])
        self.phone_label = tk.Label(
            form,
            text=f"Telefon-/Handy-Nr. DGKP: {self.settings.get('phone') or 'bitte in DGKP-Einstellungen hinterlegen'}",
            font=("Segoe UI", 11),
            fg="#000000",
            bg="#f0f0f0",
        )
        self.phone_label.grid(row=11, column=0, columnspan=4, sticky="w", pady=(6, 2))
        tk.Label(
            form,
            text="Die Strichcode-Seite wird automatisch aus dem 50-seitigen Formularsatz gewählt.",
            font=("Segoe UI", 10),
            fg="#555555",
            bg="#f0f0f0",
        ).grid(row=12, column=0, columnspan=4, sticky="w", pady=(2, 8))

        button_frame = tk.Frame(main, bg="#f0f0f0")
        button_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(button_frame, text="Abbrechen", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(
            button_frame,
            text="Bestellung speichern und PDF erstellen",
            command=self._save_order,
        ).pack(side="right")

    def _field_row(self, parent, row, title, fields):
        tk.Label(
            parent,
            text=title,
            font=("Segoe UI", 11, "bold"),
            fg="#000000",
            bg="#f0f0f0",
        ).grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=4)
        fields_frame = tk.Frame(parent, bg="#f0f0f0")
        fields_frame.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        for label, variable, width, values in fields:
            item = tk.Frame(fields_frame, bg="#f0f0f0")
            item.pack(side="left", fill="x", expand=True, padx=(0, 7))
            tk.Label(
                item,
                text=label,
                font=("Segoe UI", 10),
                fg="#555555",
                bg="#f0f0f0",
            ).pack(anchor="w")
            if values:
                widget = ttk.Combobox(
                    item,
                    textvariable=variable,
                    values=values,
                    state="readonly",
                    width=width,
                    style="Material.TCombobox",
                )
            else:
                widget = ttk.Entry(
                    item,
                    textvariable=variable,
                    style="Material.TEntry",
                    width=width,
                )
            widget.pack(fill="x", ipady=4)

    @staticmethod
    def _normalized_insurance(value):
        value = str(value or "").strip()
        normalized = value.casefold()
        if normalized in {"ögk", "oegk"} or "gesundheitskasse" in normalized:
            return "ÖGK"
        if normalized == "svs" or "sozialversicherung der selbständigen" in normalized:
            return "SVS"
        if normalized == "bvaeb" or "versicherungsanstalt öffentlich bediensteter" in normalized:
            return "BVAEB"
        return "Andere" if value else "ÖGK"

    def _toggle_insured_fields(self):
        if self.different_insured_var.get():
            self.insured_frame.grid()
        else:
            self.insured_frame.grid_remove()

    def _get_previous_products(self):
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT products
                FROM material_orders
                WHERE patient_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (self.patient["id"],),
            ).fetchone()
        return row[0] if row else ""

    def _edit_settings(self):
        dialog = DgkpSettingsDialog(self)
        self.wait_window(dialog)
        try:
            self.settings = _load_dgkp_settings()
        except RuntimeError as error:
            messagebox.showerror("DGKP-Stammdaten", str(error), parent=self)
            return
        self.phone_label.configure(
            text=(
                "Telefon-/Handy-Nr. DGKP: "
                f"{self.settings.get('phone') or 'bitte in DGKP-Einstellungen hinterlegen'}"
            )
        )

    def _collect_order_data(self):
        products = self.products_text.get("1.0", "end-1c").strip()
        if not products:
            raise ValueError("Bitte geben Sie die zu bestellenden Materialien ein.")
        if not self.patient_last_name_var.get().strip() or not self.patient_first_name_var.get().strip():
            raise ValueError("Vor- und Nachname des Patienten müssen angegeben sein.")
        if self.insurance_var.get() == "Andere" and not self.insurance_other_var.get().strip():
            raise ValueError("Bitte geben Sie den sonstigen Versicherungsträger an.")
        if self.different_insured_var.get() and not (
            self.insured_last_name_var.get().strip()
            and self.insured_first_name_var.get().strip()
        ):
            raise ValueError("Bitte Vor- und Nachname der versicherten Person angeben.")
        try:
            prescription_date = datetime.datetime.strptime(
                self.prescription_date_var.get().strip(),
                "%d.%m.%Y",
            ).strftime("%Y-%m-%d")
        except ValueError as error:
            raise ValueError("Das Verordnungsdatum muss im Format TT.MM.JJJJ angegeben sein.") from error

        signature_path = self.settings.get("signature", "")
        if not signature_path or not os.path.isfile(signature_path):
            raise ValueError("Bitte hinterlegen Sie zuerst Ihre Unterschrift unter DGKP-Einstellungen.")
        if not self.settings.get("phone", "").strip():
            raise ValueError("Bitte hinterlegen Sie zuerst Ihre Telefonnummer unter DGKP-Einstellungen.")

        return {
            "prescription_date": prescription_date,
            "insurance": self.insurance_var.get(),
            "insurance_other": self.insurance_other_var.get().strip(),
            "patient_vsnr": self.patient_vsnr_var.get().strip(),
            "patient_first_name": self.patient_first_name_var.get().strip(),
            "patient_last_name": self.patient_last_name_var.get().strip(),
            "patient_postal_code": self.postal_code_var.get().strip(),
            "patient_city": self.city_var.get().strip(),
            "patient_street": self.street_var.get().strip(),
            "insured_vsnr": self.insured_vsnr_var.get().strip() if self.different_insured_var.get() else "",
            "insured_first_name": self.insured_first_name_var.get().strip() if self.different_insured_var.get() else "",
            "insured_last_name": self.insured_last_name_var.get().strip() if self.different_insured_var.get() else "",
            "cost_exempt": int(self.cost_exempt_var.get()),
            "prescription_fee_exempt": int(self.fee_exempt_var.get()),
            "diagnosis": self.diagnosis_var.get().strip(),
            "products": products,
            "follow_up": int(self.follow_up_var.get()),
            "dgkp_phone": self.settings["phone"].strip(),
            "signature": signature_path,
        }

    def _save_order(self):
        try:
            order = self._collect_order_data()
            page_number, form_number, pdf_path = self._create_order_pdf(order)
        except (ValueError, OSError, RuntimeError, sqlite3.Error, pymupdf.FileDataError) as error:
            messagebox.showerror("Materialbestellung", str(error), parent=self)
            return

        self.result = True
        messagebox.showinfo(
            "Materialbestellung",
            f"Bestellung gespeichert.\nFormularseite: {page_number} von 50\nLaufnummer: {form_number}\n\nPDF: {pdf_path}",
            parent=self,
        )
        open_material_order_pdf(pdf_path, self)
        self.destroy()

    def _create_order_pdf(self, order):
        os.makedirs(self.output_dir, exist_ok=True)
        temporary_path = ""
        final_path = ""
        now = datetime.datetime.now()
        committed = False
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT template_page FROM material_orders ORDER BY id DESC LIMIT 1"
                ).fetchone()
                page_number = ((int(row[0]) if row else 0) % 50) + 1

                source = pymupdf.open(self.template_path)
                try:
                    if len(source) != 50:
                        raise RuntimeError(
                            "Die Druckvorlage muss genau 50 nummerierte Seiten enthalten."
                        )
                    result = pymupdf.open()
                    try:
                        result.insert_pdf(
                            source,
                            from_page=page_number - 1,
                            to_page=page_number - 1,
                        )
                        page = result[0]
                        self._overlay_order(page, order)
                        form_number = f"{50 + page_number:05d}"
                        patient_name = (
                            f"{order['patient_last_name']} {order['patient_first_name']}"
                        ).strip()
                        timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
                        safe_name = re.sub(
                            r"[^A-Za-z0-9._-]+",
                            "_",
                            patient_name,
                        ).strip("_")
                        final_path = os.path.join(
                            self.output_dir,
                            f"VO_{safe_name}_{form_number}_{timestamp}.pdf",
                        )
                        temporary_path = f"{final_path}.tmp.pdf"
                        result.save(temporary_path, garbage=4, deflate=True)
                    finally:
                        result.close()
                finally:
                    source.close()

                connection.execute(
                    """
                    INSERT INTO material_orders (
                        patient_id, created_at, prescription_date, insurance, insurance_other,
                        patient_vsnr, patient_first_name, patient_last_name, patient_postal_code,
                        patient_city, patient_street, insured_vsnr, insured_first_name,
                        insured_last_name, cost_exempt, prescription_fee_exempt, diagnosis,
                        products, follow_up, dgkp_phone, template_page, form_number, pdf_path
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        self.patient["id"],
                        now.isoformat(timespec="seconds"),
                        order["prescription_date"],
                        order["insurance"],
                        order["insurance_other"],
                        order["patient_vsnr"],
                        order["patient_first_name"],
                        order["patient_last_name"],
                        order["patient_postal_code"],
                        order["patient_city"],
                        order["patient_street"],
                        order["insured_vsnr"],
                        order["insured_first_name"],
                        order["insured_last_name"],
                        order["cost_exempt"],
                        order["prescription_fee_exempt"],
                        order["diagnosis"],
                        order["products"],
                        order["follow_up"],
                        order["dgkp_phone"],
                        page_number,
                        form_number,
                        final_path,
                    ),
                )
                os.replace(temporary_path, final_path)
                connection.commit()
                committed = True
        finally:
            if not committed:
                for path in (temporary_path, final_path):
                    if path and os.path.exists(path):
                        os.remove(path)

        return page_number, form_number, final_path

    @staticmethod
    def _overlay_order(page, order):
        black = (0, 0, 0)

        def write(rect, text, size=9, max_size=None):
            if not text:
                return
            bounds = pymupdf.Rect(rect)
            inset = 2
            bounds.x0 += inset
            bounds.y0 += inset
            bounds.x1 -= inset
            bounds.y1 -= inset
            font_size = max_size or size
            while font_size >= 6:
                remaining = page.insert_textbox(
                    bounds,
                    text,
                    fontname="helv",
                    fontsize=font_size,
                    color=black,
                    lineheight=1.15,
                    overlay=True,
                )
                if remaining >= 0:
                    return
                font_size -= 0.5
            raise ValueError(f"Der Text passt nicht in das Formularfeld: {text[:50]}")

        def check(x, y, selected):
            if not selected:
                return
            page.draw_line((x, y + 4), (x + 3, y + 7), color=black, width=1.3, overlay=True)
            page.draw_line((x + 3, y + 7), (x + 8, y), color=black, width=1.3, overlay=True)

        insurance_index = {
            "ÖGK": 226.7,
            "SVS": 277.7,
            "BVAEB": 328.7,
            "Andere": 403.6,
        }.get(order["insurance"], 403.6)
        check(insurance_index, 79.0, True)
        if order["insurance"] == "Andere":
            write((451.7, 74.0, 536.0, 92.8), order["insurance_other"], size=8)

        write((61.8, 117.7, 211.9, 139.1), order["patient_vsnr"])
        write((224.0, 117.7, 374.2, 139.1), order["patient_last_name"])
        write((385.9, 117.7, 536.0, 139.1), order["patient_first_name"])
        write((61.8, 163.1, 211.9, 184.4), order["patient_postal_code"])
        write((224.0, 163.1, 374.2, 184.4), order["patient_city"])
        write((385.9, 163.1, 536.0, 184.4), order["patient_street"])

        write((61.8, 211.0, 211.9, 232.4), order["insured_vsnr"])
        write((224.0, 211.0, 374.2, 232.4), order["insured_last_name"])
        write((385.9, 211.0, 536.0, 232.4), order["insured_first_name"])
        check(64.4, 238.6, bool(order["cost_exempt"]))
        check(303.1, 238.6, bool(order["prescription_fee_exempt"]))
        write((61.8, 266.2, 536.0, 317.8), order["diagnosis"], size=9, max_size=10)
        write((61.8, 343.0, 536.0, 426.7), order["products"], size=9, max_size=10)
        check(303.1, 330.7, bool(order["follow_up"]))

        date_text = datetime.datetime.strptime(
            order["prescription_date"],
            "%Y-%m-%d",
        ).strftime("%d.%m.%Y")
        write((61.8, 480.0, 150.4, 501.5), date_text, size=8)
        write((159.5, 480.0, 291.0, 501.5), order["dgkp_phone"], size=8)
        signature = order["signature"]
        if not os.path.isfile(signature):
            raise FileNotFoundError("Die gespeicherte DGKP-Unterschrift wurde nicht gefunden.")
        page.insert_image(
            pymupdf.Rect(300.5, 480.0, 519.6, 501.5),
            filename=signature,
            keep_proportion=True,
            overlay=True,
        )
