import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import sys
import pickle
import qrcode
from PIL import ImageTk
from src.config_loader import CONFIG
from src.companion_contracts import (
    get_contract_directory,
    read_contract_files,
    save_contract_files,
)
from src.material_orders import validate_material_order_template
from src.project_paths import get_app_directory


COMPANION_APK_URL = (
    "https://github.com/qztq/LeprendiX/releases/latest/download/LeprendiX_Mobile.apk"
)

# Design-Konstanten (passend zu LeprendiX)
COLOR_PRIMARY = "#2c3e50"
COLOR_SECONDARY = "#34495e"
COLOR_ACCENT = "#27ae60"
COLOR_TEXT = "#ecf0f1"

class SetupWizard(tk.Toplevel):
    def __init__(self, parent, current_version):
        super().__init__(parent)
        self.title(f"LeprendiX Setup - Version {current_version}")
        self.geometry("700x600")
        self.configure(bg=COLOR_PRIMARY)
        # self.transient(parent) # Entfernt, da parent (root) ausgeblendet ist -> macht Wizard sonst unsichtbar
        self.grab_set()
        
        # Fenster zentrieren
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        # Kopie der Config zum Bearbeiten
        self.config_data = CONFIG.copy()
        self.base_path = get_app_directory()
        self.current_version = current_version
        self.current_step = 0
        self.selected_contract_files = []
        self.material_order_template = ""
        configured_template = self.config_data.get("MATERIAL_ORDER_TEMPLATE", "")
        if configured_template:
            if not os.path.isabs(configured_template):
                configured_template = os.path.join(self.base_path, configured_template)
            try:
                self.material_order_template = validate_material_order_template(
                    configured_template
                )
                self.config_data["MATERIAL_ORDER_TEMPLATE"] = (
                    self.material_order_template
                )
            except (OSError, ValueError):
                self.config_data.pop("MATERIAL_ORDER_TEMPLATE", None)
        self.download_companion_var = tk.BooleanVar(
            value=bool(self.config_data.get("DOWNLOAD_COMPANION_APP", False))
        )
        
        # Determine base path and check for credentials
        self.cred_file = os.path.join(self.base_path, "credentials.dat")
        self.needs_creds = not os.path.exists(self.cred_file)
        self.new_creds = {"user": "", "password": ""}
        
        self.steps = [
            self.create_welcome_step,
        ]
        
        if self.needs_creds:
            self.steps.append(self.create_credentials_step)
            
        self.steps.extend([
            self.create_paths_step,
            self.create_api_step,
            self.create_defaults_step,
            self.create_material_order_template_step,
            self.create_companion_step,
            self.create_finish_step
        ])
        
        # Header
        header = tk.Frame(self, bg=COLOR_SECONDARY, height=60)
        header.pack(fill="x")
        tk.Label(header, text="LeprendiX Config-Assistent", font=("Segoe UI", 14, "bold"), bg=COLOR_SECONDARY, fg="white").pack(pady=15)

        # Content Container
        self.container = tk.Frame(self, bg=COLOR_PRIMARY)
        self.container.pack(fill="both", expand=True, padx=40, pady=20)
        
        # Footer (Buttons)
        self.footer = tk.Frame(self, bg=COLOR_PRIMARY)
        self.footer.pack(fill="x", padx=40, pady=20)
        
        self.btn_back = tk.Button(self.footer, text="< Zurück", command=self.prev_step, bg=COLOR_SECONDARY, fg="white", relief="flat", font=("Segoe UI", 10), padx=20, pady=8)
        self.btn_back.pack(side="left")
        
        self.btn_next = tk.Button(self.footer, text="Weiter >", command=self.next_step, bg=COLOR_ACCENT, fg="white", relief="flat", font=("Segoe UI", 10, "bold"), padx=20, pady=8)
        self.btn_next.pack(side="right")
        
        self.show_step(0)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        if messagebox.askyesno("Setup abbrechen", "Möchten Sie das Setup wirklich abbrechen? Die bisherigen Einstellungen werden nicht gespeichert."):
            self.destroy()

    def show_step(self, index):
        for widget in self.container.winfo_children():
            widget.destroy()
            
        self.current_step = index
        self.steps[index]()
        
        # Buttons aktualisieren
        if index == 0:
            self.btn_back.config(state="disabled", bg="#555555")
            self.btn_next.config(text="Starten >", bg=COLOR_ACCENT, command=self.next_step)
        elif index == len(self.steps) - 1:
            self.btn_back.config(state="normal", bg=COLOR_SECONDARY)
            self.btn_next.config(text="Speichern & Starten", bg="#e67e22", command=self.finish)
        else:
            self.btn_back.config(state="normal", bg=COLOR_SECONDARY)
            self.btn_next.config(text="Weiter >", bg=COLOR_ACCENT, command=self.next_step)

    def next_step(self):
        if self.current_step < len(self.steps) - 1:
            self.show_step(self.current_step + 1)

    def prev_step(self):
        if self.current_step > 0:
            self.show_step(self.current_step - 1)

    def create_welcome_step(self):
        tk.Label(self.container, text="Willkommen!", font=("Segoe UI", 20, "bold"), bg=COLOR_PRIMARY, fg="white").pack(pady=(20, 10))
        
        msg = (f"Sie verwenden Version {self.current_version}.\n\n"
               "Da dies der erste Start nach einer Installation oder einem Update ist, "
               "überprüfen wir kurz Ihre Einstellungen.\n\n"
               "Bitte nehmen Sie sich einen Moment Zeit, um sicherzustellen, dass alle Pfade und Daten korrekt sind.")
        
        tk.Label(self.container, text=msg, font=("Segoe UI", 11), bg=COLOR_PRIMARY, fg=COLOR_TEXT, wraplength=550, justify="center").pack(pady=20)

    def create_credentials_step(self):
        tk.Label(self.container, text="Admin-Konto erstellen", font=("Segoe UI", 16, "bold"), bg=COLOR_PRIMARY, fg="white").pack(pady=(0, 20))
        tk.Label(self.container, text="Bitte legen Sie einen Benutzer und ein Passwort fest.", font=("Segoe UI", 10), bg=COLOR_PRIMARY, fg="#bdc3c7").pack(pady=(0, 20))
        
        # Auth Toggle
        self.auth_var = tk.BooleanVar(value=self.config_data.get("AUTH_ENABLED", False))
        cb = tk.Checkbutton(self.container, text="Passwortschutz aktivieren", variable=self.auth_var, 
                            bg=COLOR_PRIMARY, fg="white", selectcolor=COLOR_SECONDARY, activebackground=COLOR_PRIMARY, activeforeground="white",
                            command=lambda: self.config_data.update({"AUTH_ENABLED": self.auth_var.get()}))
        cb.pack(pady=(0, 20))
        
        self.add_cred_input("Benutzername:", "user")
        self.add_cred_input("Passwort:", "password", show="*")

    def add_cred_input(self, label, key, show=None):
        frame = tk.Frame(self.container, bg=COLOR_PRIMARY)
        frame.pack(fill="x", pady=8)
        tk.Label(frame, text=label, bg=COLOR_PRIMARY, fg=COLOR_TEXT, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        
        var = tk.StringVar(value=self.new_creds.get(key, ""))
        entry = tk.Entry(frame, textvariable=var, bg=COLOR_SECONDARY, fg="white", relief="flat", font=("Consolas", 10), show=show)
        entry.pack(fill="x", ipady=5, pady=2)
        
        var.trace_add("write", lambda *args: self.new_creds.update({key: var.get()}))

    def create_paths_step(self):
        tk.Label(self.container, text="1. Speicherorte", font=("Segoe UI", 16, "bold"), bg=COLOR_PRIMARY, fg="white").pack(pady=(0, 20))
        tk.Label(self.container, text="Wo sollen Daten gespeichert werden?", font=("Segoe UI", 10), bg=COLOR_PRIMARY, fg="#bdc3c7").pack(pady=(0, 20))
        
        self.add_path_selector("Patienten-Ordner (Honorarnoten):", "PATIENT_BASE_DIR")
        self.add_path_selector("Archiv-Ordner:", "ARCHIVE_DIR")

    def add_path_selector(self, label, key):
        frame = tk.Frame(self.container, bg=COLOR_PRIMARY)
        frame.pack(fill="x", pady=10)
        tk.Label(frame, text=label, bg=COLOR_PRIMARY, fg=COLOR_TEXT, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        
        sub = tk.Frame(frame, bg=COLOR_PRIMARY)
        sub.pack(fill="x", pady=5)
        
        var = tk.StringVar(value=self.config_data.get(key, ""))
        entry = tk.Entry(sub, textvariable=var, bg=COLOR_SECONDARY, fg="white", relief="flat", font=("Consolas", 10))
        entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 5))
        
        var.trace_add("write", lambda *args: self.config_data.update({key: var.get()}))
        
        def browse():
            path = filedialog.askdirectory(initialdir=var.get())
            if path:
                path = path.replace("/", "\\")
                var.set(path)
                
        tk.Button(sub, text="Ordner wählen", command=browse, bg=COLOR_SECONDARY, fg="white", relief="flat", font=("Segoe UI", 9)).pack(side="right")

    def create_api_step(self):
        tk.Label(self.container, text="2. Integrationen (Optional)", font=("Segoe UI", 16, "bold"), bg=COLOR_PRIMARY, fg="white").pack(pady=(0, 20))
        tk.Label(self.container, text="Verbindungen zu externen Diensten.", font=("Segoe UI", 10), bg=COLOR_PRIMARY, fg="#bdc3c7").pack(pady=(0, 20))
        
        self.add_text_input("Teamup API Key:", "TEAMUP_API_KEY", show="*")
        self.add_text_input("Teamup Calendar ID:", "TEAMUP_CALENDAR_ID")

    def create_defaults_step(self):
        tk.Label(self.container, text="3. Standardwerte", font=("Segoe UI", 16, "bold"), bg=COLOR_PRIMARY, fg="white").pack(pady=(0, 20))
        tk.Label(self.container, text="Voreinstellungen für neue Patienten/Leistungen.", font=("Segoe UI", 10), bg=COLOR_PRIMARY, fg="#bdc3c7").pack(pady=(0, 20))
        
        self.add_text_input("Standard Diagnose:", "DEFAULT_DIAGNOSE")
        self.add_text_input("Standard Anrede:", "DEFAULT_ANREDE")
        self.add_text_input("Schnellwahl Beträge (Komma-getrennt):", "QUICK_AMOUNTS")
        self.add_text_input("Fixe Adresse (für KM-Berechnung):", "FIXED_ADDRESS")

    def create_companion_step(self):
        tk.Label(
            self.container,
            text="Companion-App & Verträge",
            font=("Segoe UI", 16, "bold"),
            bg=COLOR_PRIMARY,
            fg="white",
        ).pack(pady=(0, 12))
        tk.Label(
            self.container,
            text=(
                "Verträge werden lokal auf diesem PC gespeichert und nicht in die APK "
                "gepackt. Nach dem Verbinden über den QR-Code werden sie einmalig auf "
                "das Tablet übertragen und dort offline gespeichert."
            ),
            font=("Segoe UI", 10),
            bg=COLOR_PRIMARY,
            fg=COLOR_TEXT,
            wraplength=560,
            justify="left",
        ).pack(fill="x", pady=(0, 14))

        tk.Checkbutton(
            self.container,
            text="Companion-App auf einem Tablet installieren",
            variable=self.download_companion_var,
            bg=COLOR_PRIMARY,
            fg="white",
            selectcolor=COLOR_SECONDARY,
            activebackground=COLOR_PRIMARY,
            activeforeground="white",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        contract_box = tk.LabelFrame(
            self.container,
            text="Vertragsdateien (.json)",
            bg=COLOR_PRIMARY,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=8,
        )
        contract_box.pack(fill="both", expand=True)
        tk.Label(
            contract_box,
            text="Bestehende Verträge bleiben erhalten; ausgewählte IDs werden aktualisiert.",
            bg=COLOR_PRIMARY,
            fg=COLOR_TEXT,
            wraplength=520,
            justify="left",
        ).pack(anchor="w")
        self.contract_files_label = tk.Label(
            contract_box,
            text="Noch keine Dateien ausgewählt.",
            bg=COLOR_PRIMARY,
            fg="#bdc3c7",
            justify="left",
            anchor="w",
            wraplength=520,
        )
        self.contract_files_label.pack(fill="x", pady=8)
        tk.Button(
            contract_box,
            text="JSON-Verträge auswählen",
            command=self.select_contract_files,
            bg=COLOR_SECONDARY,
            fg="white",
            relief="flat",
            font=("Segoe UI", 10),
            padx=12,
            pady=6,
        ).pack(anchor="w")

    def create_material_order_template_step(self):
        tk.Label(
            self.container,
            text="Druckformular für Materialbestellungen",
            font=("Segoe UI", 16, "bold"),
            bg=COLOR_PRIMARY,
            fg="white",
        ).pack(pady=(0, 12))
        tk.Label(
            self.container,
            text=(
                "Wählen Sie das PDF-Druckformular aus, das für "
                "Materialbestellungen verwendet werden soll. Ohne eine gültige "
                "Druckformular-PDF bleibt diese Funktion gesperrt. Sie können "
                "die Datei auch später in der Patientenakte auswählen."
            ),
            font=("Segoe UI", 10),
            bg=COLOR_PRIMARY,
            fg=COLOR_TEXT,
            wraplength=560,
            justify="left",
        ).pack(fill="x", pady=(0, 14))

        self.material_template_label = tk.Label(
            self.container,
            text=self.material_order_template or "Noch kein Druckformular ausgewählt.",
            font=("Segoe UI", 10),
            bg=COLOR_PRIMARY,
            fg=COLOR_TEXT if self.material_order_template else "#bdc3c7",
            wraplength=540,
            justify="left",
            anchor="w",
        )
        self.material_template_label.pack(fill="x", pady=8)
        tk.Button(
            self.container,
            text="Druckformular-PDF auswählen",
            command=self.select_material_order_template,
            bg=COLOR_SECONDARY,
            fg="white",
            relief="flat",
            font=("Segoe UI", 10),
            padx=12,
            pady=6,
        ).pack(anchor="w")

    def select_material_order_template(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Druckformular-PDF auswählen",
            filetypes=(("PDF-Dateien", "*.pdf"),),
        )
        if not path:
            return
        try:
            self.material_order_template = validate_material_order_template(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Druckformular", str(error), parent=self)
            return

        self.config_data["MATERIAL_ORDER_TEMPLATE"] = self.material_order_template
        self.material_template_label.config(
            text=self.material_order_template,
            fg="white",
        )

    def select_contract_files(self):
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Vertrags-JSON-Dateien auswählen",
            filetypes=(("JSON-Dateien", "*.json"),),
        )
        if not paths:
            return
        try:
            read_contract_files(paths)
        except (OSError, ValueError) as error:
            messagebox.showerror("Verträge", str(error), parent=self)
            return

        self.selected_contract_files = list(paths)
        names = "\n".join(os.path.basename(path) for path in self.selected_contract_files)
        self.contract_files_label.config(text=names, fg="white")

    def add_text_input(self, label, key, show=None):
        frame = tk.Frame(self.container, bg=COLOR_PRIMARY)
        frame.pack(fill="x", pady=8)
        tk.Label(frame, text=label, bg=COLOR_PRIMARY, fg=COLOR_TEXT, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        
        var = tk.StringVar(value=str(self.config_data.get(key, "")))
        entry = tk.Entry(frame, textvariable=var, bg=COLOR_SECONDARY, fg="white", relief="flat", font=("Consolas", 10), show=show)
        entry.pack(fill="x", ipady=5, pady=2)
        
        var.trace_add("write", lambda *args: self.config_data.update({key: var.get()}))

    def create_finish_step(self):
        tk.Label(
            self.container,
            text="Fertig!",
            font=("Segoe UI", 20, "bold"),
            bg=COLOR_PRIMARY,
            fg="white",
        ).pack(pady=(12, 8))
        tk.Label(
            self.container,
            text=(
                "Die Vertragsdateien werden lokal gespeichert. Das Tablet lädt sie "
                "beim ersten Verbinden mit LeprendiX herunter."
            ),
            font=("Segoe UI", 11),
            bg=COLOR_PRIMARY,
            fg=COLOR_TEXT,
            wraplength=540,
            justify="center",
        ).pack(pady=8)
        if not self.material_order_template:
            tk.Label(
                self.container,
                text=(
                    "Es wurde keine Druckformular-PDF ausgewählt. "
                    "Materialbestellungen bleiben gesperrt."
                ),
                font=("Segoe UI", 10, "bold"),
                bg=COLOR_PRIMARY,
                fg="#e67e22",
                wraplength=540,
            ).pack(pady=6)
        if self.download_companion_var.get():
            try:
                qr_code = qrcode.QRCode(box_size=5, border=2)
                qr_code.add_data(COMPANION_APK_URL)
                qr_code.make(fit=True)
                qr_image = qr_code.make_image(fill_color="black", back_color="white").convert("RGB")
                qr_photo = ImageTk.PhotoImage(qr_image)
                qr_label = tk.Label(self.container, image=qr_photo, bg=COLOR_PRIMARY)
                qr_label.image = qr_photo
                qr_label.pack(pady=8)
                tk.Label(
                    self.container,
                    text="QR-Code mit dem Tablet scannen, APK herunterladen und installieren.",
                    font=("Segoe UI", 10),
                    bg=COLOR_PRIMARY,
                    fg=COLOR_TEXT,
                ).pack()
            except (ImportError, OSError, ValueError) as error:
                tk.Label(
                    self.container,
                    text=f"APK-Download: {COMPANION_APK_URL}\nQR-Code konnte nicht erstellt werden: {error}",
                    font=("Segoe UI", 9),
                    bg=COLOR_PRIMARY,
                    fg=COLOR_TEXT,
                    wraplength=560,
                ).pack()
        else:
            tk.Label(
                self.container,
                text="Die Tablet-App wurde für diesen Installationsvorgang nicht ausgewählt.",
                font=("Segoe UI", 10),
                bg=COLOR_PRIMARY,
                fg=COLOR_TEXT,
            ).pack()

    def finish(self):
        # Validate credentials if needed
        if self.needs_creds and self.config_data.get("AUTH_ENABLED", False):
            if not self.new_creds.get("user") or not self.new_creds.get("password"):
                messagebox.showwarning("Fehler", "Bitte Benutzername und Passwort festlegen.")
                return

        try:
            if self.material_order_template:
                try:
                    self.config_data["MATERIAL_ORDER_TEMPLATE"] = (
                        validate_material_order_template(
                            self.material_order_template
                        )
                    )
                except (OSError, ValueError) as error:
                    messagebox.showwarning(
                        "Druckformular",
                        f"Die ausgewählte PDF ist nicht mehr verfügbar oder ungültig. "
                        f"Materialbestellungen bleiben gesperrt.\n\n{error}",
                        parent=self,
                    )
                    self.config_data.pop("MATERIAL_ORDER_TEMPLATE", None)
                    self.material_order_template = ""

            if self.selected_contract_files:
                contract_dir = get_contract_directory(
                    self.config_data.get("COMPANION_CONTRACTS_DIR")
                )
                save_contract_files(self.selected_contract_files, contract_dir)
                self.config_data["COMPANION_CONTRACTS_DIR"] = str(contract_dir)

            self.config_data["DOWNLOAD_COMPANION_APP"] = self.download_companion_var.get()
            self.config_data["MATERIAL_ORDER_SETUP_COMPLETED"] = True
            self.config_data["COMPANION_SETUP_COMPLETED"] = True
            self.config_data["LAST_SETUP_VERSION"] = self.current_version
            config_file = os.path.join(self.base_path, 'config.json')
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
            
            if self.needs_creds:
                with open(self.cred_file, "wb") as f:
                    pickle.dump(self.new_creds, f)
                    
            CONFIG.update(self.config_data)
            self.destroy()
        except (OSError, ValueError) as e:
            messagebox.showerror("Fehler", f"Konnte Konfiguration nicht speichern: {e}")

def check_and_run_setup(root):
    try:
        # Pfad sicher auflösen (für EXE und Skript)
        base_path = get_app_directory()
        version_file = os.path.join(base_path, "version.txt")
        with open(version_file, "r") as f:
            current_version = f.read().strip()
    except:
        current_version = "1.0.0"

    last_setup_version = CONFIG.get("LAST_SETUP_VERSION", None)
    
    if (
        last_setup_version != current_version
        or not CONFIG.get("COMPANION_SETUP_COMPLETED", False)
        or not CONFIG.get("MATERIAL_ORDER_SETUP_COMPLETED", False)
    ):
        root.withdraw()
        wizard = SetupWizard(root, current_version)
        root.wait_window(wizard)
        # root.deiconify() # Entfernt: main.py übernimmt das Anzeigen am Ende

if __name__ == "__main__":
    # Ermöglicht das direkte Starten von setup_wizard.py zum Testen
    root = tk.Tk()
    root.withdraw()
    # Erzwinge Setup für Testzwecke
    wizard = SetupWizard(root, "TEST-VERSION")
    root.wait_window(wizard)