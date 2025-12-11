# db_setup.py - MIT LEISTUNGS-STAMMDATEN UND UHRZEITEN

import sqlite3
import datetime

# --- KONFIGURATION ---
DATABASE_NAME = 'patienten.db'

# --- DATENBANK-SETUP ---
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# 1. Tabelle PATIENTEN
cursor.execute("""
CREATE TABLE IF NOT EXISTS patienten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nachname TEXT NOT NULL,
    vorname TEXT NOT NULL,
    strasse TEXT,
    hausnummer TEXT,
    adresszusatz TEXT,
    plz TEXT,
    ort TEXT,
    anrede TEXT,
    versicherungsnummer TEXT,
    diagnose TEXT,
    UNIQUE(nachname, vorname)
)
""")

# 2. Tabelle LEISTUNGEN (Erweitert um Uhrzeit)
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

# 3. Tabelle STAMMDATEN LEISTUNGEN
cursor.execute("""
CREATE TABLE IF NOT EXISTS stammdaten_leistungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kurzname TEXT UNIQUE NOT NULL,   
    beschreibung TEXT NOT NULL,      
    standard_betrag REAL NOT NULL    
)
""")

# --- Beispiel-Daten (zum schnellen Start) ---

# Beispiel-Patienten
beispiel_patienten = [
    ('Mustermann', 'Max', 'Musterweg', '12A', '', '1010', 'Wien', 'Herr', '1234567890', 'Z71'),
    ('Musterfrau', 'Erika', 'Beispielgasse', '5', 'Top 3', '8010', 'Graz', 'Frau', '0987654321', 'F43')
]

for nachname, vorname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose in beispiel_patienten:
    try:
        cursor.execute("""
        INSERT INTO patienten (nachname, vorname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nachname, vorname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose))
    except sqlite3.IntegrityError:
        pass 

# Beispiel-Stammdaten (zum schnellen Start)
stammdaten_eintraege = [
    ('PT_50', 'Psychotherapie (Einheit 50 Min.)', 100.00),
    ('PT_75', 'Psychotherapie (Einheit 75 Min.)', 150.00),
    ('EL_50', 'Erstgespräch (50 Min.)', 120.00)
]

for kurzname, beschreibung, betrag in stammdaten_eintraege:
    try:
        cursor.execute("""
        INSERT INTO stammdaten_leistungen (kurzname, beschreibung, standard_betrag)
        VALUES (?, ?, ?)
        """, (kurzname, beschreibung, betrag))
    except sqlite3.IntegrityError:
        pass 

# Beispiel-Leistungen
cursor.execute("SELECT id FROM patienten WHERE nachname = 'Mustermann'")
max_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None

if max_id:
    # Datum, Uhrzeit von, Uhrzeit bis, Beschreibung, Betrag
    leistungs_daten = [
        ('2025-12-01', '11:00', '11:50', 'Psychotherapie (Einheit 50 Min.)', 100.00),
        ('2025-12-08', '14:00', '14:50', 'Psychotherapie (Einheit 50 Min.)', 100.00),
        ('2025-12-10', '10:00', '10:50', 'Erstgespräch (50 Min.)', 120.00)
    ]

    for datum, von, bis, beschreibung, betrag in leistungs_daten:
        try:
            cursor.execute("""
            INSERT INTO leistungen (patient_id, datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (max_id, datum, von, bis, beschreibung, betrag))
        except sqlite3.IntegrityError:
             pass 

conn.commit()
conn.close()
print(f"Datenbank '{DATABASE_NAME}' erfolgreich eingerichtet/aktualisiert.")