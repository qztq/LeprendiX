import datetime
import logging
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from config_loader import CONFIG
from mobile_connect import MobileServer
from material_orders import (
    MaterialOrderDialog,
    _find_template,
    get_patient_material_orders,
    open_material_order_pdf,
)


BACKGROUND = "#f0f0f0"
PANEL = "#f0f0f0"
PANEL_ALT = "#d0d0d0"
ACCENT = "#d0d0d0"
TEXT = "#000000"
MUTED = "#555555"


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _configured_path(config_key, fallback):
    configured = CONFIG.get(config_key, fallback)
    if not configured:
        return ""
    if os.path.isabs(configured):
        return configured
    return os.path.join(_base_dir(), configured)


def _patient_folder_path(patient, create=False):
    folder_name = (
        f"{patient.get('nachname') or ''} {patient.get('vorname') or ''}".strip()
    )
    if not folder_name:
        raise ValueError("Für den Patientenordner fehlen Vor- oder Nachname.")

    active_root = _configured_path("PATIENT_BASE_DIR", "") or _base_dir()
    archive_root = _configured_path("ARCHIVE_DIR", "")
    roots = (
        (archive_root, active_root)
        if patient.get("is_archived", 0)
        else (active_root, archive_root)
    )
    for root in roots:
        if root:
            path = os.path.join(root, folder_name)
            if os.path.isdir(path):
                return path

    if create:
        root = roots[0] or active_root
        path = os.path.join(root, folder_name)
        os.makedirs(path, exist_ok=True)
        return path
    return ""


def _move_archived_patient_folder(patient):
    folder_name = f"{patient.get('nachname') or ''} {patient.get('vorname') or ''}".strip()
    if not folder_name:
        raise ValueError("Für den Patientenordner fehlen Vor- oder Nachname.")

    active_root = _configured_path("PATIENT_BASE_DIR", "") or _base_dir()
    archive_root = _configured_path("ARCHIVE_DIR", "")
    if not archive_root or os.path.normcase(os.path.abspath(archive_root)) == os.path.normcase(
        os.path.abspath(active_root)
    ):
        return None

    source = os.path.join(archive_root, folder_name)
    destination = os.path.join(active_root, folder_name)
    if not os.path.isdir(source):
        return None
    if os.path.exists(destination):
        raise FileExistsError(
            f"Der aktive Patientenordner existiert bereits:\n{destination}"
        )

    os.makedirs(active_root, exist_ok=True)
    shutil.move(source, destination)
    return source, destination


def _restore_moved_patient_folder(moved_folder):
    if not moved_folder:
        return
    source, destination = moved_folder
    if os.path.exists(destination) and not os.path.exists(source):
        os.makedirs(os.path.dirname(source), exist_ok=True)
        shutil.move(destination, source)


def open_patient_records(parent):
    database_path = _configured_path("DATABASE_NAME", "patienten.db")
    if not os.path.isfile(database_path):
        messagebox.showerror(
            "Patientenakten",
            f"Die Datenbank wurde nicht gefunden:\n{database_path}",
            parent=parent,
        )
        return

    PatientRecordsWindow(parent, database_path)


