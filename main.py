import subprocess
import sys
import os
import threading
import runpy
import pickle
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import requests
from PIL import Image, ImageTk
import json
import datetime
import webbrowser
import time
import math
import shutil
import logging
import tempfile
import traceback # Für Crash-Handling

def get_base_path():
    """ Ermittelt den Pfad zum Ordner, in dem die EXE oder das Skript liegt """
    if getattr(sys, 'frozen', False):
        # Pfad der EXE im "One Directory" Modus
        return os.path.dirname(sys.executable)
    else:
        # Pfad im Editor
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
os.chdir(BASE_DIR)

def resource_path(relative_path):
    """ Hilfsfunktion für interne Ressourcen (wie Logos im _MEIPASS) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = BASE_DIR
    return os.path.join(base_path, relative_path)


from config_loader import CONFIG
import gui_generator
import patient_status_checker
import crash_handler
import setup_wizard

# --- LOGGING SETUP ---
def setup_logging():
    # Use a user-writable directory for logs to avoid PermissionError
    app_name = "LeprendiX"
    if sys.platform == "win32":
        base_path = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
    else:
        base_path = os.path.join(os.path.expanduser("~"), ".local", "share")
    
    log_dir = os.path.join(base_path, app_name, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "leprendix.log")
    except Exception:
        log_file = os.path.join(tempfile.gettempdir(), "leprendix.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"=== LeprendiX gestartet (Log: {log_file}) ===")

# --- WATCHDOG KLASSE (FREEZE DETECTION) ---
class AppWatchdog:
    """
    Überwacht den Haupt-Thread. Wenn dieser für 'timeout_sec' Sekunden blockiert,
    wird der Crash-Handler ausgelöst.
    """
    def __init__(self, root, check_interval_ms=1000, timeout_sec=20):
        self.root = root
        self.check_interval_ms = check_interval_ms
        self.timeout_sec = timeout_sec
        self.last_heartbeat = time.time()
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)

    def start(self):
        self.monitor_thread.start()
        self._schedule_heartbeat()

    def stop(self):
        self.running = False

    def _schedule_heartbeat(self):
        if not self.running:
            return
        # Heartbeat aktualisieren (dies läuft im Main-Thread)
        self.last_heartbeat = time.time()
        try:
            self.root.after(self.check_interval_ms, self._schedule_heartbeat)
        except Exception:
            pass # Falls root zerstört wurde

    def _monitor_loop(self):
        while self.running:
            time.sleep(1)
            # Prüfen, ob der letzte Heartbeat zu lange her ist
            if time.time() - self.last_heartbeat > self.timeout_sec:
                self._trigger_freeze_handling()
                break

    def _trigger_freeze_handling(self):
        logging.critical("WATCHDOG: Programm reagiert nicht mehr (Freeze detected).")
        
        # Crash-Log schreiben
        crash_file = crash_handler.CRASH_FILE
        try:
            with open(crash_file, "w", encoding="utf-8") as f:
                f.write("KRITISCHER FEHLER: PROGRAMM EINGEFROREN (FREEZE)\n")
                f.write("================================================\n")
                f.write("Der Watchdog hat festgestellt, dass die Benutzeroberfläche seit über 20 Sekunden nicht mehr reagiert.\n")
                f.write("Mögliche Ursachen: Endlosschleife, blockierende Netzwerkabfrage oder Deadlock.\n")
                f.write(f"Zeitstempel: {datetime.datetime.now()}\n")
        except Exception:
            pass

        # Crash Handler starten
        crash_handler.start_crash_handler_process()
        
        # Prozess hart beenden (os._exit killt sofort, sys.exit wirft nur Exception)
        os._exit(1)

# --- KONFIGURATION & DESIGN ---
COLOR_PRIMARY = "#2c3e50"
COLOR_SECONDARY = "#34495e"
COLOR_ACCENT = "#27ae60"
COLOR_TEXT = "#ecf0f1"
COLOR_HIGHLIGHT = "#3498db"
LOGO_PATH = resource_path("logo.png")

# --- GITHUB CONFIG FOR RELEASE NOTES ---
GITHUB_USER = "qztq"
REPO_NAME = "LeprendiX"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/releases"
GITHUB_TOKEN = CONFIG.get("GITHUB_TOKEN", "")


# --- CREDENTIALS LADEN ---
def load_credentials():
    cred_path = os.path.join(BASE_DIR, "credentials.dat")
    if os.path.exists(cred_path):
        try:
            with open(cred_path, "rb") as f:
                return pickle.load(f)
        except:
            return None
    return None

USER_CREDS = load_credentials()

def get_release_notes():
    """Fetches and formats the latest release notes from GitHub."""
    notes_content = "Release-Informationen konnten nicht geladen werden.\n\n" \
                    "Bitte prüfen Sie Ihre Internetverbindung oder besuchen Sie die Releases-Seite manuell."
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        # Get latest 5 releases
        response = requests.get(RELEASES_API_URL, headers=headers, timeout=5, params={"per_page": 5})
        response.raise_for_status()
        releases = response.json()
        
        if not releases:
            return "Derzeit sind keine Release-Informationen auf GitHub verfügbar."

        formatted_notes = ""
        for release in releases:
            tag_name = release.get('tag_name', 'N/A')
            name = release.get('name', tag_name) # Fallback to tag_name if name is empty
            published_at_iso = release.get('published_at')
            body = release.get('body', 'Keine Beschreibung vorhanden.')

            # Format date
            if published_at_iso:
                # GitHub API returns ISO 8601 format (e.g., "2024-01-15T10:00:00Z")
                dt_utc = datetime.datetime.fromisoformat(published_at_iso.replace('Z', '+00:00'))
                published_at_str = dt_utc.strftime("%d.%m.%Y")
            else:
                published_at_str = "N/A"

            # Build the string for one release
            formatted_notes += f"Version: {name}\n"
            formatted_notes += f"Datum: {published_at_str}\n"
            formatted_notes += "--------------------------------------------------\n"
            
            clean_body = body.replace('\r\n', '\n').strip()
            formatted_notes += clean_body + "\n\n\n"
            
        return formatted_notes if formatted_notes else notes_content

    except requests.exceptions.RequestException as e:
        return f"{notes_content}\n\nFehlerdetails: {e}"
    except Exception as e:
        return f"{notes_content}\n\nFehlerdetails: {e}"

class LoginSplash(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.running = True
        self.overrideredirect(True)
        self.configure(bg='#0a0a0a')

        w, h = 550, 400 
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.attributes("-topmost", True)

        self.canvas = tk.Canvas(self, width=w, height=h, bg='#0a0a0a', highlightthickness=0)
        self.canvas.pack()

        # UI Elemente from start.py
        self.canvas.create_text(w/2 - 30, h/2 - 20, text="Leprendi", font=("Segoe UI", 45, "bold"), fill="#f8f9fa")
        self.wait_text = self.canvas.create_text(w/2, h - 40, text="Anwendung wird gestartet...", font=("Segoe UI", 12, "italic"), fill="#555555")

        cx, cy = w/2 + 130, h/2 - 20
        s = 35  

        self.canvas.create_line(cx-s, cy-s, cx+s, cy+s, fill="#1a1a1a", width=15, capstyle="round")
        self.canvas.create_line(cx+s, cy-s, cx-s, cy+s, fill="#1a1a1a", width=15, capstyle="round")

        self.points = [(cx-s, cy-s), (cx+s, cy+s), (cx+s, cy-s), (cx-s, cy+s)]
        self.dot = self.canvas.create_oval(0,0,0,0, fill="#00f2ff", outline="#70f3ff", width=2)
        
        self.trail_length = 12 
        self.trail_dots = [self.canvas.create_oval(0,0,0,0, fill="#004d4d", outline="") for _ in range(self.trail_length)]
        self.history = []
        
        self.start_time = time.time()
        self.animate()

    def animate(self):
        if not self.running or not self.winfo_exists():
            return
        
        try:
            elapsed = time.time() - self.start_time

            speed = (math.sin(elapsed * 0.7) + 1.1) * 0.5
            t = (elapsed * speed) % 2.0
            p1, p2 = (self.points[0], self.points[1]) if t < 1.0 else (self.points[2], self.points[3])
            pos_t = t if t < 1.0 else t - 1.0

            cur_x = p1[0] + (p2[0] - p1[0]) * pos_t
            cur_y = p1[1] + (p2[1] - p1[1]) * pos_t

            self.history.insert(0, (cur_x, cur_y))
            if len(self.history) > self.trail_length + 1: self.history.pop()

            for i, dot_id in enumerate(self.trail_dots):
                if i < len(self.history):
                    hx, hy = self.history[i]
                    r = (self.trail_length - i) * 0.6 
                    self.canvas.coords(dot_id, hx-r, hy-r, hx+r, hy+r)

            r_main = 5 + math.sin(elapsed * 5) * 1.2
            self.canvas.coords(self.dot, cur_x-r_main, cur_y-r_main, cur_x+r_main, cur_y+r_main)

            if self.running and self.winfo_exists():
                self.after(30, self.animate)
        
        except (tk.TclError, AttributeError):
            self.running = False

    def stop(self):
        self.running = False
        self.destroy()

# In main.py
def launch_application(root):
    root.withdraw() 
    splash = LoginSplash(root)
    
    def finalize_start():
        # 1. Splash zerstören
        splash.stop()
        
        # Hauptanwendung (Generator) starten
        gen_root = tk.Tk()
        app_gen = gui_generator.HonorarGeneratorApp(gen_root)
        
        gen_root.mainloop()

        # Sobald das Hauptfenster geschlossen wird, beenden wir auch den unsichtbaren root
        root.destroy()

    # Wir warten 2 Sekunden mit dem Splash und rufen dann finalize_start im Main-Thread auf
    root.after(2000, finalize_start)
    root.mainloop()

class CollapsiblePane(tk.Frame):
    """Eine aufklappbare Frame-Komponente für Einstellungen."""
    def __init__(self, parent, title, expanded=False, bg_color=COLOR_PRIMARY):
        super().__init__(parent, bg=bg_color)
        self.columnconfigure(0, weight=1)
        self._variable = tk.BooleanVar(value=expanded)
        self._title = title
        self._bg = bg_color
        
        self._button = tk.Button(self, text=f"{'▼' if expanded else '▶'} {title}", 
                                 command=self._toggle, relief="flat", 
                                 bg=COLOR_SECONDARY, fg="white", 
                                 font=("Segoe UI", 12, "bold"), anchor="w", padx=10, pady=5)
        self._button.grid(row=0, column=0, sticky="ew", pady=(5,0))
        
        self.frame = tk.Frame(self, bg=self._bg)
        if expanded:
            self.frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
            
    def _toggle(self):
        if self._variable.get():
            self.frame.grid_remove()
            self._variable.set(False)
            self._button.configure(text=f"▶ {self._title}")
        else:
            self.frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
            self._variable.set(True)
            self._button.configure(text=f"▼ {self._title}")

# --- HAUPTFENSTER ---
def create_main():
    setup_logging() # Logging initialisieren
    
    # Hooks installieren via crash_handler
    crash_handler.install_exception_handler()
    
    if hasattr(threading, 'excepthook'):
        threading.excepthook = lambda args: crash_handler.global_exception_handler(args.exc_type, args.exc_value, args.exc_traceback)
    
    root = tk.Tk()
    # Tkinter Callback-Fehler auch abfangen
    root.report_callback_exception = crash_handler.global_exception_handler
    root.withdraw() # Fenster erst verstecken, bis alles geladen ist
    
    # --- SETUP WIZARD CHECK (Startet nur bei neuer Version/Erstinstallation) ---
    setup_wizard.check_and_run_setup(root)
    
    root.title("LeprendiX - Control Center")
    root.geometry("1150x850")
    root.configure(bg=COLOR_PRIMARY)

    # Watchdog starten (Schutz gegen Freezes)
    watchdog = AppWatchdog(root)
    watchdog.start()

    # Styles
    style = ttk.Style()
    style.theme_use('default')
    style.configure("TNotebook", background=COLOR_PRIMARY, borderwidth=0)
    style.configure("TNotebook.Tab", background=COLOR_SECONDARY, foreground=COLOR_TEXT, 
                    padding=[25, 10], font=("Segoe UI", 10, "bold"))
    style.map("TNotebook.Tab", background=[("selected", COLOR_PRIMARY)], foreground=[("selected", COLOR_ACCENT)])

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=20, pady=20)

    # --- TAB 1: ÜBERSICHT ---
    t1 = tk.Frame(nb, bg=COLOR_PRIMARY)
    nb.add(t1, text="  ÜBERSICHT  ")

    if os.path.exists(LOGO_PATH):
        # 1. Bild öffnen
        img = Image.open(LOGO_PATH)
        
        # 2. Proportionale Skalierung berechnen (z.B. maximale Breite 500px)
        max_width = 500
        w_percent = (max_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        
        # 3. Resize mit berechneten Werten (Beibehaltung des Seitenverhältnisses)
        img = img.resize((max_width, h_size), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        
        # 4. Label zentrieren
        # Durch pack(expand=True) wird das Label im verfügbaren Raum zentriert
        logo_label = tk.Label(t1, image=img_tk, bg=COLOR_PRIMARY)
        logo_label.image = img_tk  # Referenz behalten (Garbage Collection Schutz)
        logo_label.pack(pady=40, expand=False) # expand=False, falls es oben kleben soll, True für echte Mitte

    # Login Bereich
    login_f = tk.Frame(t1, bg=COLOR_SECONDARY, padx=40, pady=30, highlightbackground=COLOR_ACCENT, highlightthickness=1)
    login_f.pack(pady=10)

    tk.Label(login_f, text="SYSTEM-LOGIN", font=("Segoe UI", 14, "bold"), fg=COLOR_ACCENT, bg=COLOR_SECONDARY).pack(pady=(0, 20))
    
    tk.Label(login_f, text="Benutzername:", fg=COLOR_TEXT, bg=COLOR_SECONDARY).pack(anchor="w")
    u_ent = tk.Entry(login_f, width=30, bg=COLOR_PRIMARY, fg="white", relief="flat", insertbackground="white")
    u_ent.pack(pady=(5, 15), ipady=5)
    u_ent.insert(0, "bhag")

    tk.Label(login_f, text="Passwort:", fg=COLOR_TEXT, bg=COLOR_SECONDARY).pack(anchor="w")
    p_ent = tk.Entry(login_f, show="*", width=30, bg=COLOR_PRIMARY, fg="white", relief="flat", insertbackground="white")
    p_ent.pack(pady=(5, 20), ipady=5)

    def do_login(event=None):
        if not USER_CREDS:
            messagebox.showerror("Fehler", "Datei 'credentials.dat' fehlt!")
            return
        if u_ent.get() == USER_CREDS.get("user") and p_ent.get() == USER_CREDS.get("password"):
            launch_application(root)
        else:
            messagebox.showerror("Fehler", "Logindaten inkorrekt.")

    tk.Button(login_f, text="ANMELDEN & STARTEN", bg=COLOR_ACCENT, fg="white", font=("Segoe UI", 11, "bold"),
              relief="flat", cursor="hand2", padx=20, pady=10, command=do_login).pack(fill="x")
    root.bind('<Return>', do_login)




    # --- TAB 2: DATENBANK & EINSTELLUNGEN ---
    t2 = tk.Frame(nb, bg=COLOR_PRIMARY)
    nb.add(t2, text="   EINSTELLUNGEN   ")

    # Scroll-Container Setup
    canvas = tk.Canvas(t2, bg=COLOR_PRIMARY, highlightthickness=0)
    scrollbar = ttk.Scrollbar(t2, orient="vertical", command=canvas.yview)
    db_container = tk.Frame(canvas, bg=COLOR_PRIMARY)

    db_container.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )

    canvas_window = canvas.create_window((0, 0), window=db_container, anchor="nw")

    def _configure_canvas(event):
        canvas.itemconfig(canvas_window, width=event.width)
    
    canvas.bind("<Configure>", _configure_canvas)
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def _bind_mousewheel(event):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def _unbind_mousewheel(event):
        canvas.unbind_all("<MouseWheel>")

    # Bindings für Scrolling wenn Maus über dem Bereich ist
    db_container.bind("<Enter>", _bind_mousewheel)
    db_container.bind("<Leave>", _unbind_mousewheel)

    # --- KATEGORIE 1: DATENBANK & PFADE ---
    cat1 = CollapsiblePane(db_container, "Datenbank & Pfade", expanded=True)
    cat1.pack(fill="x", pady=5, padx=5)
    
    # Datenbank Init
    tk.Label(cat1.frame, text="Datenbank-Initialisierung", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT, bg=COLOR_PRIMARY).pack(pady=(10, 5), anchor="w")

    db_p_ent = tk.Entry(cat1.frame, show="*", width=30, bg=COLOR_SECONDARY, 
                        fg="white", font=("Arial", 12), justify="center", relief="flat")
    db_p_ent.pack(pady=5, ipady=5)

    def do_setup():
        if USER_CREDS and db_p_ent.get() == USER_CREDS.get("password"):
            try:
                setup_script = resource_path("db_setup.py")
                runpy.run_path(setup_script, run_name="__main__")
                messagebox.showinfo("Erfolg", "Datenbank bereit.")
            except Exception as e: 
                messagebox.showerror("Fehler", f"Setup fehlgeschlagen:\n{e}")
        else: 
            messagebox.showerror("Fehler", "Passwort falsch.")
            
    tk.Button(cat1.frame, text="Datenbank Setup ausführen", bg="#e67e22", fg="white", 
            font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=8, 
            command=do_setup).pack(pady=10)

    # Pfad Konfiguration
    tk.Label(cat1.frame, text="Speicherorte", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT, bg=COLOR_PRIMARY).pack(pady=(15, 5), anchor="w")

    # Frames für die Pfadanzeige
    def create_path_row(parent, label_text, config_key):
        row = tk.Frame(parent, bg=COLOR_PRIMARY)
        row.pack(fill="x", pady=5)
        
        tk.Label(row, text=label_text, fg=COLOR_TEXT, bg=COLOR_PRIMARY, font=("Segoe UI", 10, "bold"), width=15, anchor="w").pack(side="left")
        
        # Label zur Anzeige des aktuellen Pfads
        path_var = tk.StringVar(value=CONFIG.get(config_key, "Nicht gesetzt"))
        lbl = tk.Label(row, textvariable=path_var, fg="#bdc3c7", bg=COLOR_SECONDARY, font=("Consolas", 9), anchor="w", padx=10)
        lbl.pack(side="left", fill="x", expand=True, padx=10, ipady=3)
        
        def change_path():
            new_path = filedialog.askdirectory(initialdir=path_var.get())
            if new_path:
                new_path = new_path.replace("/", "\\") # Windows-Format
                # 1. Variable im Programm aktualisieren
                CONFIG[config_key] = new_path
                path_var.set(new_path)
                # 2. In JSON speichern
                try:
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(CONFIG, f, indent=4)
                    messagebox.showinfo("Gespeichert", f"{label_text} wurde aktualisiert.")
                except Exception as e:
                    messagebox.showerror("Fehler", f"Speichern fehlgeschlagen: {e}")

        tk.Button(row, text="Ändern", bg=COLOR_SECONDARY, fg="white", font=("Segoe UI", 8), 
                relief="flat", command=change_path, padx=10).pack(side="right")

    # Erzeuge die Zeilen für die beiden Hauptpfade
    create_path_row(cat1.frame, "Patienten-Ordner:", "PATIENT_BASE_DIR")
    create_path_row(cat1.frame, "Archiv-Ordner:", "ARCHIVE_DIR")

    # --- KATEGORIE 2: INTEGRATIONEN (API) ---
    cat2 = CollapsiblePane(db_container, "Integrationen (API)", expanded=False)
    cat2.pack(fill="x", pady=5, padx=5)
            
    def create_config_entry(parent, label_text, config_key, show_char=None):
        row = tk.Frame(parent, bg=COLOR_PRIMARY)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label_text, fg=COLOR_TEXT, bg=COLOR_PRIMARY, font=("Segoe UI", 10, "bold"), width=25, anchor="w").pack(side="left")
        
        var = tk.StringVar(value=CONFIG.get(config_key, ""))
        entry = tk.Entry(row, textvariable=var, bg=COLOR_SECONDARY, fg="white", relief="flat", show=show_char)
        entry.pack(side="left", fill="x", expand=True, padx=10, ipady=3)
        
        def save_val():
            CONFIG[config_key] = var.get().strip()
            try:
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(CONFIG, f, indent=4)
                messagebox.showinfo("Gespeichert", f"{label_text} gespeichert.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Speichern fehlgeschlagen: {e}")
                
        tk.Button(row, text="Speichern", bg=COLOR_SECONDARY, fg="white", font=("Segoe UI", 8), 
                relief="flat", command=save_val, padx=10).pack(side="right")

    create_config_entry(cat2.frame, "Teamup API Key:", "TEAMUP_API_KEY", show_char="*")
    create_config_entry(cat2.frame, "Teamup Calendar ID:", "TEAMUP_CALENDAR_ID")
    create_config_entry(cat2.frame, "GitHub Token (Updates):", "GITHUB_TOKEN", show_char="*")

    # --- KATEGORIE 3: STANDARDWERTE ---
    cat3 = CollapsiblePane(db_container, "Standardwerte & Editor", expanded=False)
    cat3.pack(fill="x", pady=5, padx=5)

    create_config_entry(cat3.frame, "Standard Diagnose:", "DEFAULT_DIAGNOSE")
    create_config_entry(cat3.frame, "Standard Anrede:", "DEFAULT_ANREDE")
    create_config_entry(cat3.frame, "Schnellwahl Beträge (Komma-getrennt):", "QUICK_AMOUNTS")

    # --- KATEGORIE 4: WARTUNG & BACKUPS ---
    cat4 = CollapsiblePane(db_container, "Wartung & Backups", expanded=False)
    cat4.pack(fill="x", pady=5, padx=5)
            
    # Reminder
    tk.Label(cat4.frame, text="⚠️ WICHTIG: Bitte erstellen Sie regelmäßig Backups!", 
             font=("Segoe UI", 10, "bold"), fg="#e74c3c", bg=COLOR_PRIMARY).pack(pady=(0, 10), anchor="w")

    # Backup Liste
    backup_list_frame = tk.LabelFrame(cat4.frame, text="Verfügbare Backups", bg=COLOR_PRIMARY, fg=COLOR_TEXT)
    backup_list_frame.pack(fill="x", pady=5, padx=10)
    
    backup_listbox = tk.Listbox(backup_list_frame, height=5, bg=COLOR_SECONDARY, fg="white", relief="flat")
    backup_listbox.pack(side="left", fill="x", expand=True, padx=5, pady=5)
    
    backup_scroll = tk.Scrollbar(backup_list_frame, command=backup_listbox.yview)
    backup_scroll.pack(side="right", fill="y", pady=5)
    backup_listbox.config(yscrollcommand=backup_scroll.set)

    def refresh_backups():
        backup_listbox.delete(0, tk.END)
        backup_dir = os.path.join(BASE_DIR, "backups")
        if os.path.exists(backup_dir):
            try:
                files = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")], reverse=True)
                for f in files:
                    backup_listbox.insert(tk.END, f)
            except Exception as e:
                print(f"Fehler beim Listen der Backups: {e}")

    def create_backup():
        db_path = os.path.join(BASE_DIR, "patienten.db")
        if not os.path.exists(db_path):
            messagebox.showerror("Fehler", "Datenbank nicht gefunden.")
            return
        
        backup_dir = os.path.join(BASE_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"patienten_backup_{timestamp}.db")
        
        try:
            shutil.copy2(db_path, backup_path)
            messagebox.showinfo("Backup", f"Backup erfolgreich erstellt:\n{backup_path}")
            refresh_backups()
        except Exception as e:
            messagebox.showerror("Fehler", f"Backup fehlgeschlagen: {e}")

    def restore_backup():
        selection = backup_listbox.curselection()
        if not selection:
            messagebox.showwarning("Auswahl", "Bitte wählen Sie ein Backup aus der Liste.")
            return
        
        filename = backup_listbox.get(selection[0])
        backup_path = os.path.join(BASE_DIR, "backups", filename)
        db_path = os.path.join(BASE_DIR, "patienten.db")
        
        if messagebox.askyesno("Wiederherstellen", f"ACHTUNG: Möchten Sie die Datenbank wirklich auf den Stand von '{filename}' zurücksetzen?\n\nAlle Änderungen seit diesem Backup gehen verloren!"):
            try:
                shutil.copy2(backup_path, db_path)
                messagebox.showinfo("Erfolg", "Datenbank wurde erfolgreich wiederhergestellt.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Wiederherstellung fehlgeschlagen: {e}")

    def open_app_dir():
        try:
            os.startfile(BASE_DIR) if sys.platform == 'win32' else subprocess.Popen(['xdg-open', BASE_DIR])
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Ordner nicht öffnen: {e}")

    def open_log_dir():
        app_name = "LeprendiX"
        if sys.platform == "win32":
            base_path = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
        else:
            base_path = os.path.join(os.path.expanduser("~"), ".local", "share")
        
        log_dir = os.path.join(base_path, app_name, "logs")
        
        if os.path.exists(log_dir):
            try:
                os.startfile(log_dir) if sys.platform == 'win32' else subprocess.Popen(['xdg-open', log_dir])
            except Exception as e:
                messagebox.showerror("Fehler", f"Konnte Log-Ordner nicht öffnen: {e}")
        else:
            messagebox.showinfo("Info", f"Log-Ordner existiert noch nicht:\n{log_dir}")

    btn_frame = tk.Frame(cat4.frame, bg=COLOR_PRIMARY)
    btn_frame.pack(pady=5)
    tk.Button(btn_frame, text="Backup erstellen", bg=COLOR_SECONDARY, fg="white", font=("Segoe UI", 10), relief="flat", command=create_backup, padx=15, pady=5).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Backup wiederherstellen", bg="#e67e22", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", command=restore_backup, padx=15, pady=5).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Ordner öffnen", bg=COLOR_SECONDARY, fg="white", font=("Segoe UI", 10), relief="flat", command=open_app_dir, padx=15, pady=5).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Logs öffnen", bg=COLOR_SECONDARY, fg="white", font=("Segoe UI", 10), relief="flat", command=open_log_dir, padx=15, pady=5).pack(side="left", padx=5)

    refresh_backups()

    # --- KATEGORIE 5: INFO & SUPPORT ---
    cat5 = CollapsiblePane(db_container, "Informationen & Support", expanded=False)
    cat5.pack(fill="x", pady=5, padx=5)
    
    try:
        with open("version.txt", "r") as f:
            ver = f.read().strip()
    except:
        ver = "Unbekannt (Dev)"
        
    tk.Label(cat5.frame, text=f"Version: {ver}", fg="#bdc3c7", bg=COLOR_PRIMARY, font=("Segoe UI", 10)).pack(pady=5)
    
    def open_support():
        webbrowser.open("https://github.com/qztq/LeprendiX/issues")

    def open_releases():
        webbrowser.open("https://github.com/qztq/LeprendiX/releases")
        
    def trigger_crash():
        # Simuliert einen Absturz, um den Handler zu testen
        raise RuntimeError("Dies ist ein manuell ausgelöster Test-Absturz!")
        
    support_frame = tk.Frame(cat5.frame, bg=COLOR_PRIMARY)
    support_frame.pack(pady=10)
    tk.Button(support_frame, text="Support / Fehler melden", bg=COLOR_ACCENT, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", command=open_support, padx=20, pady=5).pack(side="left", padx=5)
    tk.Button(support_frame, text="Auf Updates prüfen", bg=COLOR_SECONDARY, fg="white", font=("Segoe UI", 10), relief="flat", command=open_releases, padx=20, pady=5).pack(side="left", padx=5)
    tk.Button(support_frame, text="Crash Test 💥", bg="#c0392b", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", command=trigger_crash, padx=20, pady=5).pack(side="left", padx=5)

    # --- TAB 3: DOKUMENTATION ---
    t3 = tk.Frame(nb, bg=COLOR_PRIMARY)
    nb.add(t3, text="  DOKUMENTATION  ")

    # --- Sidebar für Navigation & Suche ---
    sidebar = tk.Frame(t3, bg=COLOR_SECONDARY, width=300)
    sidebar.pack(side="left", fill="y", padx=(10, 0), pady=10)
    sidebar.pack_propagate(False)

    # Sucheingabe
    tk.Label(sidebar, text="Suche:", bg=COLOR_SECONDARY, fg=COLOR_TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
    search_var = tk.StringVar()
    search_entry = tk.Entry(sidebar, textvariable=search_var, bg=COLOR_PRIMARY, fg="white", insertbackground="white", relief="flat")
    search_entry.pack(fill="x", padx=10, pady=(0, 10))

    # Liste der Kapitel
    tk.Label(sidebar, text="Inhalt:", bg=COLOR_SECONDARY, fg=COLOR_TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(5, 5))
    
    # Listbox mit Scrollbar
    list_frame = tk.Frame(sidebar, bg=COLOR_SECONDARY)
    list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    nav_scroll = tk.Scrollbar(list_frame)
    nav_scroll.pack(side="right", fill="y")
    
    nav_list = tk.Listbox(list_frame, bg=COLOR_PRIMARY, fg=COLOR_TEXT, selectbackground=COLOR_ACCENT, 
                          selectforeground="white", relief="flat", yscrollcommand=nav_scroll.set, font=("Segoe UI", 10))
    nav_list.pack(side="left", fill="both", expand=True)
    nav_scroll.config(command=nav_list.yview)

    # --- Content Bereich ---
    content_f = tk.Frame(t3, bg=COLOR_PRIMARY)
    content_f.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    scroll = tk.Scrollbar(content_f)
    scroll.pack(side="right", fill="y")

    doc_t = tk.Text(content_f, wrap="word", padx=30, pady=30, font=("Segoe UI", 11), 
                    bg=COLOR_SECONDARY, fg=COLOR_TEXT, relief="flat", yscrollcommand=scroll.set)
    doc_t.pack(fill="both", expand=True)
    scroll.config(command=doc_t.yview)

    # --- Dokumentations-Inhalt ---
    sections = [
        ("1. Einleitung", "SEC_1", 
         "Willkommen bei LeprendiX – Ihrer Lösung für Patientenverwaltung und Honorarnotenerstellung.\n"
         "Diese Software wurde entwickelt, um den administrativen Aufwand zu minimieren, indem sie Patientenstammdaten, "
         "Leistungserfassung (inkl. Teamup-Kalender-Import) und Rechnungslegung in einer Oberfläche vereint.\n\n"),
        
        ("2. Installation & Setup", "SEC_2", 
         "Nach der Installation muss die Anwendung einmalig eingerichtet werden:\n"
         "1. Starten Sie das Programm und melden Sie sich im 'Control Center' an.\n"
         "2. Wechseln Sie in den Tab 'EINSTELLUNGEN'.\n"
         "3. Führen Sie das 'Datenbank Setup' aus (Passwort erforderlich).\n"
         "4. Konfigurieren Sie die Pfade für 'Patienten-Ordner' (Speicherort der Honorarnoten) und 'Archiv-Ordner'.\n\n"),
        
        ("3. Patientenverwaltung", "SEC_3", 
         "Im Tab 'Patienten Verwalten' pflegen Sie Ihre Datenbank:\n"
         "- Neuer Patient: Füllen Sie alle Felder aus und klicken Sie auf 'Patient Hinzufügen'.\n"
         "- Bearbeiten: Suchen Sie einen Patienten, laden Sie ihn, ändern Sie Daten und klicken Sie auf 'Patient Aktualisieren'.\n"
         "- Löschen: Ein geladener Patient kann inkl. aller Leistungen unwiderruflich gelöscht werden.\n"
         "Hinweis: Das System prüft auf Duplikate basierend auf Vorname, Nachname und PLZ.\n\n"),
        
        ("4. Leistungen & Teamup-Import", "SEC_4", 
         "Leistungen werden im Tab 'Leistungen Hinzufügen/Prüfen' erfasst:\n"
         "- Manuell: Datum, Uhrzeit und Betrag eingeben.\n"
         "- Stammdaten: Nutzen Sie die Schnellwahl-Buttons für häufige Leistungen (konfigurierbar in Tab 4).\n"
         "- Teamup-Import: Klicken Sie auf 'Teamup-Termine Importieren'. Das System sucht nach Terminen basierend auf dem Patientennamen.\n"
         "  Wichtig: Wählen Sie vorher die gewünschten Leistungsarten (Buttons) aus, die den importierten Terminen zugewiesen werden sollen.\n"
         "  Kilometergeld wird automatisch basierend auf den Patientendaten addiert.\n\n"),
        
        ("5. Honorarnote Generieren", "SEC_5", 
         "Der Prozess der Rechnungslegung:\n"
         "1. Suchen und wählen Sie den Patienten im Tab 'Honorarnote Generieren'.\n"
         "2. Prüfen Sie die angezeigten Daten.\n"
         "3. Wählen Sie das Rechnungsdatum (Monat/Jahr).\n"
         "4. BHAG-Nummer: Die fortlaufende Nummer wird automatisch generiert, kann aber manuell korrigiert werden.\n"
         "5. Klicken Sie auf 'Speichern & Öffnen' (Word) oder 'Speichern & Drucken'.\n"
         "Nach erfolgreichem Druck wird der Status des Patienten im System auf 'Abgerechnet' (Grün) gesetzt.\n\n"),
        
        ("6. Status-Checker & Archivierung", "SEC_6", 
         "Der 'Status-Checker' (aufrufbar über Tab 1) bietet eine Übersicht:\n"
         "- Rot: Offene Leistungen / Noch nicht abgerechnet.\n"
         "- Grün: Honorarnote wurde erstellt.\n"
         "Funktionen:\n"
         "- Archivieren: Verschiebt den Ordner des Patienten in das Archiv-Verzeichnis und entfernt ihn aus der aktiven Datenbank.\n"
         "- Reset: Setzt alle Statusanzeigen zurück auf Rot (z.B. für einen neuen Abrechnungszeitraum).\n\n"),
        
        ("7. Stammdatenverwaltung", "SEC_7", 
         "Im Tab 'Stammdaten Leistungen' definieren Sie Ihre Standard-Leistungen.\n"
         "Diese erscheinen als Buttons im Leistungs-Tab. Ein Kurzname, eine Beschreibung (für die Rechnung) und ein Standardbetrag sind erforderlich.\n\n"),
        
        ("8. Technische Hinweise", "SEC_8", 
         "Konfigurationsdateien:\n"
         "- config.json: Speichert Pfade.\n"
         "- credentials.dat: Verschlüsselte Login-Daten.\n"
         "- patienten.db: SQLite Datenbank.\n"
         "Updates: Beim Start prüft der Launcher automatisch auf neue Versionen via GitHub.\n\n"),
        
        ("9. Release Notes", "SEC_9", 
         "Lade Release Notes von GitHub...\n")
    ]

    title_to_tag = {}

    for title, tag, content in sections:
        doc_t.insert(tk.END, title + "\n", ("heading", tag))
        doc_t.insert(tk.END, content, ("content",))
        title_to_tag[title] = tag
        nav_list.insert(tk.END, title)

    doc_t.tag_configure("heading", font=("Segoe UI", 14, "bold"), foreground=COLOR_ACCENT, spacing3=10)
    doc_t.tag_configure("content", spacing1=5, spacing3=15)
    doc_t.config(state="disabled")

    def on_nav_select(event):
        selection = nav_list.curselection()
        if selection:
            title = nav_list.get(selection[0])
            tag = title_to_tag.get(title)
            if tag:
                doc_t.see(f"{tag}.first")

    nav_list.bind('<<ListboxSelect>>', on_nav_select)

    def filter_list(*args):
        search_term = search_var.get().lower()
        nav_list.delete(0, tk.END)
        for title, _, _ in sections:
            if search_term in title.lower():
                nav_list.insert(tk.END, title)

    search_var.trace_add("write", filter_list)

    # --- Release Notes Lade-Logik ---
    def fetch_and_display_releases_threaded():
        def fetch():
            content = get_release_notes()
            # Schedule the UI update in the main thread
            if doc_t.winfo_exists():
                doc_t.after(0, update_ui, content)

        def update_ui(content):
            try:
                doc_t.config(state="normal")
                
                # Tag für die Überschrift der Release Notes
                heading_tag = "SEC_9"
                
                # Finde den Start der Überschrift
                heading_start_index = doc_t.tag_ranges(heading_tag)[0]
                # Der Inhalt beginnt auf der nächsten Zeile
                content_start_index = doc_t.index(f"{heading_start_index} + 1 lines linestart")
                
                # Finde das Ende des Inhaltsbereichs für diesen Abschnitt
                next_heading_pos = doc_t.tag_nextrange("heading", content_start_index)
                
                if next_heading_pos:
                    content_end_index = next_heading_pos[0]
                else:
                    content_end_index = tk.END

                # Lösche den Platzhalter-Inhalt
                doc_t.delete(content_start_index, content_end_index)
                
                # Füge den neuen Inhalt ein
                doc_t.insert(content_start_index, content, ("content",))
                
            except (IndexError, tk.TclError):
                print("Konnte Release Notes Sektion nicht aktualisieren (Fenster geschlossen?).")
            finally:
                if doc_t.winfo_exists():
                    doc_t.config(state="disabled")

        threading.Thread(target=fetch, daemon=True).start()

    # Starte das Laden der Release Notes im Hintergrund
    fetch_and_display_releases_threaded()

    # --- AUTO-BACKUP ON EXIT ---
    def on_closing():
        watchdog.stop() # Watchdog stoppen, um False Positives beim Beenden zu vermeiden
        # Automatisches Backup beim Schließen
        if messagebox.askyesno("Backup", "Möchten Sie vor dem Beenden ein automatisches Backup erstellen?"):
            db_path = os.path.join(BASE_DIR, "patienten.db")
            if os.path.exists(db_path):
                try:
                    backup_dir = os.path.join(BASE_DIR, "backups")
                    os.makedirs(backup_dir, exist_ok=True)
                    # Wir behalten nur die letzten 5 Auto-Backups, um Platz zu sparen? 
                    # Hier erstmal einfaches Backup mit Timestamp
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = os.path.join(backup_dir, f"autobackup_{timestamp}.db")
                    shutil.copy2(db_path, backup_path)
                    print(f"[AutoBackup] Backup erstellt: {backup_path}")
                except Exception as e:
                    print(f"[AutoBackup] Fehler: {e}")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.deiconify() # Fenster jetzt anzeigen (fertig geladen)
    root.mainloop()

if __name__ == "__main__":
    if "--crash-handler" in sys.argv:
        crash_handler.main()
    else:
        create_main()