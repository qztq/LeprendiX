# main.py
# Startscript mit Auswahl-Menü, Splashscreen, Auto-Update und DB-Setup-Button.

import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import os
import requests
import zipfile
import shutil
import sys
import getpass 

# --- PIL (Pillow) für PNG/JPG-Unterstützung ---
try:
    from PIL import Image, ImageTk
    USE_PIL = True
except ImportError:
    USE_PIL = False

# --- KONFIGURATION FÜR DEN UPDATER ---
GITHUB_TOKEN = "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" 
REPO_OWNER = "qztq"
REPO_NAME = "LeprendiX"
RELEASE_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
DB_FILE_TO_EXCLUDE = "patienten.db" 
TEMP_ZIP_NAME = "update_release.zip"

# --- SICHERHEIT: Passwort für DB-Setup ---
SETUP_PASSWORD = "Afrika1!" 

# --- BILD-KONFIGURATION ---
LOGO_PATH = "logo.png" 
TARGET_IMAGE_WIDTH = 800  
TARGET_IMAGE_HEIGHT = 450 

# Globale Variable für das Bild (verhindert Garbage Collection)
logo_image = None
# Globaler Frame für Status und Titel
top_info_frame = None


# --- HILFSFUNKTIONEN FÜR DEN UPDATER (Unverändert) ---

