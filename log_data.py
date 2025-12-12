# log_data.py
# Funktionen zum Speichern und Laden des Verlaufs der zuletzt bearbeiteten Patienten.

import os

LOG_FILE = "verlauf.txt"
MAX_ENTRIES = 10 # Maximale Anzahl der Einträge, die gespeichert werden sollen

def log_patient_name(name: str):
    """
    Speichert den Patientennamen an den Anfang der Verlaufsdatei.
    """
    if not name or not name.strip():
        return

    name = name.strip()
    current_entries = []

    # 1. Vorhandene Einträge laden (außer dem zu loggenden, falls er schon da ist)
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                current_entries = [line.strip() for line in f if line.strip() and line.strip() != name]
        except Exception as e:
            print(f"Fehler beim Lesen der Verlaufsdatei: {e}")

    # 2. Neuen Namen hinzufügen (ganz oben)
    current_entries.insert(0, name)

    # 3. Datei mit den neuesten Einträgen überschreiben (auf MAX_ENTRIES begrenzen)
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            for entry in current_entries[:MAX_ENTRIES]:
                f.write(entry + "\n")
    except Exception as e:
        print(f"Fehler beim Schreiben der Verlaufsdatei: {e}")

def get_recent_patients() -> list:
    """
    Gibt die Liste der zuletzt gespeicherten Patienten zurück.
    """
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []
    return []

# Beispielaufruf (Diesen Aufruf müssten Sie in gui_generator.py integrieren):
# from log_data import log_patient_name
# ... nach erfolgreicher Speicherung/Druck:
# log_patient_name("Tobias Hager")