class PatientRecordsWindow(tk.Toplevel):
    def __init__(self, parent, database_path):
        super().__init__(parent)
        self.database_path = database_path
        self.patient_rows = {}
        self.companion_server = None
        self.companion_dialog = None
        self.companion_qr_image = None

        self.title("LeprendiX - Patientenakten")
        self.geometry("1000x700")
        self.minsize(850, 550)
        self.configure(bg=BACKGROUND)

        self._configure_styles()
        self._build_window()
        self._load_patients()

    def _configure_styles(self):
        style = ttk.Style(self)
        style.configure(
            "Records.Treeview",
            rowheight=34,
            font=("Segoe UI", 13),
        )
        style.configure("Records.Treeview.Heading", font=("Segoe UI", 13, "bold"))
        style.configure("Records.TEntry", font=("Segoe UI", 13))

    def _build_window(self):
        header = tk.Frame(
            self,
            bg=BACKGROUND,
            highlightbackground=ACCENT,
            highlightthickness=1,
            padx=18,
            pady=12,
        )
        header.pack(fill="x", padx=16, pady=(16, 10))
        tk.Label(
            header,
            text="PATIENTENAKTEN",
            font=("Segoe UI", 18, "bold"),
            fg=TEXT,
            bg=BACKGROUND,
        ).pack(side="left")
        tk.Label(
            header,
            text="Aktive und archivierte Patienten",
            font=("Segoe UI", 12),
            fg=TEXT,
            bg=BACKGROUND,
        ).pack(side="right", padx=4)

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=18, pady=(0, 8))
        ttk.Button(
            actions,
            text="Neuen Patienten anlegen",
            command=self._add_patient,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="Aus Companion-App importieren",
            command=self._open_companion_import,
        ).pack(side="left")

        search_frame = tk.Frame(self, bg=BACKGROUND)
        search_frame.pack(fill="x", padx=18, pady=(4, 10))
        tk.Label(
            search_frame,
            text="Patient suchen:",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT,
            bg=BACKGROUND,
        ).pack(side="left", padx=(0, 10))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            style="Records.TEntry",
        )
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.search_var.trace_add("write", self._filter_patients)
        self.search_entry.bind("<Return>", self._open_selected_patient)

        content = tk.Frame(self, bg=BACKGROUND)
        content.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        list_frame = tk.Frame(
            content,
            bg=PANEL,
            highlightbackground=PANEL_ALT,
            highlightthickness=1,
        )
        list_frame.grid(row=0, column=0, sticky="nsew")
        self.patient_tree = ttk.Treeview(
            list_frame,
            style="Records.Treeview",
            columns=("nachname", "vorname", "status"),
            show="headings",
            selectmode="browse",
        )
        self.patient_tree.heading("nachname", text="Nachname")
        self.patient_tree.heading("vorname", text="Vorname")
        self.patient_tree.heading("status", text="Status")
        self.patient_tree.column("nachname", width=300)
        self.patient_tree.column("vorname", width=280)
        self.patient_tree.column("status", width=180, anchor="center")
        self.patient_tree.tag_configure("archived", foreground=MUTED)
        self.patient_tree.tag_configure("active", foreground=TEXT)
        self.patient_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.patient_tree.yview,
        )
        scrollbar.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.patient_tree.configure(yscrollcommand=scrollbar.set)
        self.patient_tree.bind("<Double-1>", self._open_selected_patient)
        self.patient_tree.bind("<Return>", self._open_selected_patient)

        tk.Label(
            content,
            text="Doppelklick oder Enter öffnet die Patientenakte.",
            font=("Segoe UI", 11),
            fg=MUTED,
            bg=BACKGROUND,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _load_patients(self):
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.row_factory = sqlite3.Row
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'patienten'"
                )
                if cursor.fetchone() is None:
                    raise sqlite3.OperationalError(
                        "Die Tabelle 'patienten' fehlt in der Datenbank."
                    )
                cursor.execute(
                    """
                    SELECT *
                    FROM patienten
                    ORDER BY LOWER(COALESCE(nachname, '')),
                             LOWER(COALESCE(vorname, '')),
                             id
                    """
                )
                self.patient_rows = {
                    str(row["id"]): dict(row)
                    for row in cursor.fetchall()
                }
        except sqlite3.Error as error:
            messagebox.showerror(
                "Patientenakten",
                f"Patienten konnten nicht aus der Datenbank geladen werden:\n{error}",
                parent=self,
            )
            self.destroy()
            return

        self._filter_patients()
        self.search_entry.focus_set()

    def _filter_patients(self, *_):
        if not hasattr(self, "patient_tree"):
            return
        search_term = self.search_var.get().strip().casefold()
        self.patient_tree.delete(*self.patient_tree.get_children())
        for patient_id, row in self.patient_rows.items():
            first_name = str(row.get("vorname") or "")
            last_name = str(row.get("nachname") or "")
            if search_term and search_term not in f"{first_name} {last_name}".casefold():
                continue

            archived = bool(row.get("is_archived", 0))
            self.patient_tree.insert(
                "",
                tk.END,
                iid=patient_id,
                values=(
                    last_name,
                    first_name,
                    "ARCHIVIERT" if archived else "Aktiv",
                ),
                tags=("archived" if archived else "active",),
            )

    def _open_selected_patient(self, _event=None):
        selection = self.patient_tree.selection()
        if not selection:
            return "break"
        row = self.patient_rows.get(selection[0])
        if row is not None:
            PatientRecordWindow(self, self.database_path, row)
        return "break"

    def _add_patient(self):
        PatientEntryDialog(self, self.database_path, self._patient_created)

    def _patient_created(self, patient, is_new):
        self._load_patients()
        if not patient:
            return

        def assigned(success):
            if not success and is_new:
                try:
                    with sqlite3.connect(self.database_path) as connection:
                        connection.execute(
                            "DELETE FROM patienten WHERE id = ?",
                            (patient["id"],),
                        )
                except sqlite3.Error as error:
                    logging.exception("Neuer Patient ohne Stammdaten konnte nicht zurückgenommen werden.")
                    messagebox.showerror(
                        "Patientenakte",
                        f"Der Patient wurde gespeichert, aber die abgebrochene Anlage "
                        f"konnte nicht zurückgenommen werden:\n{error}",
                        parent=self,
                    )
                self._load_patients()
                return
            if success:
                self._load_patients()
                PatientRecordWindow(self, self.database_path, patient)

        StammdatenAssignmentWindow(
            self,
            self.database_path,
            [patient],
            assigned,
            allow_cancel=True,
        )

    def _open_companion_import(self):
        if self.companion_server is None:
            server = MobileServer(
                callback_function=lambda _data: None,
                batch_callback=self._on_companion_batch,
                db_path=self.database_path,
            )
            for port in range(5000, 5010):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind(("0.0.0.0", port))
                    except OSError:
                        continue
                    server.port = port
                    break
            else:
                messagebox.showerror(
                    "Companion-App",
                    "Für den Companion-Import ist kein freier Port zwischen 5000 und 5009 verfügbar.",
                    parent=self,
                )
                return
            self.companion_server = server
            server.start()

        if self.companion_dialog and self.companion_dialog.winfo_exists():
            self.companion_dialog.lift()
            return

        dialog = tk.Toplevel(self)
        self.companion_dialog = dialog
        dialog.title("Companion-App importieren")
        dialog.geometry("480x570")
        dialog.transient(self)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

        ttk.Label(
            dialog,
            text="Companion-App verbinden",
            font=("Segoe UI", 15, "bold"),
        ).pack(padx=18, pady=(18, 8))
        ttk.Label(
            dialog,
            text=(
                "QR-Code mit dem Tablet scannen. In der Companion-App anschließend "
                "den ausstehenden Monats-Sync starten. Nach dem Import wird für jeden "
                "Patienten eine Stammdaten-Leistung zugeordnet."
            ),
            wraplength=430,
            justify="left",
        ).pack(padx=18, pady=(0, 10))
        try:
            qr_image = self.companion_server.get_qr_image().resize(
                (300, 300),
                Image.Resampling.LANCZOS,
            )
            self.companion_qr_image = ImageTk.PhotoImage(qr_image, master=dialog)
        except Exception as error:
            logging.exception("Companion-QR-Code konnte nicht erstellt werden.")
            dialog.destroy()
            self.companion_dialog = None
            messagebox.showerror(
                "Companion-App",
                f"Der QR-Code konnte nicht erstellt werden:\n{error}",
                parent=self,
            )
            return
        ttk.Label(dialog, image=self.companion_qr_image).pack(pady=5)
        url = (
            f"http://{self.companion_server.host_ip}:{self.companion_server.port}"
            f"/?token={self.companion_server.token}"
        )
        ttk.Label(
            dialog,
            text=url,
            wraplength=430,
            justify="center",
        ).pack(padx=18, pady=(4, 10))
        self.companion_status = ttk.Label(
            dialog,
            text="Warte auf den Sync aus der Companion-App.",
        )
        self.companion_status.pack(pady=(0, 10))
        ttk.Button(dialog, text="Schließen", command=dialog.destroy).pack(pady=(0, 16))

    def _on_companion_batch(self, patients):
        completed = threading.Event()
        result = {"success": False}

        def open_wizard():
            try:
                if not patients:
                    result["success"] = True
                    completed.set()
                    return

                def finish(success):
                    result["success"] = success
                    completed.set()

                StammdatenAssignmentWindow(
                    self,
                    self.database_path,
                    patients,
                    finish,
                    allow_cancel=True,
                )
            except Exception:
                logging.exception("Stammdaten-Assistent für Companion-Import konnte nicht geöffnet werden.")
                completed.set()

        try:
            self.after(0, open_wizard)
        except tk.TclError:
            logging.exception("Patientenaktenfenster wurde vor dem Stammdaten-Assistenten geschlossen.")
            return False

        if not completed.wait(timeout=1800):
            logging.error("Zeitüberschreitung beim Stammdaten-Assistenten des Companion-Imports.")
            return False

        if result["success"]:
            try:
                self.after(0, self._load_patients)
            except tk.TclError:
                logging.exception("Patientenliste konnte nach dem Companion-Import nicht aktualisiert werden.")
        return result["success"]


