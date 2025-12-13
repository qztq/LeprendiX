# main.py
# Startscript mit breitem Splashscreen, Auto-Update, geschütztem DB-Setup
# und parallelem Start von Haupt-App und Status-Checker.

import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import os
import requests
import zipfile
import shutil
import sys
import getpass 
import tkinter

# --- PIL (Pillow) für PNG/JPG-Unterstützung ---\r\n
try:
    from PIL import Image, ImageTk
    USE_PIL = True
except ImportError:
    USE_PIL = False

# --- KONFIGURATION FÜR DEN UPDATER ---\r\n
GITHUB_TOKEN = "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" 
REPO_OWNER = "qztq"
REPO_NAME = "LeprendiX"
RELEASE_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
DB_FILE_TO_EXCLUDE = "patienten.db" 
TEMP_ZIP_NAME = "update_release.zip"

# --- SICHERHEIT: Passwort für DB-Setup ---\r\n
SETUP_PASSWORD = "Afrika1!" 

# --- BILD-KONFIGURATION ---\r\n
LOGO_PATH = "logo.png" 
TARGET_IMAGE_WIDTH = 750 
TARGET_IMAGE_HEIGHT = 400 

# Globale Variablen für das...\r\n
global_logo_image = None
global_logo_photo = None

# --- UPDATE FUNKTIONEN (Unverändert) ---

def check_for_update(splash):
    """
    Überprüft die neueste Release auf GitHub und fragt den Nutzer, ob er updaten möchte.
    """
    splash.update_label.config(text="Suche nach Updates...")
    try:
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        response = requests.get(RELEASE_API_URL, headers=headers, timeout=10)
        
        if response.status_code != 200:
            splash.update_label.config(text=f"Update-Prüfung fehlgeschlagen: HTTP {response.status_code}")
            return False

        release_info = response.json()
        latest_tag = release_info.get('tag_name')
        
        if not latest_tag:
            splash.update_label.config(text="Keine Release gefunden. App ist aktuell.")
            return False

        if messagebox.askyesno("Update gefunden", 
                               f"Eine neue Version ({latest_tag}) ist verfügbar. Möchten Sie jetzt aktualisieren?"):
            update_application(release_info, splash)
            # Das Programm wird nach dem Update neu gestartet oder beendet
            return True
        else:
            splash.update_label.config(text="Update abgelehnt. App ist aktuell.")
            return False

    except requests.exceptions.RequestException as e:
        splash.update_label.config(text=f"Update-Prüfung übersprungen (keine Internetverbindung oder Fehler: {e}).")
        return False
    except Exception as e:
        splash.update_label.config(text=f"Unerwarteter Fehler beim Update-Check: {e}")
        return False

