import datetime
import json
import logging
import math
import os
import pickle
import runpy
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from src.project_paths import get_app_directory, get_resource_path

BASE_DIR = get_app_directory()
os.chdir(BASE_DIR)


def resource_path(relative_path):
    return get_resource_path(relative_path)


from src.config_loader import CONFIG
from src import crash_handler, gui_generator, patient_records, setup_wizard
from src.companion_contracts import get_contract_directory, read_contract_files, save_contract_files
from src.material_orders import validate_material_order_template

COLOR_PRIMARY = "#17212b"
COLOR_SECONDARY = "#22313f"
COLOR_ACCENT = "#28a879"
COLOR_TEXT = "#f3f6f8"
COLOR_MUTED = "#aab7c4"
COLOR_HIGHLIGHT = "#3498db"
COLOR_CARD = "#1c2a36"
LOGO_PATH = resource_path(os.path.join("assets", "logo.png"))


def setup_logging():
    if sys.platform == "win32":
        base_path = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
    else:
        base_path = os.path.join(os.path.expanduser("~"), ".local", "share")

    log_dir = os.path.join(base_path, "LeprendiX", "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "leprendix.log")
    except OSError:
        log_file = os.path.join(tempfile.gettempdir(), "leprendix.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("=== LeprendiX gestartet (Log: %s) ===", log_file)


def load_credentials():
    cred_path = os.path.join(BASE_DIR, "credentials.dat")
    if os.path.exists(cred_path):
        try:
            with open(cred_path, "rb") as credentials_file:
                return pickle.load(credentials_file)
        except Exception as error:
            logging.error("Login-Daten konnten nicht geladen werden: %s", error)
            return None
    return None


USER_CREDS = load_credentials()


class LoginSplash(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.running = True
        self.overrideredirect(True)
        self.configure(bg="#0a0a0a")

        width, height = 550, 400
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-topmost", True)

        self.canvas = tk.Canvas(
            self, width=width, height=height, bg="#0a0a0a", highlightthickness=0
        )
        self.canvas.pack()
        self.canvas.create_text(
            width / 2 - 30,
            height / 2 - 20,
            text="Leprendi",
            font=("Segoe UI", 45, "bold"),
            fill="#f8f9fa",
        )
        self.canvas.create_text(
            width / 2,
            height - 40,
            text="Anwendung wird gestartet...",
            font=("Segoe UI", 12, "italic"),
            fill="#555555",
        )

        center_x, center_y = width / 2 + 130, height / 2 - 20
        size = 35
        self.canvas.create_line(
            center_x - size,
            center_y - size,
            center_x + size,
            center_y + size,
            fill="#1a1a1a",
            width=15,
            capstyle="round",
        )
        self.canvas.create_line(
            center_x + size,
            center_y - size,
            center_x - size,
            center_y + size,
            fill="#1a1a1a",
            width=15,
            capstyle="round",
        )

        self.points = [
            (center_x - size, center_y - size),
            (center_x + size, center_y + size),
            (center_x + size, center_y - size),
            (center_x - size, center_y + size),
        ]
        self.dot = self.canvas.create_oval(
            0, 0, 0, 0, fill="#00f2ff", outline="#70f3ff", width=2
        )
        self.trail_length = 12
        self.trail_dots = [
            self.canvas.create_oval(0, 0, 0, 0, fill="#004d4d", outline="")
            for _ in range(self.trail_length)
        ]
        self.history = []
        self.start_time = time.time()
        self.animate()

    def animate(self):
        if not self.running or not self.winfo_exists():
            return
        try:
            elapsed = time.time() - self.start_time
            speed = (math.sin(elapsed * 0.7) + 1.1) * 0.5
            position = (elapsed * speed) % 2.0
            point_a, point_b = (
                (self.points[0], self.points[1])
                if position < 1.0
                else (self.points[2], self.points[3])
            )
            fraction = position if position < 1.0 else position - 1.0
            current_x = point_a[0] + (point_b[0] - point_a[0]) * fraction
            current_y = point_a[1] + (point_b[1] - point_a[1]) * fraction

            self.history.insert(0, (current_x, current_y))
            if len(self.history) > self.trail_length + 1:
                self.history.pop()
            for index, dot_id in enumerate(self.trail_dots):
                if index < len(self.history):
                    history_x, history_y = self.history[index]
                    radius = (self.trail_length - index) * 0.6
                    self.canvas.coords(
                        dot_id,
                        history_x - radius,
                        history_y - radius,
                        history_x + radius,
                        history_y + radius,
                    )

            radius = 5 + math.sin(elapsed * 5) * 1.2
            self.canvas.coords(
                self.dot,
                current_x - radius,
                current_y - radius,
                current_x + radius,
                current_y + radius,
            )
            self.after(30, self.animate)
        except (tk.TclError, AttributeError):
            self.running = False

    def stop(self):
        self.running = False
        self.destroy()


def launch_application(root):
    root.withdraw()
    splash = LoginSplash(root)

    def finalize_start():
        splash.stop()
        gen_root = tk.Tk()
        gui_generator.HonorarGeneratorApp(gen_root)
        gen_root.mainloop()
        root.destroy()

    root.after(2000, finalize_start)
    root.mainloop()


def get_version():
    try:
        with open(os.path.join(BASE_DIR, "version.txt"), "r", encoding="utf-8") as version_file:
            return version_file.read().strip()
    except OSError:
        logging.exception("Versionsdatei konnte nicht gelesen werden.")
        return "Dev-Version"


def create_main():
    setup_logging()
    crash_handler.install_exception_handler()
    if hasattr(threading, "excepthook"):
        threading.excepthook = lambda args: crash_handler.global_exception_handler(
            args.exc_type, args.exc_value, args.exc_traceback
        )

    root = tk.Tk()
    root.report_callback_exception = crash_handler.global_exception_handler
    root.withdraw()
    setup_wizard.check_and_run_setup(root)

    global USER_CREDS
    USER_CREDS = load_credentials()

    version = get_version()
    root.title("LeprendiX | Control Center")
    root.geometry("1120x820")
    root.minsize(900, 680)
    root.configure(bg=COLOR_PRIMARY)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "TNotebook",
        background=COLOR_PRIMARY,
        borderwidth=0,
        bordercolor=COLOR_PRIMARY,
        relief="flat",
        lightcolor=COLOR_PRIMARY,
        darkcolor=COLOR_PRIMARY,
        focuscolor=COLOR_PRIMARY,
        tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=COLOR_SECONDARY,
        foreground=COLOR_MUTED,
        padding=(24, 12),
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
        bordercolor=COLOR_SECONDARY,
        relief="flat",
        focuscolor=COLOR_SECONDARY,
        focusthickness=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_CARD), ("!selected", COLOR_SECONDARY)],
        foreground=[("selected", COLOR_TEXT)],
        padding=[("selected", (24, 12)), ("!selected", (24, 12))],
        focuscolor=[("focus", COLOR_SECONDARY)],
        bordercolor=[("selected", COLOR_CARD), ("!selected", COLOR_SECONDARY)],
        lightcolor=[("selected", COLOR_CARD), ("!selected", COLOR_SECONDARY)],
        darkcolor=[("selected", COLOR_CARD), ("!selected", COLOR_SECONDARY)],
    )
    style.configure(
        "LeprendiX.Vertical.TScrollbar",
        background=COLOR_SECONDARY,
        troughcolor=COLOR_PRIMARY,
        bordercolor=COLOR_PRIMARY,
        arrowcolor=COLOR_TEXT,
    )

    header = tk.Frame(root, bg=COLOR_PRIMARY)
    header.pack(fill="x", padx=34, pady=(22, 14))
    tk.Label(
        header,
        text="LeprendiX",
        bg=COLOR_PRIMARY,
        fg=COLOR_TEXT,
        font=("Segoe UI", 21, "bold"),
    ).pack(side="left")
    tk.Label(
        header,
        text="CONTROL CENTER",
        bg=COLOR_PRIMARY,
        fg=COLOR_MUTED,
        font=("Segoe UI", 9, "bold"),
    ).pack(side="left", padx=(14, 0), pady=(8, 0))
    tk.Label(
        header,
        text=f"VERSION  {version}",
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        font=("Segoe UI", 9, "bold"),
        padx=13,
        pady=7,
    ).pack(side="right")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=34, pady=(0, 28))

    overview = tk.Frame(notebook, bg=COLOR_PRIMARY)
    settings = tk.Frame(notebook, bg=COLOR_PRIMARY)
    notebook.add(overview, text="ÜBERSICHT")
    notebook.add(settings, text="EINSTELLUNGEN")

    overview_content = tk.Frame(overview, bg=COLOR_PRIMARY)
    overview_content.pack(expand=True, fill="both", padx=24, pady=25)

    brand = tk.Frame(overview_content, bg=COLOR_PRIMARY)
    brand.pack(pady=(4, 24))
    if os.path.exists(LOGO_PATH):
        try:
            image = Image.open(LOGO_PATH)
            image.thumbnail((380, 190), Image.Resampling.LANCZOS)
            logo_image = ImageTk.PhotoImage(image)
            logo = tk.Label(brand, image=logo_image, bg=COLOR_PRIMARY)
            logo.image = logo_image
            logo.pack()
        except (OSError, tk.TclError):
            logging.exception("LeprendiX-Logo konnte nicht geladen werden.")
            tk.Label(
                brand,
                text="LeprendiX",
                bg=COLOR_PRIMARY,
                fg=COLOR_TEXT,
                font=("Segoe UI", 34, "bold"),
            ).pack()
    else:
        tk.Label(
            brand,
            text="LeprendiX",
            bg=COLOR_PRIMARY,
            fg=COLOR_TEXT,
            font=("Segoe UI", 34, "bold"),
        ).pack()

    login_card = tk.Frame(
        overview_content,
        bg=COLOR_CARD,
        padx=38,
        pady=30,
        highlightbackground="#344654",
        highlightthickness=1,
    )
    login_card.pack()
    tk.Label(
        login_card,
        text="Willkommen bei LeprendiX!",
        font=("Segoe UI", 16, "bold"),
        fg=COLOR_TEXT,
        bg=COLOR_CARD,
    ).pack(pady=(0, 5))
    tk.Label(
        login_card,
        text="Melden Sie sich an, um fortzufahren.",
        font=("Segoe UI", 9),
        fg=COLOR_MUTED,
        bg=COLOR_CARD,
    ).pack(pady=(0, 21))

    input_style = {
        "bg": "#111a22",
        "fg": COLOR_TEXT,
        "insertbackground": COLOR_TEXT,
        "relief": "flat",
        "font": ("Segoe UI", 11),
        "highlightthickness": 1,
        "highlightbackground": "#344654",
        "highlightcolor": COLOR_HIGHLIGHT,
    }

    tk.Label(
        login_card,
        text="Benutzername",
        fg=COLOR_MUTED,
        bg=COLOR_CARD,
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor="w")
    username_entry = tk.Entry(login_card, width=34, **input_style)
    username_entry.pack(pady=(6, 14), ipady=9)
    default_user = "bhag"
    if USER_CREDS and USER_CREDS.get("user"):
        default_user = USER_CREDS["user"]
    username_entry.insert(0, default_user)

    tk.Label(
        login_card,
        text="Passwort",
        fg=COLOR_MUTED,
        bg=COLOR_CARD,
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor="w")
    password_entry = tk.Entry(login_card, show="*", width=34, **input_style)
    password_entry.pack(pady=(6, 20), ipady=9)

    def do_login(event=None):
        if not USER_CREDS:
            messagebox.showerror("Fehler", "Datei 'credentials.dat' fehlt.", parent=root)
            return
        if (
            username_entry.get() != USER_CREDS.get("user")
            or password_entry.get() != USER_CREDS.get("password")
        ):
            messagebox.showerror("Fehler", "Logindaten inkorrekt.", parent=root)
            return

        database_path = os.path.join(BASE_DIR, "patienten.db")
        database_ready = False
        if os.path.exists(database_path):
            try:
                with sqlite3.connect(database_path) as connection:
                    row = connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='patienten'"
                    ).fetchone()
                database_ready = row is not None
            except sqlite3.Error as error:
                messagebox.showerror(
                    "Datenbankfehler",
                    f"Die Datenbank konnte nicht geprüft werden:\n{error}",
                    parent=root,
                )
                return

        if not database_ready:
            if not messagebox.askyesno(
                "Datenbank Setup",
                "Die Datenbank wurde noch nicht eingerichtet.\n"
                "Möchten Sie die Datenbank jetzt erstellen?",
                parent=root,
            ):
                return
            try:
                setup_script = resource_path(os.path.join("src", "db_setup.py"))
                runpy.run_path(setup_script, run_name="__main__")
                messagebox.showinfo(
                    "Erfolg", "Datenbank wurde erfolgreich erstellt.", parent=root
                )
            except Exception as error:
                logging.exception("Datenbank-Setup fehlgeschlagen.")
                messagebox.showerror(
                    "Fehler", f"Setup fehlgeschlagen:\n{error}", parent=root
                )
                return

        launch_application(root)

    def open_patient_records_from_launcher():
        if not USER_CREDS:
            messagebox.showerror(
                "Fehler", "Datei 'credentials.dat' fehlt.", parent=root
            )
            return
        if (
            username_entry.get() != USER_CREDS.get("user")
            or password_entry.get() != USER_CREDS.get("password")
        ):
            messagebox.showerror(
                "Anmeldung erforderlich",
                "Bitte zuerst gültige Logindaten eingeben.",
                parent=root,
            )
            return
        patient_records.open_patient_records(root)

    tk.Button(
        login_card,
        text="ANMELDEN & STARTEN",
        bg=COLOR_ACCENT,
        fg="white",
        activebackground="#23956b",
        activeforeground="white",
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        cursor="hand2",
        padx=20,
        pady=12,
        command=do_login,
    ).pack(fill="x")
    tk.Button(
        login_card,
        text="MATERIALBESTELLUNGEN / PATIENTENAKTEN",
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        activebackground="#2d4050",
        activeforeground="white",
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        cursor="hand2",
        padx=16,
        pady=11,
        command=open_patient_records_from_launcher,
    ).pack(fill="x", pady=(9, 0))
    root.bind("<Return>", do_login)

    settings_canvas = tk.Canvas(
        settings, bg=COLOR_PRIMARY, highlightthickness=0, borderwidth=0
    )
    settings_scrollbar = ttk.Scrollbar(
        settings,
        orient="vertical",
        command=settings_canvas.yview,
        style="LeprendiX.Vertical.TScrollbar",
    )
    settings_content = tk.Frame(settings_canvas, bg=COLOR_PRIMARY)
    settings_window = settings_canvas.create_window(
        (0, 0), window=settings_content, anchor="nw"
    )
    settings_content.bind(
        "<Configure>",
        lambda _event: settings_canvas.configure(
            scrollregion=settings_canvas.bbox("all")
        ),
    )
    settings_canvas.bind(
        "<Configure>",
        lambda event: settings_canvas.itemconfigure(
            settings_window, width=event.width
        ),
    )
    settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
    settings_canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=14)
    settings_scrollbar.pack(side="right", fill="y", padx=(0, 14), pady=14)

    def scroll_settings(event):
        settings_canvas.yview_scroll(int(-event.delta / 120), "units")

    settings_canvas.bind("<Enter>", lambda _event: settings_canvas.bind_all("<MouseWheel>", scroll_settings))
    settings_canvas.bind("<Leave>", lambda _event: settings_canvas.unbind_all("<MouseWheel>"))

    def add_section(title, description):
        card = tk.Frame(
            settings_content,
            bg=COLOR_CARD,
            padx=22,
            pady=18,
            highlightbackground="#2d3e4c",
            highlightthickness=1,
        )
        card.pack(fill="x", pady=(0, 12))
        tk.Label(
            card,
            text=title,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            card,
            text=description,
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=800,
        ).pack(anchor="w", pady=(3, 14))
        body = tk.Frame(card, bg=COLOR_CARD)
        body.pack(fill="x")
        return body

    def add_config_entry(parent, label, key, variables, show=None):
        row = tk.Frame(parent, bg=COLOR_CARD)
        row.pack(fill="x", pady=5)
        tk.Label(
            row,
            text=label,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            font=("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).pack(side="left")
        variable = tk.StringVar(value=str(CONFIG.get(key, "")))
        variables[key] = variable
        tk.Entry(
            row,
            textvariable=variable,
            bg="#111a22",
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            relief="flat",
            show=show,
        ).pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 0))

    settings_vars = {}

    paths_section = add_section(
        "Datenbank & Speicherorte",
        "Datenbank einrichten und festlegen, wo aktive Patienten und Archive gespeichert werden.",
    )
    tk.Label(
        paths_section,
        text="Datenbank-Setup ist durch Ihr Admin-Passwort geschützt.",
        bg=COLOR_CARD,
        fg=COLOR_MUTED,
        font=("Segoe UI", 9),
    ).pack(anchor="w")
    setup_row = tk.Frame(paths_section, bg=COLOR_CARD)
    setup_row.pack(fill="x", pady=(8, 16))
    db_password = tk.Entry(
        setup_row,
        show="*",
        width=28,
        bg="#111a22",
        fg=COLOR_TEXT,
        insertbackground=COLOR_TEXT,
        relief="flat",
    )
    db_password.pack(side="left", ipady=7, padx=(0, 10))

    def do_database_setup():
        if not USER_CREDS or db_password.get() != USER_CREDS.get("password"):
            messagebox.showerror("Fehler", "Passwort falsch.", parent=root)
            return
        try:
            setup_script = resource_path(os.path.join("src", "db_setup.py"))
            runpy.run_path(setup_script, run_name="__main__")
            messagebox.showinfo("Erfolg", "Datenbank bereit.", parent=root)
        except Exception as error:
            logging.exception("Datenbank-Setup fehlgeschlagen.")
            messagebox.showerror(
                "Fehler", f"Setup fehlgeschlagen:\n{error}", parent=root
            )

    tk.Button(
        setup_row,
        text="Datenbank-Setup starten",
        command=do_database_setup,
        bg=COLOR_HIGHLIGHT,
        fg="white",
        activebackground="#287fc0",
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padx=15,
        pady=8,
    ).pack(side="left")

    def add_path_picker(label, key):
        row = tk.Frame(paths_section, bg=COLOR_CARD)
        row.pack(fill="x", pady=5)
        tk.Label(
            row,
            text=label,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            font=("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).pack(side="left")
        variable = tk.StringVar(value=str(CONFIG.get(key, "")))
        settings_vars[key] = variable
        tk.Entry(
            row,
            textvariable=variable,
            bg="#111a22",
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            relief="flat",
        ).pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 8))

        def choose_path():
            selected = filedialog.askdirectory(
                parent=root, initialdir=variable.get() or BASE_DIR
            )
            if selected:
                variable.set(selected)

        tk.Button(
            row,
            text="Durchsuchen",
            command=choose_path,
            bg=COLOR_SECONDARY,
            fg=COLOR_TEXT,
            relief="flat",
            padx=12,
            pady=7,
        ).pack(side="right")

    add_path_picker("Patienten-Ordner", "PATIENT_BASE_DIR")
    add_path_picker("Archiv-Ordner", "ARCHIVE_DIR")

    integrations = add_section(
        "Integrationen",
        "Zugangsdaten für den Teamup-Kalender.",
    )
    add_config_entry(integrations, "Teamup API Key", "TEAMUP_API_KEY", settings_vars, "*")
    add_config_entry(integrations, "Teamup Calendar ID", "TEAMUP_CALENDAR_ID", settings_vars)

    defaults = add_section(
        "Standardwerte & Tastenkürzel",
        "Voreinstellungen für neue Datensätze, Beträge, Aktionen und den Teamup-Zeitraum.",
    )
    add_config_entry(defaults, "Standard Diagnose", "DEFAULT_DIAGNOSE", settings_vars)
    add_config_entry(defaults, "Standard Anrede", "DEFAULT_ANREDE", settings_vars)
    add_config_entry(
        defaults, "Schnellwahl-Beträge (Komma-getrennt)", "QUICK_AMOUNTS", settings_vars
    )
    add_config_entry(defaults, "Fixe Adresse für KM-Berechnung", "FIXED_ADDRESS", settings_vars)
    add_config_entry(defaults, "Hotkey Hauptaktion", "HOTKEY_ENTER", settings_vars)
    add_config_entry(defaults, "Hotkey Tab-Wechsel", "HOTKEY_SWITCH_TAB", settings_vars)

    date_row = tk.Frame(defaults, bg=COLOR_CARD)
    date_row.pack(fill="x", pady=5)
    tk.Label(
        date_row,
        text="Datumsmodus für Teamup",
        bg=COLOR_CARD,
        fg=COLOR_TEXT,
        font=("Segoe UI", 9, "bold"),
        width=31,
        anchor="w",
    ).pack(side="left")
    date_mode = tk.StringVar(value=CONFIG.get("AUTO_DATE_SELECTOR", "Auto"))
    settings_vars["AUTO_DATE_SELECTOR"] = date_mode
    ttk.Combobox(
        date_row,
        textvariable=date_mode,
        values=("Auto", "Manual"),
        state="readonly",
        width=14,
    ).pack(side="left", padx=(8, 0), ipady=3)
    manual_dates = tk.Frame(defaults, bg=COLOR_CARD)
    manual_dates.pack(fill="x", pady=5)
    tk.Label(
        manual_dates,
        text="Manueller Zeitraum (YYYY-MM-DD)",
        bg=COLOR_CARD,
        fg=COLOR_TEXT,
        font=("Segoe UI", 9, "bold"),
        width=31,
        anchor="w",
    ).pack(side="left")
    manual_start = tk.StringVar(value=CONFIG.get("MANUAL_DATE_START", ""))
    manual_end = tk.StringVar(value=CONFIG.get("MANUAL_DATE_END", ""))
    settings_vars["MANUAL_DATE_START"] = manual_start
    settings_vars["MANUAL_DATE_END"] = manual_end
    tk.Entry(
        manual_dates,
        textvariable=manual_start,
        width=15,
        bg="#111a22",
        fg=COLOR_TEXT,
        insertbackground=COLOR_TEXT,
        relief="flat",
    ).pack(side="left", padx=(8, 5), ipady=7)
    tk.Label(manual_dates, text="bis", bg=COLOR_CARD, fg=COLOR_MUTED).pack(side="left")
    tk.Entry(
        manual_dates,
        textvariable=manual_end,
        width=15,
        bg="#111a22",
        fg=COLOR_TEXT,
        insertbackground=COLOR_TEXT,
        relief="flat",
    ).pack(side="left", padx=5, ipady=7)

    documents = add_section(
        "Dokumente & Companion",
        "Vertragsdateien für die Companion-App und das Druckformular für Materialbestellungen verwalten.",
    )
    contract_dir = get_contract_directory(CONFIG.get("COMPANION_CONTRACTS_DIR"))
    contract_files = []
    contract_status = tk.StringVar(
        value=f"Speicherort: {contract_dir}\nNoch keine neuen Dateien ausgewählt."
    )
    tk.Label(
        documents,
        text="Verträge (.json)",
        bg=COLOR_CARD,
        fg=COLOR_TEXT,
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w")
    tk.Label(
        documents,
        textvariable=contract_status,
        bg=COLOR_CARD,
        fg=COLOR_MUTED,
        font=("Segoe UI", 9),
        justify="left",
        anchor="w",
        wraplength=800,
    ).pack(fill="x", pady=(4, 8))

    def choose_contract_files():
        selected = filedialog.askopenfilenames(
            parent=root,
            title="Vertrags-JSON-Dateien auswählen",
            filetypes=(("JSON-Dateien", "*.json"),),
        )
        if not selected:
            return
        try:
            read_contract_files(selected)
        except (OSError, ValueError) as error:
            messagebox.showerror("Verträge", str(error), parent=root)
            return
        contract_files[:] = list(selected)
        filenames = "\n".join(os.path.basename(path) for path in contract_files)
        contract_status.set(f"Ausgewählt:\n{filenames}")

    tk.Button(
        documents,
        text="JSON-Verträge auswählen",
        command=choose_contract_files,
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        relief="flat",
        padx=13,
        pady=8,
    ).pack(anchor="w")

    tk.Frame(documents, bg="#344654", height=1).pack(fill="x", pady=16)
    tk.Label(
        documents,
        text="Druckformular für Materialbestellungen (PDF)",
        bg=COLOR_CARD,
        fg=COLOR_TEXT,
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w")
    template_var = tk.StringVar(value=CONFIG.get("MATERIAL_ORDER_TEMPLATE", ""))
    settings_vars["MATERIAL_ORDER_TEMPLATE"] = template_var
    template_row = tk.Frame(documents, bg=COLOR_CARD)
    template_row.pack(fill="x", pady=(7, 0))
    tk.Entry(
        template_row,
        textvariable=template_var,
        bg="#111a22",
        fg=COLOR_TEXT,
        insertbackground=COLOR_TEXT,
        relief="flat",
    ).pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))

    def choose_template():
        selected = filedialog.askopenfilename(
            parent=root,
            title="Druckformular-PDF auswählen",
            filetypes=(("PDF-Dateien", "*.pdf"),),
        )
        if not selected:
            return
        try:
            template_var.set(validate_material_order_template(selected))
        except (OSError, ValueError) as error:
            messagebox.showerror("Druckformular", str(error), parent=root)

    tk.Button(
        template_row,
        text="PDF auswählen",
        command=choose_template,
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        relief="flat",
        padx=13,
        pady=7,
    ).pack(side="right")

    maintenance = add_section(
        "Wartung & Backups",
        "Erstellen Sie regelmäßig Datenbank-Backups. Ein vorhandenes Backup kann hier wiederhergestellt werden.",
    )
    backup_list = tk.Listbox(
        maintenance,
        height=5,
        bg="#111a22",
        fg=COLOR_TEXT,
        selectbackground=COLOR_HIGHLIGHT,
        relief="flat",
        highlightthickness=0,
        font=("Segoe UI", 9),
    )
    backup_list.pack(fill="x", pady=(0, 10))

    def refresh_backups():
        backup_list.delete(0, tk.END)
        backup_dir = os.path.join(BASE_DIR, "backups")
        try:
            filenames = sorted(
                (filename for filename in os.listdir(backup_dir) if filename.endswith(".db")),
                reverse=True,
            )
        except FileNotFoundError:
            filenames = []
        except OSError as error:
            messagebox.showerror(
                "Backups", f"Backups konnten nicht geladen werden:\n{error}", parent=root
            )
            return
        for filename in filenames:
            backup_list.insert(tk.END, filename)

    def create_backup():
        database_path = os.path.join(BASE_DIR, "patienten.db")
        if not os.path.exists(database_path):
            messagebox.showerror("Fehler", "Datenbank nicht gefunden.", parent=root)
            return
        backup_dir = os.path.join(BASE_DIR, "backups")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"patienten_backup_{timestamp}.db")
        try:
            os.makedirs(backup_dir, exist_ok=True)
            shutil.copy2(database_path, backup_path)
            messagebox.showinfo(
                "Backup", f"Backup erfolgreich erstellt:\n{backup_path}", parent=root
            )
            refresh_backups()
        except OSError as error:
            messagebox.showerror(
                "Fehler", f"Backup fehlgeschlagen:\n{error}", parent=root
            )

    def restore_backup():
        selection = backup_list.curselection()
        if not selection:
            messagebox.showwarning(
                "Auswahl", "Bitte wählen Sie ein Backup aus der Liste.", parent=root
            )
            return
        filename = backup_list.get(selection[0])
        if not messagebox.askyesno(
            "Wiederherstellen",
            f"Die Datenbank wirklich auf '{filename}' zurücksetzen?\n\n"
            "Alle Änderungen seit diesem Backup gehen verloren.",
            parent=root,
        ):
            return
        backup_path = os.path.join(BASE_DIR, "backups", filename)
        database_path = os.path.join(BASE_DIR, "patienten.db")
        try:
            shutil.copy2(backup_path, database_path)
            messagebox.showinfo(
                "Erfolg", "Datenbank wurde erfolgreich wiederhergestellt.", parent=root
            )
        except OSError as error:
            messagebox.showerror(
                "Fehler", f"Wiederherstellung fehlgeschlagen:\n{error}", parent=root
            )

    backup_buttons = tk.Frame(maintenance, bg=COLOR_CARD)
    backup_buttons.pack(fill="x")
    tk.Button(
        backup_buttons,
        text="Backup erstellen",
        command=create_backup,
        bg=COLOR_ACCENT,
        fg="white",
        relief="flat",
        padx=14,
        pady=8,
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        backup_buttons,
        text="Ausgewähltes wiederherstellen",
        command=restore_backup,
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        relief="flat",
        padx=14,
        pady=8,
    ).pack(side="left")
    refresh_backups()

    support = add_section(
        "Support & Updates",
        f"LeprendiX Version {version}. Dokumentation und aktuelle Informationen finden Sie online.",
    )

    def open_url(url):
        try:
            webbrowser.open(url)
        except Exception as error:
            messagebox.showerror("Browser", f"Link konnte nicht geöffnet werden:\n{error}", parent=root)

    support_buttons = tk.Frame(support, bg=COLOR_CARD)
    support_buttons.pack(anchor="w")
    tk.Button(
        support_buttons,
        text="Online-Dokumentation",
        command=lambda: open_url("https://github.com/qztq/LeprendiX"),
        bg=COLOR_HIGHLIGHT,
        fg="white",
        relief="flat",
        padx=14,
        pady=8,
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        support_buttons,
        text="Support / Fehler melden",
        command=lambda: open_url("https://github.com/qztq/LeprendiX/issues"),
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        relief="flat",
        padx=14,
        pady=8,
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        support_buttons,
        text="Auf Updates prüfen",
        command=lambda: open_url("https://github.com/qztq/LeprendiX/releases"),
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        relief="flat",
        padx=14,
        pady=8,
    ).pack(side="left")

    save_row = tk.Frame(settings_content, bg=COLOR_PRIMARY)
    save_row.pack(fill="x", pady=(1, 16))

    def save_settings():
        updated_config = dict(CONFIG)
        for key, variable in settings_vars.items():
            updated_config[key] = variable.get().strip()
        template_path = updated_config.get("MATERIAL_ORDER_TEMPLATE", "")
        if template_path:
            try:
                updated_config["MATERIAL_ORDER_TEMPLATE"] = (
                    validate_material_order_template(template_path)
                )
            except (OSError, ValueError) as error:
                messagebox.showerror("Druckformular", str(error), parent=root)
                return
        else:
            updated_config.pop("MATERIAL_ORDER_TEMPLATE", None)

        try:
            if contract_files:
                destination = get_contract_directory(
                    updated_config.get("COMPANION_CONTRACTS_DIR")
                )
                save_contract_files(contract_files, destination)
                updated_config["COMPANION_CONTRACTS_DIR"] = str(destination)

            config_path = os.path.join(BASE_DIR, "config.json")
            with open(config_path, "w", encoding="utf-8") as config_file:
                json.dump(updated_config, config_file, ensure_ascii=False, indent=4)
            CONFIG.clear()
            CONFIG.update(updated_config)
            contract_files.clear()
            contract_status.set(
                f"Speicherort: {get_contract_directory(CONFIG.get('COMPANION_CONTRACTS_DIR'))}"
                "\nEinstellungen gespeichert."
            )
            messagebox.showinfo(
                "Gespeichert", "Einstellungen wurden gespeichert.", parent=root
            )
        except (OSError, ValueError) as error:
            logging.exception("Einstellungen konnten nicht gespeichert werden.")
            messagebox.showerror(
                "Speichern fehlgeschlagen",
                f"Einstellungen konnten nicht gespeichert werden:\n{error}",
                parent=root,
            )

    tk.Button(
        save_row,
        text="ÄNDERUNGEN SPEICHERN",
        command=save_settings,
        bg=COLOR_ACCENT,
        fg="white",
        activebackground="#23956b",
        relief="flat",
        font=("Segoe UI", 10, "bold"),
        padx=20,
        pady=11,
    ).pack(side="right")

    def open_app_dir():
        try:
            if sys.platform == "win32":
                os.startfile(BASE_DIR)
            else:
                subprocess.Popen(["xdg-open", BASE_DIR])
        except (OSError, AttributeError) as error:
            messagebox.showerror(
                "Ordner", f"Programmordner konnte nicht geöffnet werden:\n{error}", parent=root
            )

    def open_log_dir():
        if sys.platform == "win32":
            base_path = (
                os.getenv("LOCALAPPDATA")
                or os.getenv("APPDATA")
                or os.path.expanduser("~")
            )
        else:
            base_path = os.path.join(os.path.expanduser("~"), ".local", "share")
        log_dir = os.path.join(base_path, "LeprendiX", "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(log_dir)
            else:
                subprocess.Popen(["xdg-open", log_dir])
        except (OSError, AttributeError) as error:
            messagebox.showerror(
                "Logs", f"Log-Ordner konnte nicht geöffnet werden:\n{error}", parent=root
            )

    tools_row = tk.Frame(support, bg=COLOR_CARD)
    tools_row.pack(anchor="w", pady=(10, 0))
    tk.Button(
        tools_row,
        text="Programmordner öffnen",
        command=open_app_dir,
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        relief="flat",
        padx=14,
        pady=8,
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        tools_row,
        text="Log-Ordner öffnen",
        command=open_log_dir,
        bg=COLOR_SECONDARY,
        fg=COLOR_TEXT,
        relief="flat",
        padx=14,
        pady=8,
    ).pack(side="left")

    def on_closing():
        if messagebox.askyesno(
            "Backup",
            "Möchten Sie vor dem Beenden ein automatisches Backup erstellen?",
            parent=root,
        ):
            database_path = os.path.join(BASE_DIR, "patienten.db")
            if os.path.exists(database_path):
                try:
                    backup_dir = os.path.join(BASE_DIR, "backups")
                    os.makedirs(backup_dir, exist_ok=True)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = os.path.join(
                        backup_dir, f"autobackup_{timestamp}.db"
                    )
                    shutil.copy2(database_path, backup_path)
                    logging.info("Automatisches Backup erstellt: %s", backup_path)
                except OSError as error:
                    logging.exception("Automatisches Backup fehlgeschlagen.")
                    messagebox.showerror(
                        "Backup fehlgeschlagen", str(error), parent=root
                    )
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    if "--crash-handler" in sys.argv:
        crash_handler.main()
    else:
        create_main()
