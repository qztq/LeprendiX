import datetime
import os
import sqlite3
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from config_loader import CONFIG


BACKGROUND = "#2c3e50"
PANEL = "#34495e"
PANEL_ALT = "#3d566e"
ACCENT = "#27ae60"
TEXT = "#ecf0f1"
MUTED = "#aebac5"


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

        self.title("LeprendiX - Patientenakten")
        self.geometry("1000x700")
        self.minsize(800, 500)
        self.configure(bg=BACKGROUND)

        self._configure_styles()
        self._build_window()
        self._load_patients()

    def _configure_styles(self):
        style = ttk.Style(self)
        style.configure(
            "Records.Treeview",
            background=BACKGROUND,
            fieldbackground=BACKGROUND,
            foreground=TEXT,
            rowheight=32,
            borderwidth=0,
            font=("Segoe UI", 11),
        )
        style.configure(
            "Records.Treeview.Heading",
            background=PANEL,
            foreground=TEXT,
            font=("Segoe UI", 11, "bold"),
        )
        style.map(
            "Records.Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", TEXT)],
        )

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
            font=("Segoe UI", 17, "bold"),
            fg=TEXT,
            bg=BACKGROUND,
        ).pack(side="left")
        tk.Label(
            header,
            text="Aktive und archivierte Patienten",
            font=("Segoe UI", 11),
            fg=TEXT,
            bg=BACKGROUND,
        ).pack(side="right", padx=4)

        search_frame = tk.Frame(self, bg=BACKGROUND)
        search_frame.pack(fill="x", padx=18, pady=(4, 10))
        tk.Label(
            search_frame,
            text="Patient suchen:",
            font=("Segoe UI", 11, "bold"),
            fg=TEXT,
            bg=BACKGROUND,
        ).pack(side="left", padx=(0, 10))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 12),
        )
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=7)
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
            font=("Segoe UI", 10),
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
        "last_selected_kurznamen": "Zuletzt gewählte Leistungen",
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
        self.service_tree = None
        self.invoice_tree = None

        first_name = patient.get("vorname") or ""
        last_name = patient.get("nachname") or ""
        status = " [ARCHIVIERT]" if patient.get("is_archived", 0) else ""
        self.title(f"Patientenakte - {last_name} {first_name}{status}")
        self.geometry("1200x820")
        self.minsize(1000, 650)
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
            font=("Segoe UI", 17, "bold"),
            fg=TEXT,
            bg=PANEL,
        ).pack(side="left")
        if patient.get("is_archived", 0):
            tk.Label(
                header,
                text="ARCHIVIERT",
                font=("Segoe UI", 11, "bold"),
                fg=MUTED,
                bg=PANEL,
            ).pack(side="right")

        self._build_patient_details()
        self._build_activity_lists()
        self._load_services()
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
                font=("Segoe UI", 11, "bold"),
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
                font=("Segoe UI", 11, "bold"),
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
            font=("Segoe UI", 10, "bold"),
            fg="#d5dde5",
            bg=PANEL,
            anchor="w",
        ).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=3)
        tk.Label(
            parent,
            text=display_value,
            font=("Segoe UI", 11),
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

        services_frame = self._create_list_panel(
            activity_frame,
            title="Leistungen",
            columns=("datum", "von", "bis", "beschreibung", "betrag"),
            headings=("Datum", "Von", "Bis", "Beschreibung", "Betrag"),
        )
        services_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.service_tree = services_frame.tree

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

        self.service_tree.column("datum", width=95, anchor="center")
        self.service_tree.column("von", width=60, anchor="center")
        self.service_tree.column("bis", width=60, anchor="center")
        self.service_tree.column("beschreibung", width=240)
        self.service_tree.column("betrag", width=90, anchor="e")
        self.invoice_tree.column("datum", width=145, anchor="center")
        self.invoice_tree.column("datei", width=300)

        ttk.Button(
            invoices_frame,
            text="Honorarnote öffnen",
            command=self._open_selected_invoice,
        ).pack(anchor="e", padx=8, pady=(0, 8))

    def _create_list_panel(self, parent, title, columns, headings):
        panel = tk.LabelFrame(
            parent,
            text=title,
            font=("Segoe UI", 12, "bold"),
            fg=TEXT,
            bg=PANEL,
            padx=6,
            pady=6,
            labelanchor="nw",
        )
        tree = ttk.Treeview(
            panel,
            style="Records.Treeview",
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
        tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=4)
        tree.configure(yscrollcommand=scrollbar.set)
        panel.tree = tree
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

    def _load_services(self):
        try:
            with sqlite3.connect(self.database_path) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag
                    FROM leistungen
                    WHERE patient_id = ?
                    ORDER BY datum DESC, uhrzeit_von DESC, id DESC
                    """,
                    (self.patient["id"],),
                )
                rows = cursor.fetchall()
        except sqlite3.Error as error:
            messagebox.showerror(
                "Patientenakte",
                f"Leistungen konnten nicht geladen werden:\n{error}",
                parent=self,
            )
            return

        for datum, time_from, time_to, description, amount in rows:
            self.service_tree.insert(
                "",
                tk.END,
                values=(
                    self._format_date(datum),
                    time_from or "",
                    time_to or "",
                    description or "",
                    f"{amount:.2f} €" if amount is not None else "",
                ),
            )

    def _patient_folder(self):
        folder_name = f"{self.patient.get('nachname') or ''} {self.patient.get('vorname') or ''}".strip()
        preferred_dir = (
            _configured_path("ARCHIVE_DIR", "")
            if self.patient.get("is_archived", 0)
            else _configured_path("PATIENT_BASE_DIR", "")
        )
        other_dir = (
            _configured_path("PATIENT_BASE_DIR", "")
            if self.patient.get("is_archived", 0)
            else _configured_path("ARCHIVE_DIR", "")
        )
        for base_dir in (preferred_dir, other_dir):
            folder = os.path.join(base_dir, folder_name) if base_dir else ""
            if folder and os.path.isdir(folder):
                return folder
        return ""

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
            return datetime.datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError:
            return str(value)
