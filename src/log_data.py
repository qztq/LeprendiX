# log_data.py

import datetime
import os

# Datei, in der der Verlauf gespeichert wird
LOG_FILE = 'honorarnoten_verlauf.txt'

def log_patient_name(patient_identifier):
    """
    Protokolliert den Namen des Patienten und den Zeitpunkt der Erstellung
    einer Honorarnote in einer einfachen Textdatei (honorarnoten_verlauf.txt).
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] Honorarnote generiert für: {patient_identifier}\n"
    
    try:
        # 'a' steht für append (anhängen), damit die Datei nicht überschrieben wird
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
            
    except Exception as e:
        # Warnung, falls das Protokollieren fehlschlägt, aber die Hauptanwendung
        # weiterlaufen lassen.
        print(f"WARNUNG: Fehler beim Schreiben in die Log-Datei ({LOG_FILE}): {e}")

# Wenn Sie ein Verlaufsfenster (verlauf_fenster.py) verwenden, benötigt dieses
# Skript diese Datei, um die Daten bereitzustellen.