class PatientRecordWindow(tk.Toplevel):
    FIELD_LABELS = {
        "id": "Patienten-ID",
        "vorname": "Vorname",
        "nachname": "Nachname",
        "anrede": "Anrede",
        "strasse": "Straße",
        "hausnummer": "Hausnummer",
        "adresszusatz": "Adresszusatz",
        "plz": "PLZ",
        "ort": "Ort",
        "versicherungsnummer": "Versicherungsnummer",
        "krankenkasse": "Krankenkasse",
        "diagnose": "Diagnose",
        "kilometergeld": "Kilometergeld",
        "last_selected_kurznamen": "Zuletzt gewählte Abrechnungspositionen",
        "invoiced_since_reset": "Abrechnungsstatus",
        "is_archived": "Archivstatus",
    }

    FIELD_GROUPS = (
        ("Person", ("anrede", "vorname", "nachname")),
        (
            "Adresse",
            ("strasse", "hausnummer", "adresszusatz", "plz", "ort"),
        ),
        (
            "Versicherung",
            ("versicherungsnummer", "krankenkasse", "diagnose"),
        ),
        (
            "Praxisdaten",
            (
                "id",
                "kilometergeld",
                "last_selected_kurznamen",
                "invoiced_since_reset",
                "is_archived",
            ),
        ),
    )

    def __init__(self, parent, database_path, patient):
        super().__init__(parent)
        self.database_path = database_path
        self.patient = patient
        self.invoice_paths = {}
        self.material_order_paths = {}
        self.material_order_tree = None
        self.invoice_tree = None

        first_name = patient.get("vorname") or ""
        last_name = patient.get("nachname") or ""
        status = " [ARCHIVIERT]" if patient.get("is_archived", 0) else ""
        self.title(f"Patientenakte - {last_name} {first_name}{status}")
        self.geometry("1200x820")
        self.minsize(950, 620)
        self.configure(bg=BACKGROUND)

        header = tk.Frame(
            self,
            bg=PANEL,
            padx=16,
            pady=10,
        )
        header.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(
            header,
            text=f"{last_name} {first_name}",
            font=("Segoe UI", 18, "bold"),
            fg=TEXT,
            bg=PANEL,
        ).pack(side="left")
        if patient.get("is_archived", 0):
            tk.Label(
                header,
                text="ARCHIVIERT",
                font=("Segoe UI", 12, "bold"),
                fg=MUTED,
                bg=PANEL,
            ).pack(side="right")

        self._build_patient_details()
        self._build_activity_lists()
        self._load_material_orders()
        self._load_invoices()

    def _build_patient_details(self):
        details_frame = tk.Frame(self, bg=BACKGROUND)
        details_frame.pack(fill="x", padx=14, pady=(0, 10))
        used_fields = set()

        details_frame.columnconfigure(0, weight=1, uniform="details")
        details_frame.columnconfigure(1, weight=1, uniform="details")
        for group_index, (group_title, fields) in enumerate(self.FIELD_GROUPS):
            group = tk.LabelFrame(
                details_frame,
                text=group_title,
                font=("Segoe UI", 12, "bold"),
                fg=TEXT,
                bg=PANEL,
                padx=10,
                pady=8,
                labelanchor="nw",
            )
            group.grid(
                row=group_index // 2,
                column=group_index % 2,
                sticky="nsew",
                padx=(0 if group_index % 2 == 0 else 8, 0),
                pady=(0 if group_index < 2 else 8, 0),
            )
            group.columnconfigure(1, weight=1)
            for row_index, field in enumerate(fields):
                if field not in self.patient:
                    continue
                used_fields.add(field)
                self._add_detail_row(group, row_index, field, self.patient[field])

        extra_fields = [
            (field, value)
            for field, value in self.patient.items()
            if field not in used_fields
        ]
        if extra_fields:
            group = tk.LabelFrame(
                details_frame,
                text="Weitere Daten",
                font=("Segoe UI", 12, "bold"),
                fg=TEXT,
                bg=PANEL,
                padx=10,
                pady=8,
                labelanchor="nw",
            )
            group.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
            for row_index, (field, value) in enumerate(extra_fields):
                self._add_detail_row(group, row_index, field, value)

    def _add_detail_row(self, parent, row, field, value):
        label = self.FIELD_LABELS.get(
            field,
            field.replace("_", " ").capitalize(),
        )
        display_value = self._format_field_value(field, value)
        tk.Label(
            parent,
            text=f"{label}:",
            font=("Segoe UI", 11, "bold"),
            fg="#000000",
            bg=PANEL,
            anchor="w",
        ).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=3)
        tk.Label(
            parent,
            text=display_value,
            font=("Segoe UI", 12),
            fg=TEXT,
            bg=PANEL,
            anchor="w",
            justify="left",
            wraplength=250,
        ).grid(row=row, column=1, sticky="new", pady=3)

    def _build_activity_lists(self):
        activity_frame = tk.Frame(self, bg=BACKGROUND)
        activity_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        activity_frame.columnconfigure(0, weight=1, uniform="activity")
        activity_frame.columnconfigure(1, weight=1, uniform="activity")
        activity_frame.rowconfigure(0, weight=1)

        orders_frame = self._create_list_panel(
            activity_frame,
            title="Materialbestellungen",
            columns=("datum", "produkte", "laufnummer"),
            headings=("Datum", "Verordnung / Produkt", "Laufnummer"),
        )
        orders_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.material_order_tree = orders_frame.tree
        self.material_order_tree.bind("<Double-1>", self._open_selected_material_order)
        self.material_order_tree.bind("<Return>", self._open_selected_material_order)

        invoices_frame = self._create_list_panel(
            activity_frame,
            title="Honorarnoten",
            columns=("datum", "datei"),
            headings=("Dateidatum", "Datei"),
        )
        invoices_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.invoice_tree = invoices_frame.tree
        self.invoice_tree.bind("<Double-1>", self._open_selected_invoice)
        self.invoice_tree.bind("<Return>", self._open_selected_invoice)

        self.material_order_tree.column("datum", width=120, anchor="center")
        self.material_order_tree.column("produkte", width=300)
        self.material_order_tree.column("laufnummer", width=110, anchor="center")
        self.invoice_tree.column("datum", width=145, anchor="center")
        self.invoice_tree.column("datei", width=300)

        ttk.Button(
            orders_frame.button_frame,
            text="Neue Materialbestellung",
            command=self._create_material_order,
        ).pack(side="left", padx=(4, 6), pady=6)
        ttk.Button(
            orders_frame.button_frame,
            text="Bestellung öffnen",
            command=self._open_selected_material_order,
        ).pack(side="left", padx=4, pady=6)
        ttk.Button(
            invoices_frame.button_frame,
            text="Honorarnote öffnen",
            command=self._open_selected_invoice,
        ).pack(side="left", padx=4, pady=6)

    def _create_list_panel(self, parent, title, columns, headings):
        panel = tk.LabelFrame(
            parent,
            text=title,
            font=("Segoe UI", 13, "bold"),
            fg=TEXT,
            bg=PANEL,
            padx=6,
            pady=6,
            labelanchor="nw",
        )
        button_frame = ttk.Frame(panel)
        button_frame.pack(side="bottom", fill="x", padx=4)
        tree_frame = ttk.Frame(panel)
        tree_frame.pack(side="top", fill="both", expand=True)
        tree = ttk.Treeview(
            tree_frame,
            style="Records.Treeview",
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
        tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=4)
        tree.configure(yscrollcommand=scrollbar.set)
        panel.tree = tree
        panel.button_frame = button_frame
        return panel

    @staticmethod
    def _format_value(value):
        if value is None or value == "":
            return "—"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    def _format_field_value(self, field, value):
        if field == "is_archived":
            return "Ja" if value else "Nein"
        if field == "invoiced_since_reset":
            return "Abgerechnet" if value else "Offen"
        if field == "kilometergeld" and value is not None:
            return f"{value:.2f} €"
        if field == "last_selected_kurznamen" and value:
            return str(value).replace(",", ", ")
        return self._format_value(value)

    def _load_material_orders(self):
        try:
            orders = get_patient_material_orders(
                self.database_path,
                self.patient["id"],
            )
        except sqlite3.Error as error:
            messagebox.showerror(
                "Patientenakte",
                f"Materialbestellungen konnten nicht geladen werden:\n{error}",
                parent=self,
            )
            return

        for index, order in enumerate(orders):
            item_id = str(index)
            self.material_order_paths[item_id] = order["pdf_path"]
            self.material_order_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    self._format_date(order["created_at"]),
                    order["products"],
                    order["form_number"],
                ),
            )

    def _create_material_order(self):
        try:
            template_path = _find_template(_base_dir())
        except FileNotFoundError as error:
            messagebox.showerror("Materialbestellung", str(error), parent=self)
            return
        try:
            patient_folder = _patient_folder_path(self.patient, create=True)
            output_dir = os.path.join(patient_folder, "Materialbestellungen")
            os.makedirs(output_dir, exist_ok=True)
        except (OSError, ValueError) as error:
            logging.exception("Patientenordner für Materialbestellung konnte nicht angelegt werden.")
            messagebox.showerror(
                "Materialbestellung",
                f"Der Patientenordner konnte nicht vorbereitet werden:\n{error}",
                parent=self,
            )
            return
        dialog = MaterialOrderDialog(
            self,
            self.database_path,
            self.patient,
            template_path,
            output_dir,
        )
        self.wait_window(dialog)
        if dialog.result:
            self.material_order_tree.delete(*self.material_order_tree.get_children())
            self.material_order_paths.clear()
            self._load_material_orders()

    def _open_selected_material_order(self, _event=None):
        selection = self.material_order_tree.selection()
        if not selection:
            return "break"
        open_material_order_pdf(
            self.material_order_paths.get(selection[0]),
            self,
        )
        return "break"

    def _patient_folder(self):
        return _patient_folder_path(self.patient)

    def _load_invoices(self):
        patient_folder = self._patient_folder()
        if not patient_folder:
            return

        try:
            invoices = []
            for root, _directories, filenames in os.walk(patient_folder):
                for filename in filenames:
                    extension = os.path.splitext(filename)[1].lower()
                    if not filename.casefold().startswith("honorarnote"):
                        continue
                    if extension not in {".docx", ".pdf"}:
                        continue
                    path = os.path.join(root, filename)
                    modified_at = os.path.getmtime(path)
                    invoices.append((modified_at, path, filename))
        except OSError as error:
            messagebox.showerror(
                "Patientenakte",
                f"Honorarnoten konnten nicht aus dem Patientenordner gelesen werden:\n{error}",
                parent=self,
            )
            return

        for index, (modified_at, path, filename) in enumerate(
            sorted(invoices, key=lambda invoice: invoice[0], reverse=True)
        ):
            item_id = str(index)
            self.invoice_paths[item_id] = path
            date_text = datetime.datetime.fromtimestamp(modified_at).strftime(
                "%d.%m.%Y %H:%M"
            )
            self.invoice_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(date_text, filename),
            )

    def _open_selected_invoice(self, _event=None):
        if self.invoice_tree is None:
            return "break"
        selection = self.invoice_tree.selection()
        if not selection:
            return "break"
        path = self.invoice_paths.get(selection[0])
        if not path or not os.path.isfile(path):
            messagebox.showerror(
                "Honorarnote",
                "Die ausgewählte Datei wurde nicht gefunden.",
                parent=self,
            )
            return "break"

        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as error:
            messagebox.showerror(
                "Honorarnote",
                f"Die Datei konnte nicht geöffnet werden:\n{error}",
                parent=self,
            )
        return "break"

    @staticmethod
    def _format_date(value):
        if not value:
            return ""
        try:
            return datetime.datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            try:
                return datetime.datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
            except ValueError:
                return str(value)


