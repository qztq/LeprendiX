import tkinter as tk
from tkinter import ttk
import sys
import os
import subprocess
import json
import webbrowser
import urllib.parse
import traceback
import logging
# Design-Konstanten (passend zu LeprendiX)
COLOR_PRIMARY = "#2c3e50"
COLOR_SECONDARY = "#34495e"
COLOR_ACCENT = "#e74c3c" # Rot für Fehler
COLOR_TEXT = "#ecf0f1"

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
CRASH_FILE = os.path.join(BASE_DIR, "last_crash.txt")

def restart_program(root):
    """Versucht, start.py oder main.py neu zu starten."""
    root.destroy()
    
    if getattr(sys, 'frozen', False):
        try:
            subprocess.Popen([sys.executable])
        except Exception as e:
            print(f"Fehler beim Neustart: {e}")
        sys.exit(0)
    
    # Versuche start.py zu finden (Launcher)
    script_to_run = os.path.join(BASE_DIR, "start.py")
    if not os.path.exists(script_to_run):
        script_to_run = os.path.join(BASE_DIR, "main.py")
    
    if os.path.exists(script_to_run):
        try:
            if sys.platform == "win32":
                # Unter Windows ohne Fenster starten (CREATE_NO_WINDOW = 0x08000000)
                subprocess.Popen([sys.executable, script_to_run], creationflags=0x08000000)
            else:
                subprocess.Popen([sys.executable, script_to_run])
        except Exception as e:
            print(f"Fehler beim Neustart: {e}")
    sys.exit(0)

def close_program():
    sys.exit(0)

def send_and_restart(root, error_text):
    """Öffnet das Standard-Mailprogramm und startet dann neu."""
    recipient = "starbright-games@gmx.at"
    subject = "LeprendiX Crash Report"
    
    # Text kürzen für URL-Limit (ca 1500 Zeichen sicherheitshalber)
    body = f"Automatischer Fehlerbericht:\n\n{error_text}"
    if len(body) > 1500:
        body = body[:1500] + "\n... (gekürzt)"
        
    # URL Encoding
    params = {
        "subject": subject,
        "body": body
    }
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    mailto_link = f"mailto:{recipient}?{query_string}"
    
    try:
        webbrowser.open(mailto_link)
    except Exception as e:
        print(f"Konnte Mail-Programm nicht öffnen: {e}")
        
    restart_program(root)

def start_crash_handler_process():
    """Startet den Crash-Handler als neuen unabhängigen Prozess."""
    if getattr(sys, 'frozen', False):
        try:
            subprocess.Popen([sys.executable, "--crash-handler"])
        except Exception as e:
            print(f"Konnte Crash-Handler nicht starten: {e}")
    else:
        # Wir nehmen an, dass crash_handler.py im selben Verzeichnis liegt
        script_path = os.path.abspath(__file__)
        if os.path.exists(script_path):
            try:
                subprocess.Popen([sys.executable, script_path])
            except Exception as e:
                print(f"Konnte Crash-Handler nicht starten: {e}")

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Globaler Exception Handler, der von start.py und main.py genutzt wird."""
    # 1. Logging (falls konfiguriert)
    try:
        logging.critical("KRITISCHER ABSTURZ", exc_info=(exc_type, exc_value, exc_traceback))
    except:
        pass

    # 2. Traceback in Datei speichern
    try:
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        with open(CRASH_FILE, "w", encoding="utf-8") as f:
            f.write(err_msg)
    except Exception as e:
        print(f"Konnte Crash-Log nicht schreiben: {e}")

    # 3. GUI starten
    start_crash_handler_process()

    # 4. Beenden
    sys.exit(1)

def install_exception_handler():
    sys.excepthook = global_exception_handler

def main():
    root = tk.Tk()
    root.title("LeprendiX Crash Handler")
    root.geometry("700x500")
    root.configure(bg=COLOR_PRIMARY)

    # Icon laden falls vorhanden
    try:
        icon_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(icon_path):
            img = tk.PhotoImage(file=icon_path)
            root.iconphoto(False, img)
    except:
        pass

    # Header
    header_frame = tk.Frame(root, bg=COLOR_ACCENT, pady=10)
    header_frame.pack(fill="x")
    tk.Label(header_frame, text="A LeprendiX Process has crashed", font=("Segoe UI", 16, "bold"), 
             bg=COLOR_ACCENT, fg="white").pack()
    tk.Label(header_frame, text="Es ist ein unerwarteter Fehler aufgetreten.", font=("Segoe UI", 10), 
             bg=COLOR_ACCENT, fg="white").pack()

    # Fehlerbericht Bereich
    content_frame = tk.Frame(root, bg=COLOR_PRIMARY, padx=20, pady=20)
    content_frame.pack(fill="both", expand=True)

    tk.Label(content_frame, text="Fehlerdetails:", font=("Segoe UI", 10, "bold"), 
             bg=COLOR_PRIMARY, fg=COLOR_TEXT, anchor="w").pack(fill="x", pady=(0, 5))

    text_area = tk.Text(content_frame, height=15, bg=COLOR_SECONDARY, fg="#ffcccc", 
                        font=("Consolas", 9), relief="flat", padx=10, pady=10)
    text_area.pack(fill="both", expand=True)

    # Scrollbar für Textarea
    scrollbar = ttk.Scrollbar(text_area, command=text_area.yview)
    text_area['yscrollcommand'] = scrollbar.set
    scrollbar.pack(side="right", fill="y")

    # Fehler laden
    if os.path.exists(CRASH_FILE):
        with open(CRASH_FILE, "r", encoding="utf-8") as f:
            error_content = f.read()
            text_area.insert("1.0", error_content)
    else:
        error_content = "Keine Fehlerdetails gefunden."
        text_area.insert("1.0", error_content)
    
    text_area.config(state="disabled") # Read-only

    # Buttons
    btn_frame = tk.Frame(root, bg=COLOR_PRIMARY, pady=20)
    btn_frame.pack(fill="x")

    tk.Button(btn_frame, text="Schließen", command=close_program, 
              bg=COLOR_SECONDARY, fg="white", font=("Segoe UI", 11), relief="flat", padx=20, pady=10).pack(side="left", padx=20)
    
    tk.Button(btn_frame, text="LeprendiX Neustarten", command=lambda: restart_program(root), 
              bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"), relief="flat", padx=20, pady=10).pack(side="left", padx=20)

    tk.Button(btn_frame, text="Absturzbericht Senden und Neustarten", command=lambda: send_and_restart(root, error_content), 
              bg="#3498db", fg="white", font=("Segoe UI", 11), relief="flat", padx=20, pady=10).pack(side="left", padx=20)

    root.mainloop()

if __name__ == "__main__":
    main()
