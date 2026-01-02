import tkinter as tk
from tkinter import messagebox, ttk
import time
import math
import requests
import webbrowser
import os
import subprocess
import sys
import socket
import shutil
import glob
import ctypes
from config_loader import CONFIG
import crash_handler
import migrate_legacy

# Sofort den Crash-Handler aktivieren, um Fehler beim Start/Splash abzufangen
crash_handler.install_exception_handler()

# --- KONFIGURATION ---
GITHUB_USER = "qztq"
REPO_NAME = "LeprendiX"
GITHUB_TOKEN = CONFIG.get("GITHUB_TOKEN", "")
RELEASE_PAGE = f"https://github.com/{GITHUB_USER}/{REPO_NAME}/releases"
API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/releases/latest"


def get_resource_path(relative_path):
    """ Ermittelt den Pfad zur Datei, egal ob Skript oder EXE """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller temporärer Ordner
        return os.path.join(sys._MEIPASS, relative_path)
    # Normaler Ordner (Entwicklung)
    return os.path.join(os.path.abspath("."), relative_path)

def cleanup_old_installers():
    """Löscht alte Installer-Dateien, falls vorhanden."""
    installer_name = "LeprendiX_Win64.exe"
    if os.path.exists(installer_name):
        try:
            os.remove(installer_name)
            print(f"[INFO] Alter Installer '{installer_name}' wurde gelöscht.")
        except Exception as e:
            print(f"[WARNUNG] Konnte '{installer_name}' nicht löschen: {e}")