class PatientEntryDialog(tk.Toplevel):
    def __init__(self, parent, database_path, on_created):
        super().__init__(parent)
        self.database_path = database_path
        self.on_created = on_created
        self.title("Neuen Patienten anlegen")
        self.geometry("760x700")
        self.minsize(620, 560)
        self.transient(parent)
        self.grab_set()
        ttk.Style(self).configure("Patient.TEntry", font=("Segoe UI", 12))

        self.fields = {
            "anrede": tk.StringVar(value=""),
            "vorname": tk.StringVar(),
            "nachname": tk.StringVar(),
            "versicherungsnummer": tk.StringVar(),
            "krankenkasse": tk.StringVar(value="ÖGK"),
            "diagnose": tk.StringVar(),
            "strasse": tk.StringVar(),
            "hausnummer": tk.StringVar(),
            "adresszusatz": tk.StringVar(),
            "plz": tk.StringVar(),
            "ort": tk.StringVar(),
            "kilometergeld": tk.StringVar(value="0"),
        }

        content = ttk.Frame(self, padding=18)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Patientendaten", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))

        form_container = ttk.Frame(content)
        form_container.pack(fill="both", expand=True)
        form_canvas = tk.Canvas(form_container, highlightthickness=0)
        form_scrollbar = ttk.Scrollbar(
            form_container,
            orient="vertical",
            command=form_canvas.yview,
        )
        form_canvas.configure(yscrollcommand=form_scrollbar.set)
        form_scrollbar.pack(side="right", fill="y")
        form_canvas.pack(side="left", fill="both", expand=True)
        form = ttk.Frame(form_canvas, padding=(0, 0, 8, 0))
        form_window = form_canvas.create_window((0, 0), window=form, anchor="nw")

        def update_scroll_region(_event=None):
            form_canvas.configure(scrollregion=form_canvas.bbox("all"))

        def fit_form_width(event):
            form_canvas.itemconfigure(form_window, width=event.width)

        form.bind("<Configure>", update_scroll_region)
        form_canvas.bind("<Configure>", fit_form_width)
        form_canvas.bind(
            "<MouseWheel>",
            lambda event: form_canvas.yview_scroll(int(-event.delta / 120), "units"),
        )

        groups = (
            (
                "Persönliche Daten",
                (
                    (("Anrede / Titel", "anrede"), ("Vorname *", "vorname")),
                    (("Nachname *", "nachname"),),
                ),
            ),
            (
                "Versicherung",
                (
                    (("Versicherungsnummer", "versicherungsnummer"), ("Krankenkasse", "krankenkasse")),
                ),
            ),
            (
                "Adresse",
                (
                    (("Straße", "strasse"), ("Hausnummer", "hausnummer")),
                    (("Adresszusatz", "adresszusatz"),),
                    (("PLZ", "plz"), ("Ort", "ort")),
                ),
            ),
            (
                "Praxisdaten",
                (
                    (("Diagnose", "diagnose"), ("Kilometergeld (€)", "kilometergeld")),
                ),
            ),
        )
        for group_title, rows in groups:
            group = ttk.LabelFrame(form, text=group_title, padding=10)
            group.pack(fill="x", pady=(0, 10))
            for column in (1, 3):
                group.columnconfigure(column, weight=1)
            for row, field_row in enumerate(rows):
                for pair_index, (label, key) in enumerate(field_row):
                    column = pair_index * 2
                    ttk.Label(group, text=label).grid(
                        row=row,
                        column=column,
                        sticky="w",
                        padx=(0, 8),
                        pady=5,
                    )
                    ttk.Entry(
                        group,
                        textvariable=self.fields[key],
                        style="Patient.TEntry",
                    ).grid(
                        row=row,
                        column=column + 1,
                        sticky="ew",
                        padx=(0, 12 if pair_index == 0 and len(field_row) > 1 else 0),
                        pady=5,
                    )

        ttk.Label(
            content,
            text="Nach dem Speichern ordnen Sie dem Patienten eine Stammdaten-Leistung zu.",
            wraplength=620,
        ).pack(anchor="w", pady=(10, 4))
        buttons = ttk.Frame(content)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Patient speichern", command=self._save).pack(side="right")

    def _save(self):
        data = {key: value.get().strip() for key, value in self.fields.items()}
        if not data["vorname"] or not data["nachname"]:
            messagebox.showwarning(
                "Patientendaten",
                "Bitte Vor- und Nachname eintragen.",
                parent=self,
            )
            return
        try:
            kilometergeld = float(data["kilometergeld"].replace(",", ".") or "0")
            if kilometergeld < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Patientendaten",
                "Kilometergeld muss eine Zahl größer oder gleich 0 sein.",
                parent=self,
            )
            return

        moved_folder = None
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = None
                if data["versicherungsnummer"]:
                    existing = connection.execute(
                        """
                        SELECT id, is_archived, vorname, nachname
                        FROM patienten
                        WHERE versicherungsnummer = ?
                        ORDER BY CASE WHEN COALESCE(is_archived, 0) = 0 THEN 0 ELSE 1 END, id
                        LIMIT 1
                        """,
                        (data["versicherungsnummer"],),
                    ).fetchone()
                if not existing:
                    existing = connection.execute(
                        """
                        SELECT id, is_archived, vorname, nachname
                        FROM patienten
                        WHERE vorname = ? COLLATE NOCASE
                          AND nachname = ? COLLATE NOCASE
                          AND COALESCE(plz, '') = ? COLLATE NOCASE
                        ORDER BY CASE WHEN COALESCE(is_archived, 0) = 0 THEN 0 ELSE 1 END, id
                        LIMIT 1
                        """,
                        (data["vorname"], data["nachname"], data["plz"]),
                    ).fetchone()

                if existing:
                    patient_id, archived, existing_first_name, existing_last_name = existing
                    if not archived:
                        messagebox.showwarning(
                            "Patient bereits vorhanden",
                            "Ein aktiver Patient mit dieser Versicherungsnummer bzw. "
                            "diesem Namen und dieser PLZ existiert bereits.",
                            parent=self,
                        )
                        return
                    if not messagebox.askyesno(
                        "Archivierten Patienten reaktivieren",
                        "Dieser Patient ist bereits archiviert. Soll der vorhandene "
                        "Patient reaktiviert werden?",
                        parent=self,
                    ):
                        return
                    moved_folder = _move_archived_patient_folder(
                        {
                            "vorname": existing_first_name,
                            "nachname": existing_last_name,
                            "is_archived": 1,
                        }
                    )
                    connection.execute(
                        "UPDATE patienten SET is_archived = 0 WHERE id = ?",
                        (patient_id,),
                    )
                    is_new = False
                else:
                    cursor = connection.execute(
                        """
                        INSERT INTO patienten (
                            anrede, vorname, nachname, versicherungsnummer,
                            krankenkasse, diagnose, strasse, hausnummer,
                            adresszusatz, plz, ort, kilometergeld,
                            last_selected_kurznamen, is_archived
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0)
                        """,
                        (
                            data["anrede"],
                            data["vorname"],
                            data["nachname"],
                            data["versicherungsnummer"],
                            data["krankenkasse"],
                            data["diagnose"],
                            data["strasse"],
                            data["hausnummer"],
                            data["adresszusatz"],
                            data["plz"],
                            data["ort"],
                            kilometergeld,
                        ),
                    )
                    patient_id = cursor.lastrowid
                    is_new = True

                connection.row_factory = sqlite3.Row
                patient = dict(
                    connection.execute(
                        "SELECT * FROM patienten WHERE id = ?",
                        (patient_id,),
                    ).fetchone()
                )
        except sqlite3.IntegrityError as error:
            try:
                _restore_moved_patient_folder(moved_folder)
            except OSError:
                logging.exception("Archivordner konnte nach Datenbankfehler nicht wiederhergestellt werden.")
            messagebox.showerror(
                "Patientendaten",
                f"Der Patient konnte wegen eines doppelten Datenbankeintrags nicht angelegt werden:\n{error}",
                parent=self,
            )
            return
        except sqlite3.Error as error:
            try:
                _restore_moved_patient_folder(moved_folder)
            except OSError:
                logging.exception("Archivordner konnte nach Datenbankfehler nicht wiederhergestellt werden.")
            logging.exception("Patient konnte nicht angelegt werden.")
            messagebox.showerror(
                "Patientendaten",
                f"Patient konnte nicht gespeichert werden:\n{error}",
                parent=self,
            )
            return
        except (OSError, ValueError) as error:
            try:
                _restore_moved_patient_folder(moved_folder)
            except OSError:
                logging.exception("Archivordner konnte nach Fehler nicht wiederhergestellt werden.")
            messagebox.showerror(
                "Archivierter Patient",
                f"Der Patient konnte nicht aus dem Archiv übernommen werden:\n{error}",
                parent=self,
            )
            return

        self.destroy()
        self.on_created(patient, is_new)


