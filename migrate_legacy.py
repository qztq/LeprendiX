import os
import sys
import shutil
import subprocess
import ctypes
import time
import logging
import tkinter as tk
from tkinter import ttk

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class MigrationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg='#1a1a1a', highlightbackground="#00f2ff", highlightthickness=2)
        
        w, h = 450, 220
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.attributes("-topmost", True)
        
        tk.Label(self.root, text="LeprendiX Migration", font=("Segoe UI", 16, "bold"), fg="#00f2ff", bg='#1a1a1a').pack(pady=(25, 15))
        
        self.status_var = tk.StringVar(value="Initialisiere...")
        tk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 10), fg="white", bg='#1a1a1a').pack(pady=5)
        
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Horizontal.TProgressbar", background="#00f2ff", troughcolor="#333333", bordercolor="#1a1a1a", lightcolor="#00f2ff", darkcolor="#00f2ff")
        
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=350, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(pady=20)
        
        self.root.after(500, self.run_migration)
        self.root.mainloop()

    def run_migration(self):
        log_file = os.path.join(get_base_path(), "migration_log.txt")
        logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s: %(message)s')
        logging.info("Migration gestartet (Admin Mode).")

        try:
            prog_files = os.environ.get("ProgramFiles")
            if not prog_files:
                return

            old_dir = os.path.join(prog_files, "LeprendiX")
            new_dir = get_base_path()
            
            if not os.path.exists(old_dir):
                logging.info("Alter Ordner nicht gefunden. Abbruch.")
                self.root.destroy()
                return

            # 1. Datenbank retten
            self.status_var.set("Sichere Datenbank...")
            self.progress['value'] = 20
            self.root.update()
            
            old_db = os.path.join(old_dir, "patienten.db")
            new_db = os.path.join(new_dir, "patienten.db")

            if os.path.exists(old_db):
                try:
                    logging.info("Alte Datenbank gefunden.")
                    if os.path.exists(new_db):
                        timestamp = int(time.time())
                        backup_path = f"{new_db}.pre_migration_{timestamp}.bak"
                        shutil.move(new_db, backup_path)
                        logging.info(f"Existierende DB gesichert nach: {backup_path}")
                    
                    shutil.copy2(old_db, new_db)
                    logging.info("Datenbank erfolgreich kopiert.")
                except Exception as e:
                    logging.error(f"Fehler beim Verschieben der DB: {e}")

            # 2. Uninstall / Löschen
            self.status_var.set("Entferne alte Installation...")
            self.progress['value'] = 50
            self.root.update()
            
            uninstaller = os.path.join(old_dir, "Uninstall.exe")
            if os.path.exists(uninstaller):
                try:
                    logging.info("Starte Uninstaller...")
                    subprocess.run([uninstaller, "/S", "_?=" + old_dir], check=True)
                except Exception as e:
                    logging.error(f"Uninstaller Fehler: {e}")
            
            # Warten und Reste putzen
            self.status_var.set("Bereinige Dateien...")
            self.progress['value'] = 80
            self.root.update()
            time.sleep(2)
            
            if os.path.exists(old_dir):
                try:
                    logging.info("Lösche verbleibenden Ordner manuell...")
                    shutil.rmtree(old_dir, ignore_errors=True)
                except Exception as e:
                    logging.error(f"Manuelles Löschen fehlgeschlagen: {e}")
            
            self.status_var.set("Migration abgeschlossen!")
            self.progress['value'] = 100
            self.root.update()
            time.sleep(1)
            
            # Neustart mit erzwungenem Update
            logging.info("Starte Anwendung neu mit --force-update...")
            params = ["--force-update"]
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable] + params)
            else:
                start_script = os.path.join(get_base_path(), "start.py")
                subprocess.Popen([sys.executable, start_script] + params)
            
        except Exception as e:
            logging.error(f"Kritischer Fehler: {e}")
        finally:
            self.root.destroy()

def perform_cleanup():
    """
    Wird mit Admin-Rechten ausgeführt (via --migrate-cleanup).
    Startet die GUI für die Migration.
    """
    MigrationGUI()

def check_and_migrate():
    """
    Prüft vom User-Prozess aus, ob eine Migration nötig ist.
    Gibt True zurück, wenn eine Migration angestoßen wurde (Admin-Prompt).
    """
    prog_files = os.environ.get("ProgramFiles")
    if not prog_files: return False
    
    old_dir = os.path.join(prog_files, "LeprendiX")
    
    # Wir prüfen: Existiert der alte Ordner UND sind wir NICHT selbst im alten Ordner?
    if os.path.exists(old_dir):
        current_exe = os.path.normpath(sys.executable if getattr(sys, 'frozen', False) else __file__)
        if not current_exe.startswith(os.path.normpath(old_dir)):
            print("[INFO] Alte Installation entdeckt. Starte Migration...")
            ctypes.windll.user32.MessageBoxW(0, "Eine alte Installation wurde gefunden.\nDie Daten werden nun migriert.", "LeprendiX Migration", 0x40)
            try:
                params = "--migrate-cleanup"
                if getattr(sys, 'frozen', False):
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
                else:
                    script = sys.argv[0]
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
                return True
            except Exception as e:
                print(f"Konnte Migration nicht starten: {e}")
    return False