def check_internet_connection():
    """Prüft, ob eine Internetverbindung besteht (Ping zu Google DNS)."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

_mutex_handle = None
def check_single_instance():
    """Prüft via Named Mutex, ob die Anwendung bereits läuft."""
    global _mutex_handle
    if sys.platform == "win32":
        try:
            mutex_name = "Global\\LeprendiX_Single_Instance_Mutex"
            _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
            if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
                return False
        except Exception:
            pass
    return True

def check_system_integrity():
    """Prüft auf kritische fehlende Dateien und zeigt einen Analyse-Bericht."""
    errors = []
    
    # 1. version.txt
    if not os.path.exists("version.txt"):
        errors.append(("version.txt fehlt", "Die Datei 'version.txt' konnte nicht gefunden werden.\nLösung: Erstellen Sie eine Datei 'version.txt' mit dem Inhalt '1.0.0' im Programmordner oder installieren Sie das Programm neu."))

    # 2. patienten.db
    if not os.path.exists("patienten.db"):
        errors.append(("patienten.db fehlt", "Die Datenbank 'patienten.db' fehlt.\nLösung: \n- Bei Neuinstallation: Führen Sie das 'Datenbank Setup' (db_setup.py) manuell aus.\n- Andernfalls: Stellen Sie ein Backup wieder her."))

    # 3. credentials.dat
    if not os.path.exists("credentials.dat"):
        errors.append(("credentials.dat fehlt", "Die Login-Datei 'credentials.dat' fehlt.\nLösung: Bitte fordern Sie die Zugangsdaten erneut an oder führen Sie das Admin-Setup aus."))

    if errors:
        root = tk.Tk()
        root.withdraw()
        
        err_win = tk.Toplevel(root)
        err_win.title("System-Diagnose: Kritische Fehler")
        err_win.geometry("600x500")
        err_win.configure(bg="#2c3e50")
        
        tk.Label(err_win, text="⚠️ System-Integritätsprüfung fehlgeschlagen", font=("Segoe UI", 14, "bold"), fg="#e74c3c", bg="#2c3e50").pack(pady=10)
        tk.Label(err_win, text="Das Programm kann nicht gestartet werden, da folgende Dateien fehlen:", font=("Segoe UI", 10), fg="white", bg="#2c3e50").pack(pady=5)
        
        frame = tk.Frame(err_win, bg="#2c3e50")
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        for title, solution in errors:
            err_frame = tk.LabelFrame(frame, text=title, font=("Segoe UI", 10, "bold"), fg="#f1c40f", bg="#34495e")
            err_frame.pack(fill="x", pady=5)
            tk.Label(err_frame, text=solution, justify="left", font=("Segoe UI", 9), fg="white", bg="#34495e", wraplength=520).pack(padx=10, pady=5, anchor="w")

        def on_close():
            root.destroy()
            sys.exit()

        tk.Button(err_win, text="Programm beenden", command=on_close, bg="#c0392b", fg="white", font=("Segoe UI", 10, "bold"), padx=20, pady=5).pack(pady=20)
        
        # Zentrieren
        err_win.update_idletasks()
        x = (err_win.winfo_screenwidth() // 2) - (err_win.winfo_width() // 2)
        y = (err_win.winfo_screenheight() // 2) - (err_win.winfo_height() // 2)
        err_win.geometry(f"+{x}+{y}")
        
        root.wait_window(err_win)
        sys.exit()

class CustomMsgBox(tk.Toplevel):
    """Eigene Neon-Style Yes/No Box."""
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.result = False
        self.overrideredirect(True)
        self.configure(bg='#1a1a1a', highlightbackground="#00f2ff", highlightthickness=2)
        w, h = 400, 250
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{int(sw/2-w/2)}+{int(sh/2-h/2)}")
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.grab_set()
        tk.Label(self, text=title, font=("Segoe UI", 14, "bold"), fg="#00f2ff", bg='#1a1a1a', pady=10).pack()
        tk.Label(self, text=message, font=("Segoe UI", 11), fg="white", bg='#1a1a1a', wraplength=350, pady=20).pack()
        btn_frame = tk.Frame(self, bg='#1a1a1a')
        btn_frame.pack(side="bottom", pady=20)
        tk.Button(btn_frame, text=" JA ", font=("Segoe UI", 10, "bold"), bg="#00f2ff", fg="black",
                  relief="flat", width=12, command=self.yes).pack(side="left", padx=10)
        tk.Button(btn_frame, text=" NEIN ", font=("Segoe UI", 10, "bold"), bg="#333333", fg="white",
                  relief="flat", width=12, command=self.no).pack(side="left", padx=10)

    def yes(self): self.result = True; self.destroy()
    def no(self): self.result = False; self.destroy()

class NeonTraceSplash:
    def __init__(self):
        self.root = tk.Tk()
        self.running = True
        self.root.overrideredirect(True)
        self.root.configure(bg='#0a0a0a')

        w, h = 550, 400 
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{int(sw/2-w/2)}+{int(sh/2-h/2)}")

        self.canvas = tk.Canvas(self.root, width=w, height=h, bg='#0a0a0a', highlightthickness=0)
        self.canvas.pack()

        # UI Elemente
        self.canvas.create_text(w/2 - 30, h/2 - 20, text="Leprendi", font=("Segoe UI", 45, "bold"), fill="#f8f9fa")
        self.wait_text = self.canvas.create_text(w/2, h - 40, text="Ladevorgang...", font=("Segoe UI", 12, "italic"), fill="#555555")

        cx, cy = w/2 + 130, h/2 - 20
        s = 35  

        self.canvas.create_line(cx-s, cy-s, cx+s, cy+s, fill="#1a1a1a", width=15, capstyle="round")
        self.canvas.create_line(cx+s, cy-s, cx-s, cy+s, fill="#1a1a1a", width=15, capstyle="round")

        self.points = [(cx-s, cy-s), (cx+s, cy+s), (cx+s, cy-s), (cx-s, cy+s)]
        self.dot = self.canvas.create_oval(0,0,0,0, fill="#00f2ff", outline="#70f3ff", width=2)
        
        self.trail_length = 12 
        self.trail_dots = [self.canvas.create_oval(0,0,0,0, fill="#004d4d", outline="") for _ in range(self.trail_length)]
        self.history = []

        self.update_checked = False
        self.final_action_done = False # Neu: Merker für die letzte Sekunde
        self.start_time = time.time()
        self.animate()
        self.root.mainloop()
        

    

    def get_local_version(self):
        try:
            with open("version.txt", "r") as f:
                v = f.read().strip()
                print(f"[DEBUG] Lokale Version: {v}")
                return v
        except:
            return "0.0.0"

    def check_for_updates(self):
        print("\n--- UPDATE CHECK ---")
        if not check_internet_connection():
            print("[DEBUG] Keine Internetverbindung. Update-Check übersprungen.")
            print("--- CHECK BEENDET ---\n")
            return

        local_v = self.get_local_version()
        force_update = "--force-update" in sys.argv
        try:
            headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
            response = requests.get(API_URL, headers=headers, timeout=5)
            if response.status_code == 200:
                release = response.json()
                latest_tag = release.get('tag_name', '').replace('v', '')
                clean_local = local_v.replace('v', '')
                
                def to_tup(v): return tuple(map(int, v.split('.')))
                
                print(f"[DEBUG] Vergleich: GitHub({latest_tag}) vs Lokal({clean_local})")
                if force_update or to_tup(latest_tag) > to_tup(clean_local):
                    print(f"[DEBUG] Update {'erzwungen' if force_update else 'verfügbar'}!")
                    
                    # Prüfen, ob wir vom Admin-Neustart kommen (um doppelte Abfrage zu vermeiden)
                    auto_install = "--admin-restart" in sys.argv
                    should_install = False

                    if auto_install or force_update:
                        should_install = True
                    else:
                        self.root.attributes('-topmost', False)
                        msg = CustomMsgBox(self.root, "Update verfügbar", f"Neu: {latest_tag}\nLokal: {local_v}\nJetzt herunterladen & installieren?")
                        self.root.wait_window(msg)
                        should_install = msg.result

                    if should_install: 
                        # Admin-Rechte anfordern, falls noch nicht vorhanden
                        if not is_admin():
                            try:
                                params = "--admin-restart"
                                if getattr(sys, 'frozen', False):
                                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
                                else:
                                    # Argumente für Skript: "script.py" --admin-restart
                                    script_args = f'"{os.path.abspath(sys.argv[0])}" {params}'
                                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, script_args, None, 1)
                                self.root.destroy()
                                sys.exit()
                            except Exception as e:
                                print(f"[ERROR] Admin-Rechte konnten nicht angefordert werden: {e}")
                                return

                        # Asset suchen
                        target_file = "LeprendiX_Win64.exe"
                        assets = release.get('assets', [])
                        asset_url = next((a['url'] for a in assets if a['name'] == target_file), None)
                        
                        if asset_url:
                            self.download_and_install(asset_url, target_file)
                        else:
                            messagebox.showerror("Fehler", f"Datei '{target_file}' nicht im Release gefunden.")
                            webbrowser.open(RELEASE_PAGE)
                            self.root.destroy()
                            sys.exit()
                else:
                    print("[DEBUG] Kein Update nötig (Lokal >= GitHub).")
        except Exception as e:
            print(f"[DEBUG] Fehler beim Update-Check: {e}")
        print("--- CHECK BEENDET ---\n")

    def download_and_install(self, url, filename):
        dl_win = tk.Toplevel(self.root)
        dl_win.title("Update Download")
        w, h = 400, 180
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        dl_win.geometry(f"{w}x{h}+{int(sw/2-w/2)}+{int(sh/2-h/2)}")
        dl_win.configure(bg='#1a1a1a')
        dl_win.attributes("-topmost", True)
        dl_win.grab_set()

        lbl = tk.Label(dl_win, text="Starte Download...", font=("Segoe UI", 10), fg="white", bg='#1a1a1a')
        lbl.pack(pady=(20, 5))
        
        detail_lbl = tk.Label(dl_win, text="Initialisiere...", font=("Segoe UI", 9), fg="#aaaaaa", bg='#1a1a1a')
        detail_lbl.pack(pady=(0, 10))

        pb = ttk.Progressbar(dl_win, orient="horizontal", length=300, mode="determinate")
        pb.pack(pady=10)
        dl_win.update()

        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/octet-stream"}
        save_path = os.path.join(os.getcwd(), filename)

        start_time = time.time()

        try:
            with requests.get(url, headers=headers, stream=True) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                dl = 0
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        dl += len(chunk)
                        f.write(chunk)
                        if total:
                            perc = int(dl/total*100)
                            pb['value'] = perc
                            
                            # Details berechnen (MB und Geschwindigkeit)
                            elapsed = time.time() - start_time
                            dl_mb = dl / (1024 * 1024)
                            total_mb = total / (1024 * 1024)
                            speed_str = "0 KB/s"
                            if elapsed > 0:
                                speed = (dl / 1024) / elapsed
                                speed_str = f"{speed/1024:.2f} MB/s" if speed > 1024 else f"{speed:.0f} KB/s"

                            lbl.config(text=f"Herunterladen: {perc}%")
                            detail_lbl.config(text=f"{dl_mb:.2f} MB / {total_mb:.2f} MB @ {speed_str}")
                            dl_win.update()
            
            lbl.config(text="Sichere Datenbank...")
            dl_win.update()
            self.create_db_backup(parent=dl_win)
            
            lbl.config(text="Installiere Update...")
            dl_win.update()
            time.sleep(1)
            
            # Batch-Skript erstellen für nahtloses Update (Warten -> Installieren -> Neustart)
            bat_path = os.path.join(os.getcwd(), "update_runner.bat")
            # Nur im kompilierten Zustand neu starten, um Dev-Loops zu vermeiden
            app_exe = sys.executable if getattr(sys, 'frozen', False) else None
            
            with open(bat_path, "w") as bat:
                bat.write("@echo off\n")
                bat.write("timeout /t 1 /nobreak > NUL\n") # Nur kurz warten, Installer übernimmt das Timing mit Splash
                bat.write(f'"{save_path}" /S\n')           # Installer SILENT ausführen
                if app_exe:
                    bat.write(f'start "" "{app_exe}"\n')   # App neu starten
                bat.write(f'del "{save_path}"\n')          # Installer aufräumen
                bat.write('del "%~f0"\n')                  # Batch-Skript selbst löschen

            # Batch-Datei komplett versteckt ausführen (CREATE_NO_WINDOW = 0x08000000)
            subprocess.Popen(["cmd.exe", "/C", bat_path], creationflags=0x08000000)
            
            self.root.destroy()
            sys.exit()
        except Exception as e:
            messagebox.showerror("Fehler", f"Download fehlgeschlagen: {e}")
            dl_win.destroy()

    def create_db_backup(self, parent=None):
        """Erstellt ein Backup der patienten.db vor dem Update."""
        if os.path.exists("patienten.db"):
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                try:
                    os.makedirs(backup_dir)
                except OSError as e:
                    print(f"[ERROR] Konnte Backup-Ordner nicht erstellen: {e}")
                    return

            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup_name = f"patienten_backup_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_name)

            try:
                shutil.copy2("patienten.db", backup_path)
                print(f"[INFO] Backup erstellt: {backup_path}")
                self.cleanup_old_backups(backup_dir)
            except Exception as e:
                print(f"[ERROR] Backup fehlgeschlagen: {e}")
                messagebox.showwarning("Backup Warnung", f"Konnte kein Backup der Datenbank erstellen:\n{e}\nDas Update wird trotzdem fortgesetzt.", parent=parent)

    def cleanup_old_backups(self, backup_dir):
        """Behält nur die neuesten 5 Backups, löscht ältere."""
        try:
            files = glob.glob(os.path.join(backup_dir, "patienten_backup_*.db"))
            # Sortieren nach Änderungsdatum (älteste zuerst)
            files.sort(key=os.path.getmtime)
            
            # Wenn mehr als 5, die ältesten löschen (Rotation)
            if len(files) > 5:
                for f in files[:-5]:
                    try:
                        os.remove(f)
                        print(f"[INFO] Altes Backup gelöscht: {f}")
                    except OSError as e:
                        print(f"[WARNUNG] Konnte altes Backup nicht löschen: {e}")
        except Exception as e:
            print(f"[ERROR] Fehler beim Bereinigen der Backups: {e}")

    def final_action(self):
        """Wird 1 Sekunde vor dem Ende ausgeführt."""
        print("[DEBUG] Bereite Start vor...")
        self.running = False  # Animation stoppen
        self.root.destroy()
        print("[DEBUG] Splash-Screen geschlossen.")

    def animate(self):
        if not self.running or not self.canvas.winfo_exists():
            return
        
        try:
            elapsed = time.time() - self.start_time

            # 1. Update Check nach 3 Sekunden
            if not self.update_checked and elapsed > 3.0:
                self.update_checked = True
                self.canvas.itemconfig(self.wait_text, text="Prüfe auf Updates...")
                self.check_for_updates()
                self.canvas.itemconfig(self.wait_text, text="Bitte warten...")

            # 2. Finale Aktion genau 1 Sekunde vor dem Ende (bei 8.5s)
            if not self.final_action_done and elapsed > 8.5:
                self.final_action_done = True
                self.final_action()
                return

            # 3. Programm beenden nach 9.5s
            if elapsed > 9.5: 
                print("[DEBUG] Splash beendet.")
                self.root.destroy()
                return

            # Animation (Langsam)
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

            if self.running and self.root.winfo_exists():
                self.root.after(30, self.animate)
        
        except (tk.TclError, AttributeError):
            # Falls während der Berechnung das Fenster geschlossen wurde
            self.running = False

if __name__ == "__main__":
    if "--crash-handler" in sys.argv:
        crash_handler.main()
        sys.exit(0)
        
    # Check für Migrations-Modus (Admin-Prozess)
    if "--migrate-cleanup" in sys.argv:
        migrate_legacy.perform_cleanup()
        sys.exit(0)

    if not check_single_instance():
        # Prüfen, ob der Nutzer die existierende Instanz beenden möchte
        response = ctypes.windll.user32.MessageBoxW(
            0, 
            "LeprendiX läuft bereits!\nMöchten Sie die bestehende Instanz beenden und neu starten?", 
            "LeprendiX läuft bereits", 
            0x04 | 0x30 | 0x40000 # MB_YESNO | MB_ICONWARNING | MB_TOPMOST
        )
        
        if response == 6: # IDYES
            try:
                my_pid = os.getpid()
                if getattr(sys, 'frozen', False):
                    exe_name = os.path.basename(sys.executable)
                    subprocess.Popen(f'taskkill /F /IM "{exe_name}" /FI "PID ne {my_pid}"', shell=True, creationflags=0x08000000).wait()
                else:
                    cmd = f"wmic process where \"name='python.exe' and commandline like '%start.py%' and ProcessId!={my_pid}\" call terminate"
                    subprocess.Popen(cmd, shell=True, creationflags=0x08000000).wait()
                
                if _mutex_handle:
                    ctypes.windll.kernel32.CloseHandle(_mutex_handle)
                    _mutex_handle = None
                
                time.sleep(1)
                
                if not check_single_instance():
                    ctypes.windll.user32.MessageBoxW(0, "Konnte die alte Instanz nicht vollständig beenden.", "Fehler", 0x10)
                    sys.exit(0)
            except Exception as e:
                ctypes.windll.user32.MessageBoxW(0, f"Fehler beim Beenden: {e}", "Fehler", 0x10)
                sys.exit(0)
        else:
            sys.exit(0)

    cleanup_old_installers()
    
    # Prüfen auf alte Installation und ggf. Migration anstoßen
    if migrate_legacy.check_and_migrate():
        sys.exit(0)
    
    check_system_integrity()
    NeonTraceSplash()
    
    # Nach dem Splash-Screen (wenn mainloop beendet ist):
    print("[DEBUG] Starte Hauptprogramm...")
    try:
        import main
        main.create_main()
    except Exception as e:
        import traceback
        err_msg = f"Kritischer Fehler beim Start:\n{e}\n\n{traceback.format_exc()}"
        print(err_msg)
        ctypes.windll.user32.MessageBoxW(0, err_msg, "LeprendiX Start-Fehler", 0x10)