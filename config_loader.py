import os
import json
import sys


def get_config():
    # Ermittle den Basispfad (Exe-Verzeichnis oder Skript-Verzeichnis)
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        
    config_file = os.path.join(base_path, 'config.json')
    
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    defaults = {
        "DATABASE_NAME": "patienten.db",
        "PATIENT_BASE_DIR": desktop,
        "ARCHIVE_DIR": os.path.join(desktop, "1Ehemalige Patienten"),
        "TEAMUP_API_KEY": "c307ae48dc5f918fd9dada7b9e922a00e30c27a8939d8a31eb02dac60efe566a",
        "TEAMUP_CALENDAR_ID": "ks63f68d2f870c62a1",
        "GITHUB_TOKEN": "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",
        "QUICK_AMOUNTS": "33, 35, 57, 83",
        "LAST_SETUP_VERSION": "0.0.0",
        "HOTKEY_ENTER": "<Return>",
        "HOTKEY_SWITCH_TAB": "<F12>, <Delete>"
    }

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                defaults.update(saved_config)
        except Exception as e:
            print(f"Fehler beim Laden der config.json: {e}")
    
    return defaults

# Die Daten laden
_config = get_config()

# 1. Einzelne Variablen exportieren (für patient_status_checker)
DATABASE_NAME = _config["DATABASE_NAME"]
PATIENT_BASE_DIR = _config["PATIENT_BASE_DIR"]
ARCHIVE_DIR = _config["ARCHIVE_DIR"]

# 2. Das ganze Objekt exportieren (für den "Einstellungen"-Tab in main.py)
CONFIG = _config