# db_setup.py
import sqlite3
import os
import sys

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

DATABASE_NAME = os.path.join(get_base_path(), 'patienten.db')

def setup_database():
    """
    Erstellt die notwendigen SQLite-Tabellen (patienten, leistungen, stammdaten_leistungen).
    Fügt die neue Spalte 'kilometergeld' und 'last_selected_kurznamen' in die patienten-Tabelle ein.
    """
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    print(f"Datenbank wird eingerichtet oder aktualisiert: {DATABASE_NAME}")

    # 1. Patienten-Tabelle erstellen (mit neuer Spalte kilometergeld und last_selected_kurznamen)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patienten (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vorname TEXT NOT NULL,
        nachname TEXT NOT NULL,
        strasse TEXT,
        hausnummer TEXT,
        adresszusatz TEXT,
        plz TEXT,
        ort TEXT,
        anrede TEXT,
        versicherungsnummer TEXT,
        diagnose TEXT,
        kilometergeld REAL DEFAULT 0.0,
        last_selected_kurznamen TEXT DEFAULT '', -- NEUE SPALTE FÜR ZULETZT GEWÄHLTE LEISTUNGEN
        is_archived INTEGER DEFAULT 0, -- 0 = Aktiv, 1 = Archiviert
        UNIQUE(vorname, nachname, plz)
    )
    """)

    # 2. Leistungen-Tabelle erstellen
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leistungen (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        datum TEXT NOT NULL,
        uhrzeit_von TEXT,
        uhrzeit_bis TEXT,
        beschreibung TEXT NOT NULL,
        einzelbetrag REAL NOT NULL, 
        FOREIGN KEY (patient_id) REFERENCES patienten(id)
    )
    """)
    
    # 3. Stammdaten-Tabelle erstellen
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stammdaten_leistungen (
        kurzname TEXT PRIMARY KEY NOT NULL,
        beschreibung TEXT NOT NULL,
        standard_betrag REAL NOT NULL,
        is_archived INTEGER DEFAULT 0 -- 0 = Aktiv, 1 = Archiviert
    )
    """)

    # db_setup.py - Ergänzungen in setup_database()

    # 4. Einstellungen-Tabelle erstellen (für Honorarnoten-Folgenummer)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS einstellungen (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Optional: Standard-Einstellungen einfügen (nur wenn die Tabelle leer ist)
    try:
        cursor.execute("SELECT COUNT(*) FROM einstellungen WHERE key = 'rechnung_folgenummer'")
        if cursor.fetchone()[0] == 0:
            import datetime
            now = datetime.datetime.now()
            # Fügen Sie die Zeilen nur ein, wenn sie nicht existieren
            initial_settings = [
                ('rechnung_jahr', str(now.year)),
                ('rechnung_monat', str(now.month).zfill(2)), # Monat mit führender Null
                ('rechnung_folgenummer', '0'), # Start bei 0, da die erste generierte Rechnung 1 sein wird
            ]
            cursor.executemany("INSERT OR IGNORE INTO einstellungen (key, value) VALUES (?, ?)", initial_settings)
            print("Standard-Einstellungen für Rechnungsnummern eingefügt.")
            
    except Exception as e:
         print(f"Fehler beim Einfügen von Standard-Einstellungen: {e}")
    
    # Optional: Spalte zu bestehenden DBs hinzufügen
    try:
        cursor.execute("SELECT last_selected_kurznamen FROM patienten LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE patienten ADD COLUMN last_selected_kurznamen TEXT DEFAULT ''")
        print("Spalte 'last_selected_kurznamen' zur patienten-Tabelle hinzugefügt.")

    try:
        cursor.execute("SELECT is_archived FROM patienten LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE patienten ADD COLUMN is_archived INTEGER DEFAULT 0")
        print("Spalte 'is_archived' zur patienten-Tabelle hinzugefügt.")

    try:
        cursor.execute("SELECT is_archived FROM stammdaten_leistungen LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE stammdaten_leistungen ADD COLUMN is_archived INTEGER DEFAULT 0")
        print("Spalte 'is_archived' zur stammdaten_leistungen-Tabelle hinzugefügt.")
    
           
    conn.commit()
    conn.close()
    print("Datenbank-Setup abgeschlossen.")

# Führen Sie die Funktion aus, wenn das Skript direkt gestartet wird
if __name__ == "__main__":
    # Löschen Sie diese Zeile, wenn Sie NICHT jedes Mal eine komplett neue DB erstellen möchten!
    # try:
    #     os.remove(DATABASE_NAME)
    #     print(f"Vorherige Datenbank '{DATABASE_NAME}' gelöscht.")
    # except FileNotFoundError:
    #     pass
        
    setup_database()