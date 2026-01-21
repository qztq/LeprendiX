# leprendix/db/queries.py
import sqlite3
import logging
from leprendix.core.paths import DB_PATH

def _ensure_db_schema():
    """
    Stellt sicher, dass die Spalten in der patienten-Tabelle existieren.
    Wird einmal beim Start aufgerufen.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if table exists to avoid crash on first run
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='patienten'")
    if not cursor.fetchone():
        conn.close()
        return

    try:
        # Versuche, die Spalte zu lesen
        cursor.execute("SELECT invoiced_since_reset FROM patienten LIMIT 1")
    except sqlite3.OperationalError:
        # Wenn die Spalte nicht existiert, füge sie hinzu
        cursor.execute("ALTER TABLE patienten ADD COLUMN invoiced_since_reset INTEGER DEFAULT 0")
        conn.commit()
        logging.info("Spalte 'invoiced_since_reset' in patienten-Tabelle hinzugefügt.")

    try:
        cursor.execute("SELECT last_selected_kurznamen FROM patienten LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE patienten ADD COLUMN last_selected_kurznamen TEXT DEFAULT ''")
        conn.commit()
        logging.info("Spalte 'last_selected_kurznamen' zur patienten-Tabelle hinzugefügt.")
    
    
    try:
        cursor.execute("SELECT is_archived FROM patienten LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE patienten ADD COLUMN is_archived INTEGER DEFAULT 0")
        conn.commit()
        logging.info("Spalte 'is_archived' zur patienten-Tabelle hinzugefügt.")

    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS blacklist (name TEXT PRIMARY KEY)")
        conn.commit()
    except Exception as e:
        logging.error(f"Fehler beim Erstellen der Blacklist-Tabelle: {e}")

    finally:
        conn.close()

def update_invoiced_status(patient_id, status=1):
    """Setzt den Status eines Patienten auf 1 (Grün/Abgerechnet) oder 0 (Rot/Offen)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE patienten SET invoiced_since_reset = ? WHERE id = ?", (status, patient_id))
        conn.commit()
        logging.info(f"Patient {patient_id} Honorarnoten-Status auf {status} gesetzt.")
    except Exception as e:
        logging.error(f"FEHLER beim Status-Update für Patient {patient_id}: {e}")
    finally:
        conn.close()

def get_patient_data(search_name):
    """Sucht Patienten und gibt ID und alle Adressfelder (inkl. Kilometergeld und letzte Leistungen) zurück."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    search_term = f'%{search_name}%'
    
    query = """
    SELECT id, vorname, nachname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld, last_selected_kurznamen
    FROM patienten 
    WHERE (nachname LIKE ? OR vorname LIKE ?) AND (is_archived IS NULL OR is_archived = 0)
    """
    params = [search_term, search_term]
    
    if search_name.isdigit():
        query += " OR (id = ? AND (is_archived IS NULL OR is_archived = 0))"
        params.append(search_name)
        
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results

def save_last_selected_leistungen(patient_id, kurznamen_set):
    """Speichert die Liste der zuletzt ausgewählten Kurznamen für einen Patienten in der DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Konvertiere das Set in einen String
    kurznamen_str = ','.join(sorted(list(kurznamen_set)))
    try:
        cursor.execute("""
        UPDATE patienten 
        SET last_selected_kurznamen = ?
        WHERE id = ?
        """, (kurznamen_str, patient_id))
        conn.commit()
    except Exception as e:
        logging.error(f"Fehler beim Speichern der letzten Leistungen für Patient {patient_id}: {e}")
    finally:
        conn.close()

def get_patient_leistungen(patient_id):
    """Holt alle NICHT ABGERECHNETEN Leistungen für die GUI-Anzeige."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag 
    FROM leistungen 
    WHERE patient_id = ? 
    ORDER BY datum ASC, uhrzeit_von ASC
    """, (patient_id,))
    leistungen = cursor.fetchall()
    conn.close()
    return leistungen

def get_patient_leistungen_for_template(patient_id):
    """Holt NICHT ABGERECHNETE Leistungen (ohne ID) für die Word-Generierung."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag 
    FROM leistungen 
    WHERE patient_id = ? 
    ORDER BY datum ASC, uhrzeit_von ASC
    """, (patient_id,))
    leistungen = cursor.fetchall()
    conn.close()
    return leistungen

def get_all_stammdaten_dict(archived=False):
    """Holt alle Stammdaten aus der DB und gibt sie als Liste und Dict zurück."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT kurzname, beschreibung, standard_betrag FROM stammdaten_leistungen WHERE is_archived = ? ORDER BY kurzname"
    cursor.execute(query, (1 if archived else 0,))
    results = cursor.fetchall()
    conn.close()
    
    stammdaten_list = [f"{r[0]} - {r[1]}" for r in results]
    stammdaten_dict = {item: r[2] for item, r in zip(stammdaten_list, results)}
    return stammdaten_list, stammdaten_dict

# Sicherstellen, dass die Spalten beim Import existieren
_ensure_db_schema()