def get_current_version():
    """Liest die aktuelle Version aus einer lokalen Datei (falls vorhanden)."""
    try:
        with open("version.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "v0.0.0" 

def update_current_version(new_version):
    """Speichert die neue Versionsnummer in einer lokalen Datei."""
    try:
        with open("version.txt", "w") as f:
            f.write(new_version)
    except Exception as e:
        print(f"Fehler beim Speichern der Versionsnummer: {e}")

def check_for_updates(root):
    """Prüft auf GitHub, ob eine neue Version verfügbar ist."""
    current_version = get_current_version()
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(RELEASE_API_URL, headers=headers)
        response.raise_for_status()
        
        release_data = response.json()
        latest_version = release_data.get("tag_name")
        zip_asset = next((asset for asset in release_data.get("assets", []) if asset["name"].endswith(".zip")), None)
        
        if not latest_version or not zip_asset:
            return False

        if latest_version > current_version:
            if messagebox.askyesno("Update verfügbar", 
                                  f"Eine neue Version ({latest_version}) ist verfügbar. Aktuell: {current_version}.\nJetzt herunterladen und installieren?"):
                download_url = zip_asset["browser_download_url"]
                download_headers = {"Authorization": f"token {GITHUB_TOKEN}"} 
                
                if download_and_replace(download_url, download_headers, latest_version):
                    root.destroy()
                    messagebox.showinfo("Update Erfolgreich", "Update abgeschlossen. Die Anwendung wird jetzt neu gestartet.")
                    os.execl(sys.executable, sys.executable, *sys.argv)
                return True 
            else:
                return False 
        else:
            return False

    except requests.exceptions.HTTPError as e:
        if e.response.status_code in [404, 401]:
            error_msg = "Prüfen Sie Token und Repository-Namen." if e.response.status_code == 401 else "Release nicht gefunden."
            print(f"WARNUNG: Konnte Update nicht prüfen (HTTP {e.response.status_code}). {error_msg}")
        else:
            print(f"WARNUNG: Ein Fehler ist aufgetreten: {e}")
        return False
    except Exception as e:
        print(f"WARNUNG: Ein unbekannter Fehler beim Update-Check: {e}")
        return False

def download_and_replace(url, headers, new_version):
    """Lädt die ZIP-Datei herunter, entpackt und ersetzt die Dateien."""
    try:
        r = requests.get(url, headers=headers, stream=True)
        r.raise_for_status()

        with open(TEMP_ZIP_NAME, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
            
        with zipfile.ZipFile(TEMP_ZIP_NAME, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if DB_FILE_TO_EXCLUDE not in member and not member.endswith('/'):
                    base_filename = member.split('/', 1)[-1] 
                    
                    if base_filename:
                        source = zip_ref.open(member)
                        target_path = os.path.join(os.getcwd(), base_filename)
                        
                        with open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)

        os.remove(TEMP_ZIP_NAME)
        update_current_version(new_version)
        return True

    except Exception as e:
        messagebox.showerror("Download/Installations Fehler", f"Fehler beim Installieren des Updates: {e}")
        if os.path.exists(TEMP_ZIP_NAME):
            os.remove(TEMP_ZIP_NAME)
        return False

# --- HILFSFUNKTIONEN FÜR DB-SETUP (Unverändert) ---

def run_db_setup_protected():
    # ... (DB-Setup Logik wie zuvor)
    if not messagebox.askyesno("Sicherheit: DB-Setup", 
                              "WARNUNG: Das Ausführen des DB-Setup überschreibt oder löscht ALLE Stammdaten und Leistungen!\n\nSind Sie ABSOLUT sicher, dass Sie fortfahren möchten?"):
        return
        
    password_window = tk.Toplevel()
    password_window.title("Sicherheits-Passwort")
    
    password_window.update_idletasks()
    width = 300
    height = 120
    x = (password_window.winfo_screenwidth() // 2) - (width // 2)
    y = (password_window.winfo_screenheight() // 2) - (height // 2)
    password_window.geometry(f'{width}x{height}+{x}+{y}')
    
    ttk.Label(password_window, text="Bitte geben Sie das Master-Passwort ein:").pack(padx=10, pady=5)
    password_entry = ttk.Entry(password_window, show="*", width=30)
    password_entry.pack(padx=10, pady=5)
    password_entry.focus_set()
    
    def check_password_and_run():
        entered_password = password_entry.get()
        if entered_password == SETUP_PASSWORD:
            password_window.destroy()
            execute_db_setup()
        else:
            messagebox.showerror("Fehler", "Falsches Passwort.")

    ttk.Button(password_window, text="Bestätigen", command=check_password_and_run).pack(pady=5)
    password_window.bind('<Return>', lambda event: check_password_and_run())

def execute_db_setup():
    """Führt das externe db_setup.py Skript aus."""
    try:
        process = subprocess.run([sys.executable, "db_setup.py"], 
                                 capture_output=True, 
                                 text=True, 
                                 check=True)
        
        messagebox.showinfo("DB-Setup Erfolg", 
                            f"Datenbank-Setup erfolgreich ausgeführt.\n\nAusgabe:\n{process.stdout}")
        
        os.execl(sys.executable, sys.executable, *sys.argv)
        
    except subprocess.CalledProcessError as e:
        messagebox.showerror("DB-Setup Fehler", 
                             f"Fehler beim Ausführen von db_setup.py:\n\n{e.stderr}\n\nBitte Konsole prüfen.")
    except FileNotFoundError:
        messagebox.showerror("DB-Setup Fehler", "Das Skript 'db_setup.py' wurde nicht gefunden.")
    except Exception as e:
        messagebox.showerror("DB-Setup Fehler", f"Ein unbekannter Fehler ist aufgetreten: {e}")


# --- GUI (Start) ---

def show_splashscreen():
    """Zeigt den Splashscreen an und initialisiert die Haupt-GUI."""
    splash = tk.Tk()
    splash.title("LeprendiX Start")
    
    # --- Geometrie: Breit (900x600) ---
    window_width = 900
    window_height = 600
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    splash.geometry(f'{window_width}x{window_height}+{x}+{y}')
    splash.resizable(False, False)

    # --- 1. Großes Bild (Logo) ---
    # Wir platzieren das Bild direkt über place/pack, nicht in einem Haupt-Frame
    image_label = ttk.Label(splash)
    image_label.pack(pady=(10, 0)) # Nur ein kleiner Rand oben
    
    global logo_image 
    
    if os.path.exists(LOGO_PATH):
        try:
            if USE_PIL:
                img = Image.open(LOGO_PATH)
                img = img.resize((TARGET_IMAGE_WIDTH, TARGET_IMAGE_HEIGHT), Image.Resampling.LANCZOS)
                logo_image = ImageTk.PhotoImage(img)
            else:
                logo_image = tk.PhotoImage(file=LOGO_PATH)
                
            image_label.config(image=logo_image)
            
        except Exception as e:
            # Fallback bei Fehler: Großer Text
            image_label.config(text="LeprendiX - Fehler beim Laden des Bildes", font=("Helvetica", 16, "bold"))
    else:
        # Fallback bei fehlender Datei: Großer Text
        image_label.config(text="LeprendiX - (Logo fehlt)", font=("Helvetica", 16, "bold"))
        
    # --- 2. Status und Version (unter dem Bild, zentriert) ---
    # Verwenden Sie ein Label, um den Titel anzuzeigen (falls das Bild fehlt) oder einfach den Untertitel
    title_label = ttk.Label(splash, text="Honorarnoten Generator", font=("Helvetica", 12))
    title_label.pack(pady=(0, 5))
    
    status_label = ttk.Label(splash, text="Prüfe auf Updates...", foreground='blue')
    status_label.pack(pady=5)
    
    # Hier werden die Buttons in start_application_buttons über place gesetzt
    
    # Wir nutzen after, damit die GUI Zeit hat, sich zu rendern.
    splash.after(100, lambda: start_application_buttons(splash, status_label))
    
    splash.mainloop()

def start_application_buttons(splash, status_label):
    """Führt den Update-Check durch und zeigt die Haupt-Buttons an."""
    
    # Prüfe auf Updates 
    if check_for_updates(splash):
        return 

    # Update abgeschlossen oder ignoriert
    status_label.config(text=f"Bereit zum Start. Version: {get_current_version()}")
    
    # --- 3. Haupt-Buttons (zentral unten platziert) ---
    
    # Relativer Y-Wert: ca. 85% der Höhe des Fensters (unten)
    # Relativer X-Wert: Mitte des Fensters (0.5)
    
    start_btn = ttk.Button(splash, 
                           text="App Starten", 
                           command=lambda: start_gui(splash), 
                           width=15)
                           
    beenden_btn = ttk.Button(splash, 
                             text="Beenden", 
                             command=splash.destroy, 
                             width=15)
                             
    # Platzieren Sie die Buttons nebeneinander (relx=0.5 zentriert, dann Korrektur durch Anker)
    start_btn.place(relx=0.5, rely=0.85, anchor=tk.CENTER, x=-70) # 70px links der Mitte
    beenden_btn.place(relx=0.5, rely=0.85, anchor=tk.CENTER, x=70) # 70px rechts der Mitte

    # --- 4. DB-Setup Button (Admin) in der Ecke ---
    db_setup_btn = ttk.Button(splash, 
                              text="DB-Setup (Admin)", 
                              command=run_db_setup_protected)
                              
    # Platziere den Button in der linken unteren Ecke (rely=0.90, relx=0.03)
    db_setup_btn.place(relx=0.03, rely=0.90, anchor='sw')


# Auszug aus main.py (nur die Funktion start_gui ist relevant)

def start_gui(splash):
    """Startet die Haupt-GUI (gui_generator.py) und das Verlaufsfenster."""
    splash.destroy()
    
    # 1. Start des Hauptprogramms (gui_generator.py)
    try:
        # Führen Sie gui_generator.py im Hintergrund aus
        subprocess.Popen([sys.executable, "gui_generator.py"], start_new_session=True)
    except FileNotFoundError:
        messagebox.showerror("Fehler", "Das Skript 'gui_generator.py' wurde nicht gefunden.")
        return
    except Exception as e:
        messagebox.showerror("Fehler", f"Hauptprogramm konnte nicht gestartet werden: {e}")
        return
        
    # 2. Start des Verlaufsfensters (verlauf_fenster.py) im selben Prozess
    try:
        # Starte das Verlaufsfenster über subprocess, um es als unabhängigen Prozess zu starten
        # oder verwenden Sie den tk.Toplevel Ansatz aus verlauf_fenster.py
        
        # WICHTIG: Wenn gui_generator.py eine Tkinter-Anwendung ist,
        # dann sollte auch verlauf_fenster.py ein Teil davon sein (via Toplevel)
        # oder als eigenständiger Prozess gestartet werden.

        # Da wir bereits den Haupt-Splashscreen geschlossen haben (splash.destroy()), 
        # nutzen wir hier den einfachen Popen-Ansatz für zwei parallele Prozesse:
        subprocess.Popen([sys.executable, "verlauf_fenster.py"], start_new_session=True)
        
    except FileNotFoundError:
        messagebox.showwarning("Warnung", "Das Skript 'verlauf_fenster.py' wurde nicht gefunden.")
    except Exception as e:
        messagebox.showwarning("Warnung", f"Verlaufsfenster konnte nicht gestartet werden: {e}")
        
    # main.py beendet sich hier, da die Kindprozesse laufen


# --- MAIN ---
if __name__ == "__main__":
    show_splashscreen()