def update_application(release_info, splash):
    """
    Lädt das Release-Asset herunter, entpackt es direkt in das aktuelle Verzeichnis
    und stellt die DB-Datei wieder her (falls sie gesichert werden musste).
    """
    
    assets = release_info.get('assets', [])
    if not assets:
        messagebox.showerror("Fehler", "Kein Asset im neuestem Release gefunden.")
        return

    # Download URL für das Asset (z.B. latest.zip)
    download_url = assets[0]['browser_download_url'] 
    
    splash.update_label.config(text="Lade Update herunter...")
    splash.update()

    # --- 1. Vorbereitung & Temporäres Speichern der DB ---
    db_backup_needed = os.path.exists(DB_FILE_TO_EXCLUDE)
    db_temp_path = DB_FILE_TO_EXCLUDE + ".temp_backup"

    if db_backup_needed:
        try:
            # Kopiere die DB, bevor das Update das Original möglicherweise überschreibt/löscht
            shutil.copy2(DB_FILE_TO_EXCLUDE, db_temp_path)
            print(f"INFO: {DB_FILE_TO_EXCLUDE} wurde temporär gesichert.")
        except Exception as e:
            # Wenn die Sicherung fehlschlägt, ist die Gefahr des Datenverlusts hoch.
            messagebox.showwarning("Warnung", f"Konnte {DB_FILE_TO_EXCLUDE} nicht sichern. Update wird NICHT durchgeführt: {e}")
            return # Update abbrechen, um Datenverlust zu verhindern
        
    try:
        # --- 2. Download der ZIP-Datei ---
        response = requests.get(download_url, stream=True, timeout=300)
        response.raise_for_status()
        with open(TEMP_ZIP_NAME, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # --- 3. Entpacken des Updates ---
        splash.update_label.config(text="Entpacke Dateien...")
        splash.update()
        
        with zipfile.ZipFile(TEMP_ZIP_NAME, 'r') as zip_ref:
            
            members = zip_ref.namelist()
            
            for member in members:
                # 3a. Ignoriere die Datenbank-Datei im ZIP beim Entpacken
                if member == DB_FILE_TO_EXCLUDE or member.endswith('/'):
                    print(f"INFO: Ignoriere {member} (DB oder Verzeichnis).")
                    continue
                
                # 3b. Entpacke alle anderen Dateien direkt ins aktuelle Verzeichnis
                # target_path ist der Dateiname im aktuellen Ordner
                target_path = os.path.join(os.getcwd(), os.path.basename(member))
                
                # Stelle sicher, dass der Zielordner existiert (falls es Unterverzeichnisse gibt)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                # Extrahiere die Datei
                source = zip_ref.open(member)
                target = open(target_path, "wb")
                with source, target:
                    shutil.copyfileobj(source, target)
        
        # --- 4. Aufräumen des Downloads ---
        os.remove(TEMP_ZIP_NAME)
        
        # --- 5. Wiederherstellung der DB ---
        if db_backup_needed and os.path.exists(db_temp_path):
            # Verschiebe die gesicherte DB zurück, um sie wiederherzustellen (überschreibt evtl. leere DB aus dem Update-Prozess)
            shutil.move(db_temp_path, DB_FILE_TO_EXCLUDE)
            print(f"INFO: {DB_FILE_TO_EXCLUDE} wurde erfolgreich wiederhergestellt.")

        messagebox.showinfo("Update erfolgreich", "Die Anwendung wurde erfolgreich aktualisiert und wird jetzt neu gestartet.")
        # Beende das aktuelle Programm und starte es neu
        python = sys.executable
        os.execl(python, python, *sys.argv)
        
    except Exception as e:
        messagebox.showerror("Update Fehler", f"Fehler beim Aktualisieren: {e}")
    finally:
        # cleanup bei Fehlern
        if os.path.exists(TEMP_ZIP_NAME):
            os.remove(TEMP_ZIP_NAME)
        # Lösche den DB-Backup nur, wenn die Original-DB wiederhergestellt wurde oder der Fehler früh auftrat
        if 'db_temp_path' in locals() and os.path.exists(db_temp_path):
             # Falls der Fehler nach der Sicherung, aber vor der Wiederherstellung auftrat, lösche den Backup.
             # Im Erfolgsfall wurde er bereits nach DB_FILE_TO_EXCLUDE verschoben.
             if not os.path.exists(DB_FILE_TO_EXCLUDE) or os.stat(db_temp_path).st_mtime == os.stat(DB_FILE_TO_EXCLUDE).st_mtime:
                 # Nur löschen, wenn der Backup nicht das Original ist oder das Original bereits wiederhergestellt wurde (gleiche Zeitstempel)
                 pass 
             else:
                 os.remove(db_temp_path)


# --- DB SETUP FUNKTIONEN (Unverändert) ---

def run_db_setup():
    """Startet das db_setup.py Skript."""
    try:
        subprocess.run([sys.executable, "db_setup.py"], check=True)
        messagebox.showinfo("DB Setup", "Datenbank-Setup erfolgreich abgeschlossen.")
    except FileNotFoundError:
        messagebox.showerror("Fehler", "Das Skript 'db_setup.py' wurde nicht gefunden.")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Fehler", f"Fehler beim Ausführen von 'db_setup.py': {e}")
    except Exception as e:
        messagebox.showerror("Fehler", f"Ein unerwarteter Fehler ist aufgetreten: {e}")

def run_db_setup_protected():
    """Fragt nach dem Passwort, bevor das DB-Setup gestartet wird."""
    
    pwd_window = tk.Toplevel()
    pwd_window.title("Admin-Passwort")
    pwd_window.geometry("300x100")
    pwd_window.resizable(False, False)
    
    ttk.Label(pwd_window, text="Bitte Admin-Passwort eingeben:").pack(pady=5)
    
    password_entry = ttk.Entry(pwd_window, show="*")
    password_entry.pack(pady=5)
    password_entry.focus()
    
    def check_password():
        if password_entry.get() == SETUP_PASSWORD:
            pwd_window.destroy()
            run_db_setup()
        else:
            messagebox.showerror("Fehler", "Falsches Passwort.")
            password_entry.delete(0, tk.END)

    pwd_window.bind('<Return>', lambda event=None: check_password())
    
    ttk.Button(pwd_window, text="OK", command=check_password).pack(pady=5)
    pwd_window.transient(tk.Tk.root) 


# --- START FUNKTIONEN (Angepasst: Start-Button) ---

def start_gui(splash):
    """
    Startet die Haupt-GUI (gui_generator.py) und den Status-Checker im parallelen Prozess.
    """
    splash.destroy()
    
    # 1. Start des Hauptprogramms (gui_generator.py)
    try:
        subprocess.Popen([sys.executable, "gui_generator.py"], start_new_session=True)
        print("INFO: 'gui_generator.py' gestartet.")
    except FileNotFoundError:
        messagebox.showerror("Fehler", "Das Skript 'gui_generator.py' wurde nicht gefunden.")
        return
    except Exception as e:
        messagebox.showerror("Fehler", f"Hauptprogramm konnte nicht gestartet werden: {e}")
        return
        
    # 2. Start des Status-Checkers (patient_status_checker.py) im parallelen Prozess
    try:
        subprocess.Popen([sys.executable, "patient_status_checker.py"], start_new_session=True)
        print("INFO: 'patient_status_checker.py' gestartet.")
        
    except FileNotFoundError:
        messagebox.showwarning("Warnung", "Das Skript 'patient_status_checker.py' wurde nicht gefunden. Hauptprogramm läuft weiter.")
        
    except Exception as e:
        messagebox.showerror("Fehler", f"Status-Checker konnte nicht gestartet werden: {e}")
        
    # main.py beendet sich, die gestarteten Prozesse laufen weiter.
    sys.exit()


# --- SPLASHSCREEN (Angepasst: Layout und Start-Button) ---

def create_splash_screen():
    """Erstellt den Splashscreen."""
    
    root = tk.Tk()
    root.withdraw() 
    
    splash = tk.Toplevel(root)
    splash.title("LeprendiX: Honorarnoten-Generator")
    splash.overrideredirect(True) 
    
    SPLASH_WIDTH = 800
    SPLASH_HEIGHT = 550 
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    
    x_pos = (screen_width - SPLASH_WIDTH) // 2
    y_pos = (screen_height - SPLASH_HEIGHT) // 2
    splash.geometry(f"{SPLASH_WIDTH}x{SPLASH_HEIGHT}+{x_pos}+{y_pos}")

    # --- Container Frame für Bild und Info ---
    main_frame = ttk.Frame(splash)
    main_frame.pack(padx=10, pady=10, fill="both", expand=True)

    # --- 1. Bild/Logo ---
    global global_logo_image, global_logo_photo
    
    if USE_PIL and os.path.exists(LOGO_PATH):
        try:
            img = Image.open(LOGO_PATH)
            img = img.resize((TARGET_IMAGE_WIDTH, TARGET_IMAGE_HEIGHT), Image.Resampling.LANCZOS)
            global_logo_image = img 
            global_logo_photo = ImageTk.PhotoImage(global_logo_image)
            
            logo_label = tk.Label(main_frame, image=global_logo_photo, borderwidth=0)
            logo_label.pack(pady=(0, 10)) 

        except Exception as e:
            tk.Label(main_frame, text=f"LOGO FEHLER: {e}", fg="red").pack(pady=10)
    else:
        # Fallback ohne PIL oder wenn das Bild fehlt
        tk.Label(main_frame, text="LeprendiX: Honorarnoten-Generator", 
                 font=("Helvetica", 18, "bold"), fg="blue").pack(pady=10)
    
    # --- 2. Update-Status Label ---
    splash.update_label = ttk.Label(main_frame, 
                                    text="Initialisiere...", 
                                    font=("Arial", 10))
    splash.update_label.pack(pady=(0, 5)) 

    # --- 3. Progressbar ---
    style = ttk.Style()
    style.theme_use('default')
    style.configure("TProgressbar", thickness=10)

    progress = ttk.Progressbar(main_frame, orient="horizontal", length=SPLASH_WIDTH - 40, mode="indeterminate")
    progress.pack(pady=(0, 15), fill='x', padx=50) 
    progress.start(10) 
    
    # --- 4. Start Button ---
    # *KORRIGIERT*: Feste, großzügige Breite und vertikales Padding (ipady) für die Höhe
    splash.start_button = ttk.Button(main_frame, 
                                     text="▶️ Anwendung starten", 
                                     command=lambda: start_gui(splash), 
                                     state=tk.DISABLED,
                                     width=35) # Breite auf 35 Zeichen setzen
                                     
    # Packen: Button zentrieren und vertikalen Innenabstand (ipady) hinzufügen
    # ipady erhöht die Höhe des Buttons
    splash.start_button.pack(pady=(0, 15), ipady=10) 

    # --- 5. DB-Setup Button (Admin) in der Ecke ---
    db_setup_btn = ttk.Button(splash, 
                              text="DB-Setup (Admin)", 
                              command=run_db_setup_protected)
                              
    db_setup_btn.place(relx=0.03, rely=0.97, anchor='sw')

    return root, splash, progress

# --- HAUPTPROGRAMM ---

if __name__ == "__main__":
    
    root, splash, progress = create_splash_screen()
    
    splash.update()
    
    # Führe den Update-Check aus
    if not check_for_update(splash):
        # Wenn kein Update gestartet wurde, stoppe den Progressbar und aktiviere den Start-Button
        progress.stop()
        progress.config(mode="determinate", value=100) 
        splash.update_label.config(text="Bereit zum Start.")
        splash.start_button.config(state=tk.NORMAL)
        
    root.mainloop()