class StammdatenAssignmentWindow(tk.Toplevel):
    def __init__(
        self,
        parent,
        database_path,
        patients,
        on_complete,
        allow_cancel=True,
    ):
        super().__init__(parent)
        self.database_path = database_path
        self.patients = patients
        self.on_complete = on_complete
        self.allow_cancel = allow_cancel
        self.current_index = 0
        self.service_rows = []
        self.completed = False

        self.title("Stammdaten-Leistung zuordnen")
        self.geometry("760x700")
        self.minsize(650, 600)
        ttk.Style(self).configure("Assignment.TEntry", font=("Segoe UI", 12))
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        content = ttk.Frame(self, padding=16)
        content.pack(fill="both", expand=True)
        ttk.Label(
            content,
            text="Stammdaten-Leistung zuordnen",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        self.patient_label = ttk.Label(content, font=("Segoe UI", 13, "bold"))
        self.patient_label.pack(anchor="w", pady=(10, 2))
        self.patient_details = ttk.Label(content, wraplength=700, justify="left")
        self.patient_details.pack(anchor="w")
        self.progress_label = ttk.Label(content)
        self.progress_label.pack(anchor="w", pady=(4, 8))

        form = ttk.LabelFrame(
            content,
            text="Vorhandene Leistung auswählen oder neue erstellen",
            padding=10,
        )
        form.pack(fill="x", pady=(0, 8))
        form.columnconfigure(1, weight=1)
        ttk.Style(self).configure("Assignment.TEntry", font=("Segoe UI", 12))
        ttk.Label(form, text="Kurzname").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, style="Assignment.TEntry").grid(
            row=0, column=1, sticky="ew", pady=5
        )
        ttk.Label(form, text="Standardbetrag (€)").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=5
        )
        self.amount_var = tk.StringVar()
        amount_controls = ttk.Frame(form)
        amount_controls.grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Entry(
            amount_controls,
            textvariable=self.amount_var,
            style="Assignment.TEntry",
            width=12,
        ).pack(side="left", padx=(0, 8))

        quick_amounts_text = CONFIG.get("QUICK_AMOUNTS", "33, 35, 57, 83")
        try:
            quick_amounts = [
                float(value.strip())
                for value in quick_amounts_text.split(",")
                if value.strip()
            ]
        except (ValueError, AttributeError):
            quick_amounts = [33, 35, 57, 83]

        for value in quick_amounts:
            label = f"€{int(value)}" if value.is_integer() else f"€{value:g}"
            ttk.Button(
                amount_controls,
                text=label,
                width=6,
                command=lambda amount=value: self.amount_var.set(f"{amount:.2f}"),
            ).pack(side="left", padx=2)
        ttk.Label(form, text="Beschreibung für Honorarnote").grid(
            row=2, column=0, sticky="nw", padx=(0, 10), pady=5
        )
        self.description_text = tk.Text(form, height=4, font=("Segoe UI", 12), wrap="word")
        self.description_text.grid(row=2, column=1, sticky="ew", pady=5)
        self.status_label = ttk.Label(form, text="")
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="w")

        list_frame = ttk.LabelFrame(content, text="Aktive Stammdaten-Leistungen", padding=8)
        list_frame.pack(fill="both", expand=True)
        self.service_list = tk.Listbox(list_frame, font=("Segoe UI", 12), height=10)
        self.service_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, command=self.service_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.service_list.configure(yscrollcommand=scrollbar.set)
        self.service_list.bind("<<ListboxSelect>>", self._select_service)

        buttons = ttk.Frame(content)
        buttons.pack(fill="x", pady=(10, 0))
        if allow_cancel:
            ttk.Button(buttons, text="Abbrechen", command=self._cancel).pack(side="left")
        ttk.Button(buttons, text="Felder leeren", command=self._clear_fields).pack(side="left", padx=8)
        self.next_button = ttk.Button(buttons, command=self._save_current)
        self.next_button.pack(side="right")

        self._refresh_services()
        self._show_patient()

    def _refresh_services(self):
        try:
            with sqlite3.connect(self.database_path) as connection:
                self.service_rows = connection.execute(
                    """
                    SELECT kurzname, beschreibung, standard_betrag
                    FROM stammdaten_leistungen
                    WHERE COALESCE(is_archived, 0) = 0
                    ORDER BY kurzname
                    """
                ).fetchall()
        except sqlite3.Error as error:
            logging.exception("Stammdaten-Leistungen konnten nicht geladen werden.")
            messagebox.showerror(
                "Stammdaten-Leistungen",
                f"Leistungen konnten nicht geladen werden:\n{error}",
                parent=self,
            )
            return

        self.service_list.delete(0, tk.END)
        for name, description, amount in self.service_rows:
            self.service_list.insert(
                tk.END,
                f"{name} — {description} (Standard: {amount:.2f} €)",
            )

    def _show_patient(self):
        patient = self.patients[self.current_index]
        name = patient.get("name") or (
            f"{patient.get('anrede') or ''} {patient.get('vorname') or ''} "
            f"{patient.get('nachname') or ''}"
        ).strip()
        address = patient.get("adresse") or " ".join(
            part
            for part in (
                patient.get("strasse"),
                patient.get("hausnummer"),
                patient.get("adresszusatz"),
            )
            if part
        )
        city = patient.get("ort") or " ".join(
            part for part in (patient.get("plz"), patient.get("ort")) if part
        )
        vsnr = patient.get("vsnr") or patient.get("versicherungsnummer") or "—"
        self.patient_label.configure(text=name or "Patient")
        self.patient_details.configure(
            text=f"Versicherungsnummer: {vsnr} | Adresse: {address or '—'}, {city or '—'}"
        )
        self.progress_label.configure(
            text=f"Patient {self.current_index + 1} von {len(self.patients)}"
        )
        self.next_button.configure(
            text="Fertig" if self.current_index == len(self.patients) - 1 else "Weiter"
        )
        self._clear_fields()

    def _select_service(self, _event=None):
        selection = self.service_list.curselection()
        if not selection:
            return
        name, description, amount = self.service_rows[selection[0]]
        self.name_var.set(name)
        self.amount_var.set(f"{amount:.2f}")
        self.description_text.delete("1.0", tk.END)
        self.description_text.insert("1.0", description)
        self.status_label.configure(text="Vorhandene Leistung ausgewählt.")

    def _clear_fields(self):
        self.name_var.set("")
        self.amount_var.set("")
        self.description_text.delete("1.0", tk.END)
        self.service_list.selection_clear(0, tk.END)
        self.status_label.configure(text="")

    def _save_current(self):
        name = self.name_var.get().strip()
        amount_text = self.amount_var.get().strip().replace(",", ".")
        description = self.description_text.get("1.0", "end-1c").strip()
        if not name or "," in name or not amount_text or not description:
            messagebox.showwarning(
                "Stammdaten-Leistung",
                "Bitte Kurzname (ohne Komma), Standardbetrag und Beschreibung angeben.",
                parent=self,
            )
            return
        try:
            amount = float(amount_text)
            if amount < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Stammdaten-Leistung",
                "Der Standardbetrag muss eine Zahl größer oder gleich 0 sein.",
                parent=self,
            )
            return

        patient = self.patients[self.current_index]
        patient_id = patient.get("db_id") or patient.get("id")
        if not patient_id:
            messagebox.showerror(
                "Patient nicht gefunden",
                "Für diesen Import wurde keine Patienten-ID zurückgegeben.",
                parent=self,
            )
            return

        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO stammdaten_leistungen
                        (kurzname, beschreibung, standard_betrag, is_archived)
                    VALUES (?, ?, ?, 0)
                    ON CONFLICT(kurzname) DO UPDATE SET
                        beschreibung = excluded.beschreibung,
                        standard_betrag = excluded.standard_betrag,
                        is_archived = 0
                    """,
                    (name, description, amount),
                )
                cursor = connection.execute(
                    "UPDATE patienten SET last_selected_kurznamen = ? WHERE id = ?",
                    (name, patient_id),
                )
                if cursor.rowcount != 1:
                    raise sqlite3.DatabaseError(
                        f"Patient {patient_id} wurde beim Speichern nicht gefunden."
                    )
        except sqlite3.Error as error:
            logging.exception("Stammdaten-Leistung konnte nicht gespeichert werden.")
            messagebox.showerror(
                "Speichern fehlgeschlagen",
                f"Stammdaten-Leistung konnte nicht gespeichert werden:\n{error}",
                parent=self,
            )
            return

        if self.current_index == len(self.patients) - 1:
            self._finish(True)
        else:
            self.current_index += 1
            self._refresh_services()
            self._show_patient()

    def _cancel(self):
        if not self.allow_cancel:
            return
        if messagebox.askyesno(
            "Zuordnung abbrechen",
            "Die Stammdaten-Zuordnung abbrechen? Der Companion-Sync wird dann nicht bestätigt.",
            parent=self,
        ):
            self._finish(False)

    def _finish(self, success):
        if self.completed:
            return
        self.completed = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self.on_complete(success)
