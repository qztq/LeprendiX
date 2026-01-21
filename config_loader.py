import os
import json
from .paths import CONFIG_PATH, PROJECT_ROOT

def get_config():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    defaults = {
        "PATIENT_BASE_DIR": desktop,
        "ARCHIVE_DIR": os.path.join(desktop, "1Ehemalige Patienten"),
        "FIXED_ADDRESS": "Triesterstraße 10/4, 2351 Wiener Neudorf",
        "TEAMUP_API_KEY": "",
        "TEAMUP_CALENDAR_ID": "",
        "GITHUB_TOKEN": "",
        "QUICK_AMOUNTS": "33, 35, 57, 83",
        "LAST_SETUP_VERSION": "0.0.0",
        "HOTKEY_ENTER": "<Return>",
        "HOTKEY_SWITCH_TAB": "<F12>, <Delete>",
        "AUTO_DATE_SELECTOR": "Auto",
        "MANUAL_DATE_START": "",
        "MANUAL_DATE_END": "",
        "DEFAULT_DIAGNOSE": "Z71",
        "DEFAULT_ANREDE": "Herr/Frau"
    }

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                defaults.update(saved_config)
        except Exception as e:
            print(f"Fehler beim Laden der config.json: {e}")
    
    return defaults

CONFIG = get_config()