import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import sys
import pickle
from config_loader import CONFIG

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
        self.current_version = current_version
        self.current_step = 0
        
        # Determine base path and check for credentials
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            
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

    def add_text_input(self, label, key, show=None):
        frame = tk.Frame(self.container, bg=COLOR_PRIMARY)
        frame.pack(fill="x", pady=8)
        tk.Label(frame, text=label, bg=COLOR_PRIMARY, fg=COLOR_TEXT, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        
        var = tk.StringVar(value=str(self.config_data.get(key, "")))
        entry = tk.Entry(frame, textvariable=var, bg=COLOR_SECONDARY, fg="white", relief="flat", font=("Consolas", 10), show=show)
        entry.pack(fill="x", ipady=5, pady=2)
        
        var.trace_add("write", lambda *args: self.config_data.update({key: var.get()}))

    def create_finish_step(self):
        tk.Label(self.container, text="Fertig!", font=("Segoe UI", 20, "bold"), bg=COLOR_PRIMARY, fg="white").pack(pady=(40, 20))
        tk.Label(self.container, text="Alle Einstellungen wurden erfasst.\n\nSie können diese später jederzeit im Tab 'EINSTELLUNGEN' ändern.", 
                 font=("Segoe UI", 11), bg=COLOR_PRIMARY, fg=COLOR_TEXT, wraplength=500, justify="center").pack(pady=20)

    def finish(self):
        # Validate credentials if needed
        if self.needs_creds and self.config_data.get("AUTH_ENABLED", False):
            if not self.new_creds.get("user") or not self.new_creds.get("password"):
                messagebox.showwarning("Fehler", "Bitte Benutzername und Passwort festlegen.")
                return

        self.config_data["LAST_SETUP_VERSION"] = self.current_version
        CONFIG.update(self.config_data)
        
        try:
            config_file = os.path.join(self.base_path, 'config.json')
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
            
            if self.needs_creds:
                with open(self.cred_file, "wb") as f:
                    pickle.dump(self.new_creds, f)
                    
            self.destroy()
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Konfiguration nicht speichern: {e}")

def check_and_run_setup(root):
    try:
        # Pfad sicher auflösen (für EXE und Skript)
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        version_file = os.path.join(base_path, "version.txt")
        with open(version_file, "r") as f:
            current_version = f.read().strip()
    except:
        current_version = "1.0.0"

    last_setup_version = CONFIG.get("LAST_SETUP_VERSION", None)
    
    if last_setup_version != current_version:
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