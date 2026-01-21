# leprendix/services/os_utils.py
import os
import sys
import subprocess

def print_document_silently(file_path):
    """
    Versucht, die angegebene Datei direkt an den Standarddrucker zu senden.
    """
    if not os.path.exists(file_path):
        return False, "Datei zum Drucken nicht gefunden."

    try:
        if sys.platform.startswith('win'):
            # Windows: Nutzt den 'print' Verb des Dateityps (oft dialoglos)
            os.startfile(file_path, 'print')
            return True, "Druckauftrag an Windows-Standarddrucker gesendet."
            
        elif sys.platform.startswith('darwin') or sys.platform.startswith('linux'):
            # macOS/Linux: Nutzt 'lpr' (kann auf einigen Systemen einen Dialog auslösen)
            subprocess.run(['lpr', file_path], check=True)
            return True, "Druckauftrag via lpr (Linux/macOS) gesendet."
            
        else:
            return False, f"Automatisches Drucken wird auf dem Betriebssystem '{sys.platform}' nicht unterstützt."
            
    except subprocess.CalledProcessError as e:
        return False, f"Fehler beim LPR-Druckbefehl: {e}"
    except Exception as e:
        return False, f"Fehler beim direkten Drucken: {e}"