# gui_generator.py
# Grafische Benutzeroberfläche (GUI) für den Honorarnoten-Generator mit voller Verwaltung und Teamup API-Integration

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime
from docx import Document
import os
import requests 
import json     
import subprocess 
import sys
import tkinter

# Entfernt: from log_data import log_patient_name 

# --- KONFIGURATION ---
DATABASE_NAME = 'patienten.db'
TEMPLATE_FILE = 'honorar_vorlage.docx' 
OUTPUT_FOLDER = 'Honorarnoten/' # Basisordner

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- KONFIGURATION (Teamup API) ---
# HINWEIS: Hier muss IHR Teamup Key und die Kalender ID stehen.
TEAMUP_API_KEY = 'c307ae48dc5f918fd9dada7b9e922a00e30c27a8939d8a31eb02dac60efe566a'
TEAMUP_CALENDAR_ID = 'ks63f68d2f870c62a1'
TEAMUP_BASE_URL = f"https://api.teamup.com/{TEAMUP_CALENDAR_ID}/events"

# Platzhalter für die Überprüfung, falls der Nutzer den Key nicht eingetragen hat
TEAMUP_API_KEY_PLACEHOLDER = 'YOUR_TEAMUP_API_KEY_HERE'


# --- NEUE FUNKTIONEN FÜR DEN STATUS-CHECK (WICHTIG!) ---

def _ensure_status_column():
    """
    Stellt sicher, dass die Spalte 'invoiced_since_reset' in der patienten-Tabelle existiert.
    Wird einmal beim Start aufgerufen.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Versuche, die Spalte zu lesen
        cursor.execute("SELECT invoiced_since_reset FROM patienten LIMIT 1")
    except sqlite3.OperationalError:
        # Wenn die Spalte nicht existiert, füge sie hinzu
        cursor.execute("ALTER TABLE patienten ADD COLUMN invoiced_since_reset INTEGER DEFAULT 0")
        conn.commit()
        print("INFO: Spalte 'invoiced_since_reset' in patienten-Tabelle hinzugefügt.")
    finally:
        conn.close()

def _update_invoiced_status(patient_id, status=1):
    """Setzt den Status eines Patienten auf 1 (Grün/Abgerechnet) oder 0 (Rot/Offen)."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE patienten SET invoiced_since_reset = ? WHERE id = ?", (status, patient_id))
        conn.commit()
        print(f"INFO: Patient {patient_id} Honorarnoten-Status auf {status} gesetzt.")
    except Exception as e:
        print(f"FEHLER beim Status-Update für Patient {patient_id}: {e}")
    finally:
        conn.close()
        
# Sicherstellen, dass die Spalte beim Start existiert
_ensure_status_column()

# HINZUFÜGEN in gui_generator.py (nach den anderen DB-Helfern, aber vor der Klasse HonorarGeneratorApp)
def _set_search_patient_id(patient_id):
    """Setzt die ID eines Patienten, der im Status-Checker zur Suche im Hauptfenster ausgewählt wurde. 
       Wird nur vom Status-Checker aufgerufen."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    key = 'last_selected_patient_id_for_search'
    try:
        # Führt ein INSERT OR REPLACE aus (fügt ein, oder überschreibt, wenn der Key existiert)
        cursor.execute("INSERT OR REPLACE INTO einstellungen (key, value) VALUES (?, ?)", (key, str(patient_id)))
        conn.commit()
    except Exception as e:
        # Die Tabelle 'einstellungen' muss existieren. Wenn nicht, wird hier ein Fehler ausgegeben.
        print(f"FEHLER beim Setzen der Search-Target-ID: {e}")
    finally:
        conn.close()

# KORRIGIERT: gui_generator.py (Funktion außerhalb der Klasse)

def _get_and_clear_search_patient_id():
    """
    Holt die ID des zur Suche markierten Patienten, löscht den Eintrag 
    und gibt die ID zurück.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    key = 'last_selected_patient_id_for_search'
    patient_id = None # Initialisiere patient_id

    try:
        # 1. Hole die ID
        cursor.execute("SELECT value FROM einstellungen WHERE key = ?", (key,))
        result = cursor.fetchone()
        
        if result:
            patient_id = int(result[0])
            # 2. Lösche den Eintrag, damit er nur einmal verwendet wird
            cursor.execute("DELETE FROM einstellungen WHERE key = ?", (key,))
            conn.commit()
            
    except Exception as e:
        print(f"FEHLER beim Lesen/Löschen der Search-Target-ID: {e}")
        patient_id = None # Sicherstellen, dass bei Fehler keine ID zurückkommt
        
    finally:
        # Nur Aufräumarbeiten im finally-Block
        conn.close() 
        
    # Der Rückgabewert erfolgt nun außerhalb des finally-Blocks
    return patient_id
# --- HILFSFUNKTIONEN FÜR DRUCK, DB und API ---

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

def get_patient_data(search_name):
    """Sucht Patienten und gibt ID und alle Adressfelder (inkl. Kilometergeld und letzte Leistungen) zurück."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    search_term = f'%{search_name}%'
    # Wichtig: last_selected_kurznamen ist Spalte 13 (Index 12)
    # Wichtig: invoiced_since_reset ist Spalte 14 (Index 13), wird hier nicht benötigt, aber später
    cursor.execute("""
    SELECT id, vorname, nachname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld, last_selected_kurznamen
    FROM patienten 
    WHERE nachname LIKE ? OR vorname LIKE ?
    """, (search_term, search_term))
    results = cursor.fetchall()
    conn.close()
    return results

def save_last_selected_leistungen(patient_id, kurznamen_set):
    """Speichert die Liste der zuletzt ausgewählten Kurznamen für einen Patienten in der DB."""
    conn = sqlite3.connect(DATABASE_NAME)
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
        print(f"Fehler beim Speichern der letzten Leistungen für Patient {patient_id}: {e}")
    finally:
        conn.close()


def get_patient_leistungen(patient_id):
    """Holt alle NICHT ABGERECHNETEN Leistungen für die GUI-Anzeige."""
    # TODO: Muss später um 'WHERE abgerechnet_am IS NULL' erweitert werden
    conn = sqlite3.connect(DATABASE_NAME)
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
    # TODO: Muss später um 'WHERE abgerechnet_am IS NULL' erweitert werden
    conn = sqlite3.connect(DATABASE_NAME)
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

def get_all_stammdaten_dict():
    """Holt alle Stammdaten aus der DB und gibt sie als Liste und Dict zurück."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT kurzname, beschreibung, standard_betrag FROM stammdaten_leistungen ORDER BY kurzname")
    results = cursor.fetchall()
    conn.close()
    stammdaten_list = [f"{r[0]} - {r[1]}" for r in results]
    stammdaten_dict = {item: r[2] for item, r in zip(stammdaten_list, results)}
    return stammdaten_list, stammdaten_dict

def search_teamup_events(search_term, start_date=None, end_date=None):
    """
    Sucht Teamup-Kalendereinträge basierend auf dem Titel/Notizen.
    """
    
    clean_api_key = TEAMUP_API_KEY.strip()
    
    headers = {
        'Teamup-Token': clean_api_key, 
        'Accept': 'application/json'
    }
    
    # BEGRENZUNG DES ZEITRAUMS
    if start_date is None:
        start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = (datetime.date.today() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        
    params = {
        'startDate': start_date,
        'endDate': end_date
    }
    
    try:
        response = requests.get(TEAMUP_BASE_URL, headers=headers, params=params)
        response.raise_for_status()  
        
        data = response.json()
        
        matching_events = []
        term = search_term.lower()

        for event in data.get('events', []):
            title = event.get('title', '')
            notes = event.get('notes', '')
            
            if term in title.lower() or term in notes.lower():
                
                start_iso = event.get('start_dt')
                end_iso = event.get('end_dt')
                
                if start_iso and end_iso:
                    start_iso_clean = start_iso.replace('Z', '+00:00')
                    end_iso_clean = end_iso.replace('Z', '+00:00')
                    
                    start_dt = datetime.datetime.fromisoformat(start_iso_clean)
                    end_dt = datetime.datetime.fromisoformat(end_iso_clean)
                    
                    event_tuple = (
                        title, 
                        start_dt.strftime('%d.%m.%Y'),
                        start_dt.strftime('%H:%M'),
                        end_dt.strftime('%H:%M')
                    )
                    matching_events.append(event_tuple)
                    
        return matching_events
        
    except requests.exceptions.HTTPError as e:
        error_details = response.text if hasattr(response, 'text') else str(e)
        messagebox.showerror("API Fehler", f"HTTP-Fehler beim Abruf der Teamup-Daten: {e}\nDetails: {error_details}")
        return []
    except Exception as e:
        messagebox.showerror("Fehler", f"Teamup API-Fehler: {e}")
        return []


# --- WORD-GENERIERUNGSFUNKTION ---

def fill_template(patient_id, patient_data_tuple, template_data): # NEUE SIGNATUR
    """Füllt die Word-Vorlage mit den Patientendaten und Leistungen und speichert sie."""
    
    # patient_data_tuple hat 13 Elemente: Index 0=id, ..., 11=kilometergeld, 12=last_selected_kurznamen (nicht benötigt)
    _, vorname, nachname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld, _ = patient_data_tuple
    
    leistungen_liste = get_patient_leistungen_for_template(patient_id)
    
    heute = datetime.date.today().strftime("%d.%m.%Y")
    # honorar_nummer = f"HN-{datetime.date.today().year}-{datetime.date.today().month:02d}-{patient_id:03d}" # ALTE LOGIK ENTFERNT
    
    try:
        document = Document(TEMPLATE_FILE)
    except FileNotFoundError:
        raise FileNotFoundError(f"Die Vorlagendatei '{TEMPLATE_FILE}' wurde nicht gefunden.")
    
    total_betrag = 0.0
    
    # Statische Platzhalter
    replacements = {
        '{{Rechnungsnummer}}': template_data['BHAG_NUMMER'], # NEU: BHAG-Nummer verwenden
        '{{Anrede}}': anrede, 
        '{{Nachname}}': nachname,
        '{{Vorname}}': vorname,
        '{{Straße}}': strasse,
        '{{Hausnummer}}': hausnummer,
        '{{Adresszusatz}}': adresszusatz or '',
        '{{Postleitzahl}}': plz,
        '{{Stadt}}': ort,
        '{{Versicherungsnummer}}': versicherungsnummer,
        '{{Datum_Austellung}}': heute,
        '{{Diagnose}}': diagnose
    }
    
    # --- Dynamische Leistungsblock-Logik ---
    
    start_tag = '{{LEISTUNGSBLOCK_START}}'
    end_tag = '{{LEISTUNGSBLOCK_ENDE}}'
    
    block_start_paragraph = None
    block_end_paragraph = None
    block_paragraphs = []
    
    in_block = False
    
    # Text-Ersetzung und Block-Suche in einem Durchlauf
    for p in document.paragraphs:
        # Statische Platzhalter ersetzen
        for key, value in replacements.items():
            if key in p.text:
                p.text = p.text.replace(key, value)
                
        # Block-Logik: Musterblock finden
        if start_tag in p.text:
            block_start_paragraph = p
            in_block = True
            continue
        
        if end_tag in p.text:
            block_end_paragraph = p
            break
            
        if in_block:
            block_paragraphs.append(p)

    # Generieren des gesamten Leistungs-Textes
    gesamt_leistungs_text = ""
    
    if block_start_paragraph and block_end_paragraph:
        
        template_text = '\n'.join([p.text for p in block_paragraphs])
        
        for datum_db, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag in leistungen_liste: 
            
            datum_formatiert = datetime.datetime.strptime(datum_db, '%Y-%m-%d').strftime('%d.%m.%Y')
            datum_uhrzeit_text = f"{datum_formatiert}, von {uhrzeit_von} bis {uhrzeit_bis}" 
            
            summe_leistung = einzelbetrag # Enthält bereits den Kilometergeld-Aufschlag
            total_betrag += summe_leistung
            
            leistung_block = template_text.replace('{{LEISTUNG_DATUM}}', datum_uhrzeit_text)
            leistung_block = leistung_block.replace('{{LEISTUNG_BESCHREIBUNG}}', beschreibung)
            leistung_block = leistung_block.replace('{{LEISTUNG_SUMME}}', f"€ {summe_leistung:.2f}")
            
            gesamt_leistungs_text += leistung_block + '\n\n'
            
        # Den generierten Text an der Startposition einfügen
        if gesamt_leistungs_text:
            
            for zeile in gesamt_leistungs_text.split('\n'):
                if zeile.strip():
                    p_new = block_start_paragraph.insert_paragraph_before(zeile.strip())
                    p_new.style = block_start_paragraph.style
                
            block_start_paragraph.text = '' 
            for p in block_paragraphs:
                p._element.getparent().remove(p._element)
            block_end_paragraph.text = ''
        else:
             # Falls keine Leistungen da sind, Platzhalter entfernen
             block_start_paragraph.text = '' 
             for p in block_paragraphs:
                 p._element.getparent().remove(p._element)
             block_end_paragraph.text = ''


    # Ersetzen des Gesamtbetrags
    gesamt_betrag_str = f"{total_betrag:.2f}"
    
    for paragraph in document.paragraphs:
        if '{{Gesamt_Betrag}}' in paragraph.text:
            # BUG FIX: Muss auf paragraph.text angewendet werden!
            paragraph.text = paragraph.text.replace('{{Gesamt_Betrag}}', gesamt_betrag_str)

    # --- Speichern des Dokuments ---
    # Entfernt: log_patient_name(f"{nachname}_{vorname}")
    patient_folder_name = f"{nachname}_{vorname}"
    patient_output_path = os.path.join(OUTPUT_FOLDER, patient_folder_name)
    os.makedirs(patient_output_path, exist_ok=True)
    
    output_filename = f"Honorarnote Krankenkasse {template_data['BHAG_NUMMER']}.docx" # BHAG-Nummer im Dateinamen
    output_path = os.path.join(patient_output_path, output_filename)

    document.save(output_path)
    return output_path # Rückgabe des Pfades


# --- HAUPT-GUI-KLASSE ---

class HonorarGeneratorApp:
    def __init__(self, master):
        self.master = master
        master.title("Honorarnoten-Generator")
        master.geometry("900x700")
        
        self.patient_data = None  
        self.stammdaten_betraege = {} 
        self.selected_leistung_id = None 
        self.selected_leistungs_kurznamen = set() # Für die Mehrfachauswahl-Buttons

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        self.tab_generate = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_generate, text='📝 Honorarnote Generieren')
        
        self.tab_patient = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_patient, text='👤 Patienten Verwalten')
        self.setup_patient_tab(self.tab_patient)

        self.tab_leistung = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_leistung, text='➕ Leistungen Hinzufügen/Prüfen')
        self.setup_leistung_tab(self.tab_leistung)
        
        self.tab_stammdaten = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_stammdaten, text='⚙️ Stammdaten Leistungen')
        self.setup_stammdaten_tab(self.tab_stammdaten)
        
        # NEU: Initialisierung des TK-Stil-Objekts (FIX für AttributeError)
        self.ttk_style = ttk.Style() 
        
        # NEU: Initialisierung der Folgenummer (BHAG-Logik)
        self.invoice_seq_var = tk.StringVar() 
        self.invoice_sequence_data = self._get_invoice_sequence_data()
        # Zeigt die gespeicherte Folgenummer mit führenden Nullen (z.B. '001') an
        self.invoice_seq_var.set(str(self.invoice_sequence_data.get('rechnung_folgenummer', '0')).zfill(3))
        
        self.setup_generate_tab(self.tab_generate)
        
        self.update_patient_info() 
        self.load_leistung_stammdaten_buttons() 


   
    def _get_invoice_sequence_data(self):
        """Holt die aktuelle Folgenummer, Jahr und Monat aus der Einstellungen-Tabelle."""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        data = {}
        now = datetime.datetime.now()
        
        # Standardwerte (für den Fall, dass die DB-Tabelle noch nicht existiert)
        default_data = {
            'rechnung_jahr': str(now.year),
            'rechnung_monat': str(now.month).zfill(2),
            'rechnung_folgenummer': '0' # Start bei 0
        }
        
        try:
            cursor.execute("SELECT key, value FROM einstellungen WHERE key IN ('rechnung_jahr', 'rechnung_monat', 'rechnung_folgenummer')")
            for key, value in cursor.fetchall():
                data[key] = value
            
            # Stelle sicher, dass alle Schlüssel vorhanden sind
            return {**default_data, **data}
            
        except sqlite3.OperationalError:
            # Fallback, wenn die Tabelle noch nicht existiert (z.B. wenn db_setup.py nicht lief)
            print("WARNUNG: Einstellungen-Tabelle nicht gefunden. Verwende Standardwerte.")
            return default_data
        finally:
            conn.close()

    def _update_invoice_sequence_data(self, key, value):
        """Aktualisiert oder fügt einen Wert in der Einstellungen-Tabelle ein."""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            # Versucht, den Wert zu aktualisieren (UPDATE OR IGNORE ist sicherer)
            cursor.execute("UPDATE einstellungen SET value = ? WHERE key = ?", (str(value), key))
            if cursor.rowcount == 0:
                 # Wenn kein Update möglich war, wird ein INSERT versucht
                 cursor.execute("INSERT OR IGNORE INTO einstellungen (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
        except Exception as e:
            print(f"FEHLER beim Aktualisieren der Folgenummer in der DB ({key}): {e}")
            messagebox.showerror("Fehler", f"Fehler beim Aktualisieren der Folgenummer in der DB ({key}): {e}")
        finally:
            conn.close()

    def _save_custom_invoice_number(self):
        """Speichert die manuell eingegebene Folgenummer und aktualisiert die DB."""
        try:
            new_nummer_str = self.invoice_seq_var.get().strip()
            
            # Validierung: Muss eine Zahl sein (max. 3 Ziffern, wir akzeptieren bis 999)
            if not new_nummer_str.isdigit() or len(new_nummer_str) > 3 or int(new_nummer_str) < 0:
                messagebox.showerror("Fehler", "Folgenummer muss eine Zahl zwischen 0 und 999 sein.")
                # Setzt auf den letzten gültigen Wert zurück (intern gespeichert)
                self.invoice_seq_var.set(str(self.invoice_sequence_data['rechnung_folgenummer']).zfill(3)) 
                return

            new_nummer = int(new_nummer_str)

            # Aktualisiere interne Daten und DB
            self.invoice_sequence_data['rechnung_folgenummer'] = str(new_nummer)
            self._update_invoice_sequence_data('rechnung_folgenummer', str(new_nummer))
            
            # Aktualisiere das Anzeige-Feld (mit führenden Nullen)
            self.invoice_seq_var.set(str(new_nummer).zfill(3))
            
            messagebox.showinfo("Erfolg", f"Folgenummer manuell auf '{str(new_nummer).zfill(3)}' gespeichert.")
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Speichern der Folgenummer: {e}")

    def _prepare_bhag_number(self):
        """Generiert die nächste BHAG-Nummer, aktualisiert die DB und die GUI."""
        now = datetime.datetime.now()
        current_year = str(now.year)
        current_month = str(now.month).zfill(2) 

        # Hole die gespeicherten Daten (als String)
        stored_year = self.invoice_sequence_data.get('rechnung_jahr', current_year)
        stored_month = self.invoice_sequence_data.get('rechnung_monat', current_month)
        current_folgenummer = int(self.invoice_sequence_data.get('rechnung_folgenummer', '0'))

        # --- Reset-Logik (Jährlich) ---
        if current_year != stored_year:
            # Jährlicher Reset: Setze auf 1 und aktualisiere Jahr/Monat
            new_folgenummer = 1
            self.invoice_sequence_data['rechnung_jahr'] = current_year
            self.invoice_sequence_data['rechnung_monat'] = current_month
            self._update_invoice_sequence_data('rechnung_jahr', current_year)
            self._update_invoice_sequence_data('rechnung_monat', current_month)
        else:
            # Normales Inkremement
            new_folgenummer = current_folgenummer + 1

        # 2. Folgenummer formatieren und BHAG-Nummer generieren
        folgenummer_str = str(new_folgenummer).zfill(3) # z.B. '001', '010'
        bhag_nummer = f"BHAG{current_year}{current_month}{folgenummer_str}"

        # 3. Datenbank und GUI aktualisieren
        self.invoice_sequence_data['rechnung_folgenummer'] = str(new_folgenummer)
        self._update_invoice_sequence_data('rechnung_folgenummer', str(new_folgenummer))
        self.invoice_seq_var.set(folgenummer_str) # Aktualisiere das Feld im GUI
        
        # Stelle sicher, dass die Monatsangabe immer aktuell ist (falls sie sich innerhalb des Jahres ändert)
        if stored_month != current_month:
            self.invoice_sequence_data['rechnung_monat'] = current_month
            self._update_invoice_sequence_data('rechnung_monat', current_month)

        return {'BHAG_NUMMER': bhag_nummer}
        
    # --- 1. Generieren Tab ---
    def setup_generate_tab(self, tab):
        ttk.Label(tab, text="Patienten-Suche (Nachname/Vorname):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.search_entry = ttk.Entry(tab, width=40)
        self.search_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(tab, text="Suchen", command=self.search_patients).grid(row=0, column=2, padx=5, pady=5)
        
        self.results_listbox = tk.Listbox(tab, height=10, width=60)
        self.results_listbox.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')
        self.results_listbox.bind('<<ListboxSelect>>', self.select_patient_from_list)

        ttk.Label(tab, text="Aktueller Patient:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.current_patient_label = ttk.Label(tab, text="Kein Patient ausgewählt", foreground='blue')
        self.current_patient_label.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky='w')

        # Frame für die Generierungs-Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        # Bestehender Button
        ttk.Button(btn_frame, text="HONORARNOTE GENERIEREN (Speichern & Öffnen)", command=self.generate_invoice).pack(side=tk.LEFT, padx=10)
        
        # NEUER BUTTON: Generieren und Sofort Drucken
        ttk.Button(btn_frame, text="✅ Generieren & Sofort Drucken", command=self.generate_and_print_invoice).pack(side=tk.LEFT, padx=10)
        
        # --- Honorarnoten-Folgenummer (NEU) ---
        folgenummer_frame = ttk.LabelFrame(tab, text="Honorar-Folgenummer (BHAG-Nr.)")
        folgenummer_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky="ew")

        ttk.Label(folgenummer_frame, text="Aktuelle Folgenummer (000-999):").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.invoice_seq_entry = ttk.Entry(folgenummer_frame, textvariable=self.invoice_seq_var, width=5)
        self.invoice_seq_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        save_folgenummer_btn = ttk.Button(folgenummer_frame, text="Folgenummer speichern (manuell korrigieren)", command=self._save_custom_invoice_number)
        save_folgenummer_btn.grid(row=0, column=2, padx=5, pady=2, sticky="w")

        ttk.Label(folgenummer_frame, text="Format: BHAG[Jahr][Monat][Folgenummer]").grid(row=1, column=0, columnspan=3, padx=5, pady=2, sticky="w")

        tab.grid_rowconfigure(1, weight=1)

    def search_patients(self):
# ... (Funktion bleibt unverändert)
        search_term = self.search_entry.get().strip()
        if not search_term:
            messagebox.showwarning("Suche", "Bitte geben Sie einen Suchbegriff ein.")
            return
            
        results = get_patient_data(search_term)
        
        self.results_listbox.delete(0, tk.END)
        self.results_listbox.patient_data_list = []

        if not results:
            self.results_listbox.insert(tk.END, "Keine Patienten gefunden.")
            return

        for patient_data_tuple in results:
            display_text = f"ID {patient_data_tuple[0]} - {patient_data_tuple[2]} {patient_data_tuple[1]} ({patient_data_tuple[7]})"
            self.results_listbox.insert(tk.END, display_text)
            self.results_listbox.patient_data_list.append(patient_data_tuple)

    def select_patient_from_list(self, event):
# ... (Funktion bleibt unverändert)
        selection = self.results_listbox.curselection()
        if selection:
            index = selection[0]
            self.patient_data = self.results_listbox.patient_data_list[index] 
            self.update_patient_info()
            
            # NEU: Lade und wähle die zuletzt ausgewählten Leistungen aus
            self.load_and_select_last_leistungen()
            
            # Automatisch zum Leistungs-Tab wechseln und Liste aktualisieren
            self.notebook.select(self.tab_leistung)
            self.update_leistung_list() 

    def update_patient_info(self):
# ... (Funktion bleibt unverändert)
        if self.patient_data:
            # patient_data[11] ist das Kilometergeld
            km_geld = self.patient_data[11] if len(self.patient_data) > 11 and self.patient_data[11] is not None else 0.0
            text = f"{self.patient_data[2]} {self.patient_data[1]} (ID: {self.patient_data[0]}, VersNr: {self.patient_data[9]}, KM: €{km_geld:.2f})"
            self.current_patient_label.config(text=text)
            if hasattr(self, 'leistung_patient_label'):
                self.leistung_patient_label.config(text=text, foreground='blue')
        else:
            self.current_patient_label.config(text="Kein Patient ausgewählt")
            if hasattr(self, 'leistung_patient_label'):
                self.leistung_patient_label.config(text="Bitte Patient in Tab 1 auswählen", foreground='red')

    def generate_invoice(self):
        """Generiert die Honorarnote und öffnet die Datei."""
        if not self.patient_data:
            messagebox.showwarning("Warnung", "Bitte wählen Sie zuerst einen Patienten aus.")
            return

        patient_id = self.patient_data[0]
        
        try:
            # NEU: BHAG-Nummer generieren und DB aktualisieren
            data_for_template = self._prepare_bhag_number() 
            
            output_path = fill_template(patient_id, self.patient_data, data_for_template) # NEUE SIGNATUR
            
            # NEU: Setze den Status des Patienten auf "abgerechnet" (1 = Grün)
            _update_invoiced_status(patient_id, 1)

            messagebox.showinfo("Erfolg", f"Honorarnote erfolgreich erstellt!\nGespeichert unter: {output_path}")
            
            # Öffnen der Datei nach Generierung
            if sys.platform.startswith('win'):
                os.startfile(output_path)
            elif sys.platform.startswith('darwin'):
                subprocess.call(('open', output_path))
            elif sys.platform.startswith('linux'):
                subprocess.call(('xdg-open', output_path))
                
            # TODO: Hier Funktion zum Markieren der Leistungen als "abgerechnet" aufrufen
            
        except FileNotFoundError as e:
             messagebox.showerror("Fehler", str(e))
        except Exception as e:
            import traceback
            messagebox.showerror("Fehler", f"Fehler bei der Generierung: {e}\n\nDetails siehe Konsole.")
            traceback.print_exc()

    def generate_and_print_invoice(self):
        """Generiert die Honorarnote und versucht, sie direkt zu drucken."""
        if not self.patient_data:
            messagebox.showwarning("Warnung", "Bitte wählen Sie zuerst einen Patienten aus.")
            return

        try:
            # NEU: BHAG-Nummer generieren und DB aktualisieren
            data_for_template = self._prepare_bhag_number() 
            
            # 1. Generiere die Honorarnote
            output_path = fill_template(self.patient_data[0], self.patient_data, data_for_template) # NEUE SIGNATUR
            
            # 2. Versuche, sie sofort zu drucken
            success, message = print_document_silently(output_path)
            
            if success:
                # NEU: Setze den Status des Patienten auf "abgerechnet" (1 = Grün)
                _update_invoiced_status(self.patient_data[0], 1)
                
                messagebox.showinfo("Druckerfolg", f"Honorarnote erstellt und erfolgreich gedruckt.\n{message}")
                # TODO: Hier Funktion zum Markieren der Leistungen als "abgerechnet" aufrufen
                
            else:
                # Fallback: Datei anzeigen, falls Drucken fehlschlägt
                if sys.platform.startswith('win'):
                    os.startfile(output_path)
                elif sys.platform.startswith('darwin'):
                    subprocess.call(('open', output_path))
                elif sys.platform.startswith('linux'):
                    subprocess.call(('xdg-open', output_path))
                    
                messagebox.showwarning("Druckfehler", f"Druckauftrag konnte nicht direkt gesendet werden:\n{message}\nDie Datei wurde im Viewer geöffnet.")
                
        except FileNotFoundError as e:
             messagebox.showerror("Fehler", str(e))
        except Exception as e:
            import traceback
            messagebox.showerror("Fehler", f"Fehler bei Generierung/Druck: {e}")
            traceback.print_exc()


    # --- 2. Patienten Verwalten Tab (Hinzufügen und Bearbeiten) ---
    def setup_patient_tab(self, tab):
# ... (Rest der Klasse bleibt unverändert)
        search_frame = ttk.Frame(tab)
        search_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        
        ttk.Label(search_frame, text="Patient suchen/laden:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.patient_search_entry = ttk.Entry(search_frame, width=30)
        self.patient_search_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(search_frame, text="Laden", command=self.search_and_load_patient).grid(row=0, column=2, padx=5, pady=5)
        
        self.patient_id_to_edit = None
        
        fields = [
            "Anrede", "Vorname", "Nachname", "Versicherungsnummer", 
            "Straße", "Hausnummer", "Adresszusatz", "PLZ", "Ort", "Diagnose",
            "Kilometergeld (€)"
        ]
        self.patient_entries = {}

        for i, field in enumerate(fields):
            ttk.Label(tab, text=f"{field}:").grid(row=i + 1, column=0, padx=5, pady=5, sticky='w')
            entry = ttk.Entry(tab, width=40)
            entry.grid(row=i + 1, column=1, padx=5, pady=5, sticky='we')
            self.patient_entries[field] = entry

        self.patient_entries["Anrede"].insert(0, "Herr/Frau")
        self.patient_entries["Diagnose"].insert(0, "Z71")
        self.patient_entries["Kilometergeld (€)"].insert(0, "0.00")
        
        self.save_patient_button = ttk.Button(tab, text="Patient Hinzufügen", command=self.add_patient_gui)
        self.save_patient_button.grid(row=len(fields) + 1, column=0, columnspan=2, pady=10)
        
        ttk.Button(tab, text="Formular Leeren / Abbrechen", command=self.clear_patient_form).grid(row=len(fields) + 2, column=0, columnspan=2, pady=5)

    def search_and_load_patient(self):
# ... (Rest der Klasse bleibt unverändert)
        """Sucht einen Patienten und lädt die Daten in die Bearbeitungsfelder."""
        search_term = self.patient_search_entry.get().strip()
        if not search_term:
            messagebox.showwarning("Suche", "Bitte geben Sie einen Suchbegriff (Name) ein.")
            return

        results = get_patient_data(search_term) 

        if not results:
            messagebox.showinfo("Suche", f"Kein Patient gefunden für '{search_term}'.")
            self.clear_patient_form()
            return
        
        patient_data_tuple = results[0] 
        self.patient_id_to_edit = patient_data_tuple[0] 
        
        self.clear_patient_form(clear_defaults=False) 
        
        # patient_data_tuple: Index 0=id, 1=vorname, ..., 10=diagnose, 11=kilometergeld, 12=last_selected_kurznamen
        data_map = {
            "Anrede": patient_data_tuple[8],
            "Vorname": patient_data_tuple[1],
            "Nachname": patient_data_tuple[2],
            "Versicherungsnummer": patient_data_tuple[9],
            "Straße": patient_data_tuple[3],
            "Hausnummer": patient_data_tuple[4],
            "Adresszusatz": patient_data_tuple[5],
            "PLZ": patient_data_tuple[6],
            "Ort": patient_data_tuple[7],
            "Diagnose": patient_data_tuple[10],
            "Kilometergeld (€)": f"{patient_data_tuple[11]:.2f}" if patient_data_tuple[11] is not None else "0.00"
        }
        
        for field, value in data_map.items():
            self.patient_entries[field].insert(0, value or "") 
        
        self.save_patient_button.config(text=f"Patient Aktualisieren (ID: {self.patient_id_to_edit})")
        print(f"INFO: Patient '{patient_data_tuple[1]} {patient_data_tuple[2]}' geladen. Bearbeiten und 'Aktualisieren' klicken.") # messagebox entfernt

    def clear_patient_form(self, clear_defaults=True):
# ... (Rest der Klasse bleibt unverändert)
        """Leert das Patientenformular und setzt den Button-Text zurück."""
        self.patient_id_to_edit = None
        for key, entry in self.patient_entries.items():
            entry.delete(0, tk.END)
        
        if clear_defaults:
            self.patient_entries["Anrede"].insert(0, "Herr/Frau")
            self.patient_entries["Diagnose"].insert(0, "Z71")
            self.patient_entries["Kilometergeld (€)"].insert(0, "0.00")
        
        self.save_patient_button.config(text="Patient Hinzufügen")
        self.patient_search_entry.delete(0, tk.END)


    def add_patient_gui(self):
# ... (Rest der Klasse bleibt unverändert)
        """Fügt neuen Patienten hinzu oder aktualisiert bestehenden."""
        vorname = self.patient_entries["Vorname"].get().strip()
        nachname = self.patient_entries["Nachname"].get().strip()
        strasse = self.patient_entries["Straße"].get().strip()
        hausnummer = self.patient_entries["Hausnummer"].get().strip()
        adresszusatz = self.patient_entries["Adresszusatz"].get().strip()
        plz = self.patient_entries["PLZ"].get().strip()
        ort = self.patient_entries["Ort"].get().strip()
        anrede = self.patient_entries["Anrede"].get().strip()
        versicherungsnummer = self.patient_entries["Versicherungsnummer"].get().strip()
        diagnose = self.patient_entries["Diagnose"].get().strip()
        kilometergeld_str = self.patient_entries["Kilometergeld (€)"].get().strip().replace(',', '.') 

        if not vorname or not nachname:
            messagebox.showwarning("Achtung", "Vor- und Nachname sind Pflichtfelder.")
            return

        try:
             kilometergeld = float(kilometergeld_str)
        except ValueError:
             messagebox.showwarning("Achtung", "Kilometergeld muss eine gültige Zahl sein (z.B. 5.50).")
             return

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        try:
            if self.patient_id_to_edit:
                # AKTUALLISIEREN
                
                # FIX: Prüfe, ob die neuen Schlüssel mit einem ANDEREN Patienten kollidieren
                cursor.execute("""
                SELECT id FROM patienten 
                WHERE vorname = ? AND nachname = ? AND plz = ? AND id != ?
                """, (vorname, nachname, plz, self.patient_id_to_edit))
                
                if cursor.fetchone():
                    raise sqlite3.IntegrityError("Konflikt mit existierendem Patienten")
                
                # Wenn kein Konflikt mit einem ANDEREN Patienten, führe Update aus:
                cursor.execute("""
                UPDATE patienten 
                SET nachname=?, vorname=?, strasse=?, hausnummer=?, adresszusatz=?, plz=?, ort=?, anrede=?, versicherungsnummer=?, diagnose=?, kilometergeld=?
                WHERE id=?
                """, (nachname, vorname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld, self.patient_id_to_edit))
                
                conn.commit()
                messagebox.showinfo("Erfolg", f"Patient '{vorname} {nachname}' erfolgreich aktualisiert (ID: {self.patient_id_to_edit}).")
                self.clear_patient_form()
                
            else:
                # HINZUFÜGEN (Neue Spalte last_selected_kurznamen und invoiced_since_reset mit Standardwert '')
                cursor.execute("""
                INSERT INTO patienten (nachname, vorname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld, last_selected_kurznamen, invoiced_since_reset)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nachname, vorname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld, '', 0))
                
                conn.commit()
                messagebox.showinfo("Erfolg", f"Neuer Patient '{vorname} {nachname}' erfolgreich gespeichert.")
                self.clear_patient_form()
                
        except sqlite3.IntegrityError:
            # Wird bei INSERT oder bei Konflikt mit ANDEREM Patienten beim UPDATE ausgelöst
            messagebox.showerror("Fehler", f"Patient '{vorname} {nachname}' mit dieser PLZ existiert bereits in der Datenbank.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Datenbankfehler: {e}")
        conn.close()


    # --- HILFSFUNKTIONEN FÜR LEISTUNGEN --- 
    # ... (Rest der Klasse bleibt unverändert)

    def _delete_all_patient_leistungen(self, patient_id):
        """Löscht ALLE Leistungen des angegebenen Patienten ohne GUI-Interaktion."""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM leistungen WHERE patient_id = ?", (patient_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"FEHLER: Fehler beim Löschen aller Leistungen für Patient {patient_id}: {e}")
            return False
        finally:
            conn.close()

    def _get_leistung_insertion_params(self):
        """Hilfsfunktion zur Vorbereitung von Betrag und KM-Geld."""
        manual_betrag_str = self.amount_entry.get().strip().replace(',', '.')
        try:
            manual_betrag = float(manual_betrag_str)
            use_manual_override = manual_betrag > 0.009
        except ValueError:
            use_manual_override = False
            manual_betrag = 0.0
        km_geld = self.get_current_kilometergeld()
        return manual_betrag, use_manual_override, km_geld

    def _reset_leistung_selection(self):
        """Hilfsfunktion zum Zurücksetzen der Button-Auswahl in der GUI."""
        self.selected_leistungs_kurznamen.clear()
        for widget in self.leistung_button_frame.winfo_children():
            if hasattr(widget, 'is_selected') and widget.is_selected:
                widget.config(style='TButton')
                widget.is_selected = False

    def add_leistung_to_db(self, patient_id, datum_str, time_from, time_to, kurzname, standard_betrag, manual_betrag, use_manual_override, km_geld):
        """Fügt eine einzelne Leistung in die DB ein."""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            datum_db = datetime.datetime.strptime(datum_str, '%d.%m.%Y').strftime('%Y-%m-%d')

            betrag = manual_betrag if use_manual_override else standard_betrag
            end_betrag = betrag + km_geld 

            # Beschreibung basierend auf manuellem Override oder Stammdaten
            beschreibung = self.stammdaten_betraege.get(kurzname, kurzname)
            if use_manual_override:
                beschreibung = f"Manuelle Eingabe ({kurzname})"

            cursor.execute("""
            INSERT INTO leistungen (patient_id, datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (patient_id, datum_db, time_from, time_to, beschreibung, end_betrag))
            conn.commit()
            return True
        except Exception as e:
            print(f"FEHLER: Fehler beim Speichern der Leistung {kurzname}: {e}")
            return False
        finally:
            conn.close()

    def _insert_multiple_leistungen(self, patient_id, events_list):
        """Fügt mehrere Leistungen aus Teamup-Einträgen in die DB ein."""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        total_success_count = 0
        km_geld = self.get_current_kilometergeld()

        for title, date_str, time_from, time_to in events_list:
            
            # WICHTIG: Die ausgewählten Leistungen (self.selected_leistungs_kurznamen) werden auf jeden Termin angewendet.
            for kurzname in self.selected_leistungs_kurznamen:
                
                # Hole den Betrag für diese Leistung
                # Der Kurzname in stammdaten_betraege ist im Format 'Kurzname - Beschreibung'
                stammdaten_key = [k for k in self.stammdaten_betraege.keys() if k.startswith(kurzname + ' -')]
                if not stammdaten_key:
                    print(f"WARNUNG: Stammdaten für '{kurzname}' nicht gefunden. Überspringe.")
                    continue
                
                standard_betrag = self.stammdaten_betraege[stammdaten_key[0]]
                end_betrag = standard_betrag + km_geld
                
                # Die Beschreibung der Leistung wird aus den Stammdaten übernommen
                final_beschreibung = stammdaten_key[0] 
                
                try:
                    datum_db = datetime.datetime.strptime(date_str, '%d.%m.%Y').strftime('%Y-%m-%d')

                    # Die Beschreibung wird aus den Stammdaten übernommen, nicht aus dem Teamup-Titel
                    cursor.execute("""
                    INSERT INTO leistungen (patient_id, datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (patient_id, datum_db, time_from, time_to, final_beschreibung, end_betrag))
                    total_success_count += 1
                except Exception as e:
                    print(f"FEHLER: Fehler beim Speichern des Termins {date_str} für Leistung {kurzname}: {e}")

        conn.commit()
        conn.close()
        return total_success_count 
    
    # --- ENDE HILFSFUNKTIONEN FÜR LEISTUNGEN --- 

    # --- 3. Leistungen Hinzufügen/Prüfen Tab (Mit Uhrzeiten und Teamup) --- 
    # ... (Rest der Klasse bleibt unverändert)

    def _on_canvas_configure(self, event):
        """Passt die Breite des inneren Frames an die Breite des Canvas an."""
        self.leistung_canvas.itemconfig(self.window_id, width=event.width)

    def setup_leistung_tab(self, tab):
# ... (Rest der Klasse bleibt unverändert)
        ttk.Label(tab, text="Aktueller Patient:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.leistung_patient_label = ttk.Label(tab, text="Bitte Patient in Tab 1 auswählen", foreground='red')
        self.leistung_patient_label.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky='w')

        # Erste Zeile: Datum und Uhrzeit Frame
        date_time_frame = ttk.Frame(tab)
        date_time_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        ttk.Label(date_time_frame, text="Datum (TT.MM.JJJJ):").pack(side=tk.LEFT, padx=(0,5))
        self.date_entry = ttk.Entry(date_time_frame, width=15)
        self.date_entry.pack(side=tk.LEFT, padx=(0,15))
        self.date_entry.insert(0, datetime.date.today().strftime("%d.%m.%Y"))
        ttk.Label(date_time_frame, text="Von (HH:MM):").pack(side=tk.LEFT, padx=(0,5))
        self.time_from_entry = ttk.Entry(date_time_frame, width=8)
        self.time_from_entry.pack(side=tk.LEFT, padx=(0,5))
        self.time_from_entry.insert(0, "11:00")
        ttk.Label(date_time_frame, text="Bis (HH:MM):").pack(side=tk.LEFT, padx=(5,5))
        self.time_to_entry = ttk.Entry(date_time_frame, width=8)
        self.time_to_entry.pack(side=tk.LEFT, padx=(0,5))
        self.time_to_entry.insert(0, "11:50")

        # NEU: Button zum Starten der Kalender-Suche
        ttk.Button(date_time_frame, text="📅 Teamup-Termine Importieren/Ersetzen", command=self.open_teamup_search).pack(side=tk.LEFT, padx=10)

        # Leistungsbuttons Frame (Scrollable)
        leistung_scroll_frame = ttk.Frame(tab)
        leistung_scroll_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')
        
        self.leistung_canvas = tk.Canvas(leistung_scroll_frame)
        self.leistung_canvas.pack(side="left", fill="both", expand=True)

        leistung_scrollbar = ttk.Scrollbar(leistung_scroll_frame, orient="vertical", command=self.leistung_canvas.yview)
        leistung_scrollbar.pack(side="right", fill="y")

        self.leistung_canvas.configure(yscrollcommand=leistung_scrollbar.set)
        self.leistung_canvas.bind('<Configure>', self._on_canvas_configure)

        self.leistung_button_frame = ttk.Frame(self.leistung_canvas)
        self.window_id = self.leistung_canvas.create_window((0, 0), window=self.leistung_button_frame, anchor="nw")
        
        # Zeile 3: Manuelle Beschreibung und Betrag
        manual_frame = ttk.Frame(tab)
        manual_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        
        ttk.Label(manual_frame, text="Manuelle Betragseingabe (€):").pack(side=tk.LEFT, padx=(0,5))
        self.amount_entry = ttk.Entry(manual_frame, width=10)
        self.amount_entry.pack(side=tk.LEFT, padx=(0,15))
        self.amount_entry.insert(0, "0.00")
        
        self.add_leistung_button = ttk.Button(manual_frame, text="Leistung Hinzufügen (Manuell/Auswahl)", command=self.add_leistung_gui)
        self.add_leistung_button.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(manual_frame, text="Zurücksetzen", command=lambda: self._reset_leistung_selection()).pack(side=tk.LEFT, padx=10)

        # Zeile 4: Trennlinie
        ttk.Separator(tab, orient='horizontal').grid(row=4, column=0, columnspan=3, sticky='ew', pady=5)

        # Zeile 5: Gesamtübersicht
        self.summary_label = ttk.Label(tab, text="Gesamtsumme: €0.00 | Nicht abgerechnete Leistungen: 0")
        self.summary_label.grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky='w')

        # Zeile 6: Treeview
        columns = ('ID', 'Datum', 'Von', 'Bis', 'Beschreibung', 'Betrag')
        self.leistung_tree = ttk.Treeview(tab, columns=columns, show='headings', selectmode='browse')
        for col in columns:
            self.leistung_tree.heading(col, text=col)
        
        # Spaltenbreiten 
        self.leistung_tree.column('ID', width=40, anchor='center')
        self.leistung_tree.column('Datum', width=100, anchor='center')
        self.leistung_tree.column('Von', width=60, anchor='center')
        self.leistung_tree.column('Bis', width=60, anchor='center')
        self.leistung_tree.column('Beschreibung', width=300, anchor='w')
        self.leistung_tree.column('Betrag', width=120, anchor='e')
        self.leistung_tree.grid(row=6, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')

        tab.grid_rowconfigure(6, weight=1)

        control_frame = ttk.Frame(tab)
        control_frame.grid(row=7, column=0, columnspan=3, pady=10, sticky='ew')
        ttk.Button(control_frame, text="Leistung Löschen", command=self.delete_leistung_gui).pack(side=tk.LEFT, padx=10)
        ttk.Button(control_frame, text="Alle Leistungen Löschen", command=self.delete_all_leistungen_gui).pack(side=tk.LEFT, padx=10)
        ttk.Button(control_frame, text="Leistung Bearbeiten/Laden", command=self.load_leistung_for_edit).pack(side=tk.RIGHT, padx=10)
        
        self.leistung_tree.bind('<<TreeviewSelect>>', self.select_leistung_for_edit)

    def get_current_kilometergeld(self):
# ... (Rest der Klasse bleibt unverändert)
        """Ruft das Kilometergeld des aktuell ausgewählten Patienten ab."""
        if not self.patient_data:
            return 0.0
        # Kilometergeld ist Spalte 12, Index 11 in patient_data
        km_geld = self.patient_data[11] if len(self.patient_data) > 11 and self.patient_data[11] is not None else 0.0
        return km_geld

    def open_teamup_search(self):
# ... (Rest der Klasse bleibt unverändert)
        """Öffnet einen Dialog zum Suchen und Auswählen von Teamup-Einträgen. Erlaubt Mehrfachauswahl."""
        if not self.patient_data:
            messagebox.showwarning("Achtung", "Bitte wählen Sie zuerst einen Patienten im ersten Tab aus.")
            return
        if not self.selected_leistungs_kurznamen:
            messagebox.showwarning("Achtung", "Bitte wählen Sie zuerst im Hauptfenster mindestens eine Leistung (Button) aus, die den Terminen zugewiesen werden soll.")
            return

        search_window = tk.Toplevel(self.master)
        search_window.title("Teamup Termin-Suche")
        search_window.geometry("600x500")

        ttk.Label(search_window, text="Suchbegriff (Name/Titel):").pack(pady=5, padx=10, anchor='w')
        search_entry = ttk.Entry(search_window, width=60)
        search_entry.pack(pady=5, padx=10)
        search_entry.focus_set()
        
        initial_search_term = self.patient_data[2] if self.patient_data and self.patient_data[2] else ""
        if initial_search_term:
            search_entry.insert(0, initial_search_term)

        results_tree = ttk.Treeview(search_window, columns=('Titel', 'Datum', 'Von', 'Bis'), selectmode='extended', show='headings')
        results_tree.heading('Titel', text='Titel')
        results_tree.heading('Datum', text='Datum')
        results_tree.heading('Von', text='Von')
        results_tree.heading('Bis', text='Bis')
        results_tree.column('Datum', width=90, anchor='center')
        results_tree.column('Von', width=60, anchor='center')
        results_tree.column('Bis', width=60, anchor='center')
        results_tree.pack(pady=10, padx=10, expand=True, fill='both')

        def perform_search(term=None):
            search_term = term if term is not None else search_entry.get().strip()
            results = search_teamup_events(search_term)
            results_tree.delete(*results_tree.get_children())
            if results:
                for title, date, time_from, time_to in results:
                    results_tree.insert('', tk.END, values=(title, date, time_from, time_to))
            else:
                results_tree.insert('', tk.END, values=(f"Keine Termine für '{search_term}' gefunden.", "", "", ""))
                
        def search_by_patient_name():
            perform_search(self.patient_data[2])

        def _get_selected_events_and_validate():
            selected_items = results_tree.selection()
            if not selected_items:
                messagebox.showwarning("Achtung", "Bitte wählen Sie Termine aus der Liste aus.")
                return None

            selected_events_to_add = []
            for item in selected_items:
                title, date_str, time_from, time_to = results_tree.item(item, 'values')
                # Schnelle Validierung der Zeit
                if not (time_from and time_to and ':' in time_from and ':' in time_to):
                    messagebox.showwarning("Fehler", "Ausgewählter Eintrag enthält ungültige Zeitangaben.")
                    return None
                selected_events_to_add.append((title, date_str, time_from, time_to))
            return selected_events_to_add

        def add_selected_events():
            """Fügt ausgewählte Termine HINZU."""
            events = _get_selected_events_and_validate()
            if events:
                self.add_multiple_leistungen_from_teamup(events)
                search_window.destroy()

        def replace_selected_events():
            """Ersetzt alle bestehenden Leistungen mit den ausgewählten Terminen."""
            # Zusätzliche Sicherheitsabfrage für das Ersetzen
            if not messagebox.askyesno("WARNUNG: Leistungen ERSETZEN", "Sind Sie sicher, dass Sie ALLE bestehenden offenen Leistungen dieses Patienten löschen und durch die ausgewählten Termine ERSETZEN möchten?"):
                return
            events = _get_selected_events_and_validate()
            if events:
                self.replace_all_leistungen_from_teamup(events)
                search_window.destroy()

        # --- BUTTONS IM DIALOG ---
        search_button_frame = ttk.Frame(search_window)
        search_button_frame.pack(pady=10)
        ttk.Button(search_button_frame, text="Suchen (Manuell)", command=lambda: perform_search()).pack(side=tk.LEFT, padx=10)
        ttk.Button(search_button_frame, text=f"Nachname ({initial_search_term}) suchen", command=search_by_patient_name, state=tk.NORMAL if self.patient_data else tk.DISABLED).pack(side=tk.LEFT, padx=10)
        
        action_frame = ttk.Frame(search_window)
        action_frame.pack(pady=10)
        ttk.Button(action_frame, text="Termin(e) HINZUFÜGEN (Zu den Bestehenden)", command=add_selected_events).pack(side=tk.LEFT, padx=10)
        
        # NEUER BUTTON FÜR ERSETZEN
        ttk.Button(action_frame, text="WARNUNG: Termin(e) ERSETZEN (Alle Bestehenden Löschen!)", command=replace_selected_events).pack(side=tk.LEFT, padx=10) 

        # Doppelklick auf Eintrag soll Hinzufügen auslösen
        results_tree.bind('<Double-1>', lambda event: add_selected_events())

        search_window.update_idletasks()
        width = search_window.winfo_width()
        height = search_window.winfo_height()
        x = (search_window.winfo_screenwidth() // 2) - (width // 2)
        y = (search_window.winfo_screenheight() // 2) - (height // 2)
        search_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        if self.patient_data:
            perform_search(initial_search_term)

    def load_leistung_stammdaten_buttons(self):
# ... (Rest der Klasse bleibt unverändert)
        """Lädt die Stammdaten und befüllt den Button-Bereich."""
        stammdaten_list, stammdaten_dict = get_all_stammdaten_dict()
        self.stammdaten_betraege = stammdaten_dict 

        # Lösche vorhandene Buttons
        for widget in self.leistung_button_frame.winfo_children():
            widget.destroy()

        # Erstelle neue Buttons
        for i, item in enumerate(stammdaten_list):
            kurzname = item.split(' - ')[0]
            betrag = stammdaten_dict[item]
            
            # Korrigiert: Verwenden Sie self.ttk_style anstelle von self.master.style
            if 'Selected.TButton' not in self.ttk_style.theme_names(): 
                # Definiert den Stil (wird nur einmal ausgeführt)
                self.ttk_style.configure('Selected.TButton', background='light green', foreground='black')

            btn = ttk.Button(self.leistung_button_frame, 
                             text=f"{kurzname} (€{betrag:.2f})", 
                             command=lambda k=kurzname: self.toggle_leistung_selection(k))
            
            btn.kurzname = kurzname
            btn.is_selected = False
            btn.grid(row=i // 5, column=i % 5, padx=5, pady=5, sticky='w')
            
        self.leistung_button_frame.update_idletasks()
        self.leistung_canvas.config(scrollregion=self.leistung_canvas.bbox("all"))

    def load_and_select_last_leistungen(self):
# ... (Rest der Klasse bleibt unverändert)
        """Lädt die zuletzt gespeicherte Leistungsauswahl für den Patienten und wählt die Buttons."""
        if not self.patient_data:
            return 
            
        patient_id = self.patient_data[0]
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # 1. Letzte Auswahl abrufen (Index 12)
        cursor.execute("SELECT last_selected_kurznamen FROM patienten WHERE id = ?", (patient_id,))
        kurznamen_str = cursor.fetchone()[0]
        conn.close()
        
        # 2. Bestehende Auswahl zurücksetzen
        self._reset_leistung_selection()
        
        if not kurznamen_str:
            return

        kurznamen_set = set(kurznamen_str.split(','))
        
        # 3. Buttons entsprechend auswählen
        for kurzname_to_select in kurznamen_set:
            # Finde den Button und wähle ihn aus
            for widget in self.leistung_button_frame.winfo_children():
                if hasattr(widget, 'kurzname') and widget.kurzname == kurzname_to_select:
                    self.selected_leistungs_kurznamen.add(kurzname_to_select)
                    widget.is_selected = True
                    widget.config(style='Selected.TButton')
                    break

    def toggle_leistung_selection(self, kurzname):
# ... (Rest der Klasse bleibt unverändert)
        """Wechselt den Auswahlzustand eines Leistungs-Buttons und passt das Aussehen an."""
        button_ref = None
        for widget in self.leistung_button_frame.winfo_children():
            if hasattr(widget, 'kurzname') and widget.kurzname == kurzname:
                button_ref = widget
                break
        
        if not button_ref:
            return

        if kurzname in self.selected_leistungs_kurznamen:
            # Abwählen
            self.selected_leistungs_kurznamen.remove(kurzname)
            button_ref.is_selected = False
            button_ref.config(style='TButton')
        else:
            # Auswählen
            self.selected_leistungs_kurznamen.add(kurzname)
            button_ref.is_selected = True 
            # Hervorhebung durch eigenen Style
            # Korrigiert: Verwenden Sie self.ttk_style anstelle von self.master.style
            self.ttk_style.configure('Selected.TButton', background='light green', foreground='black')
            button_ref.config(style='Selected.TButton')

    def add_leistung_gui(self):
# ... (Rest der Klasse bleibt unverändert)
        """Fügt neue Leistung(en) in die DB ein, nun mit Uhrzeit und Kilometergeld-Zuschlag."""
        if not self.patient_data:
            messagebox.showwarning("Warnung", "Bitte wählen Sie zuerst einen Patienten aus.")
            return

        patient_id = self.patient_data[0]
        datum_str = self.date_entry.get().strip()
        time_from_str = self.time_from_entry.get().strip()
        time_to_str = self.time_to_entry.get().strip()
        
        manual_betrag, use_manual_override, km_geld = self._get_leistung_insertion_params()

        try:
            datetime.datetime.strptime(datum_str, '%d.%m.%Y')
            if len(time_from_str) < 5 or len(time_to_str) < 5 or ":" not in time_from_str:
                raise ValueError("Uhrzeit muss im Format HH:MM angegeben werden.")
        except ValueError as e:
            messagebox.showerror("Fehler", f"Ungültiges Datums- oder Zeitformat: {e}")
            return
        
        success_count = 0
        
        if use_manual_override:
            # Nur eine Leistung (manuelle) hinzufügen
            kurzname = "Manuell"
            standard_betrag = manual_betrag
            if self.add_leistung_to_db(patient_id, datum_str, time_from_str, time_to_str, kurzname, standard_betrag, manual_betrag, use_manual_override, km_geld):
                success_count = 1
        
        else:
            # Leistungen basierend auf ausgewählten Buttons hinzufügen
            if not self.selected_leistungs_kurznamen:
                messagebox.showwarning("Achtung", "Bitte wählen Sie mindestens eine Leistung aus der Liste aus oder geben Sie einen manuellen Betrag ein.")
                return

            for kurzname in self.selected_leistungs_kurznamen:
                # Finde den vollen Stammdaten-Key für den Betrag
                stammdaten_key = [k for k in self.stammdaten_betraege.keys() if k.startswith(kurzname + ' -')]
                if not stammdaten_key:
                    print(f"WARNUNG: Stammdaten für '{kurzname}' nicht gefunden. Überspringe.")
                    continue
                
                standard_betrag = self.stammdaten_betraege[stammdaten_key[0]]
                
                if self.add_leistung_to_db(patient_id, datum_str, time_from_str, time_to_str, kurzname, standard_betrag, manual_betrag, use_manual_override, km_geld):
                    success_count += 1
            
            # Speichere die aktuelle Auswahl für diesen Patienten
            save_last_selected_leistungen(patient_id, self.selected_leistungs_kurznamen)


        if success_count > 0:
            messagebox.showinfo("Erfolg", f"{success_count} Leistung(en) erfolgreich hinzugefügt.")
            self._reset_leistung_selection()
            self.update_leistung_list()
        elif success_count == 0 and not use_manual_override:
            messagebox.showwarning("Achtung", "Es konnten keine neuen Leistungen hinzugefügt werden (Prüfen Sie, ob Stammdaten fehlen).")

    def add_multiple_leistungen_from_teamup(self, events_list):
# ... (Rest der Klasse bleibt unverändert)
        """Fügt mehrere Leistungen (Teamup) hinzu und speichert die Auswahl."""
        if not self.patient_data or not self.selected_leistungs_kurznamen:
            messagebox.showwarning("Fehler", "Kein Patient oder keine Leistung ausgewählt. Vorgang abgebrochen.")
            return

        patient_id = self.patient_data[0]
        # Hier wird die Kernlogik aufgerufen
        total_success_count = self._insert_multiple_leistungen(patient_id, events_list) 

        if total_success_count > 0:
            # Speichere die aktuelle Auswahl für diesen Patienten
            save_last_selected_leistungen(patient_id, self.selected_leistungs_kurznamen)
            messagebox.showinfo("Erfolg", f"{total_success_count} Leistung(en) für Patient {self.patient_data[2]} erfolgreich hinzugefügt.")
            self._reset_leistung_selection()
            self.update_leistung_list()
        # Keine MessageBox bei 0, da das System das intern loggen kann.

    def replace_all_leistungen_from_teamup(self, events_list):
# ... (Rest der Klasse bleibt unverändert)
        """Löscht alle bestehenden Leistungen des Patienten und fügt die ausgewählten Teamup-Termine als neue Leistungen ein."""
        if not self.patient_data or not self.selected_leistungs_kurznamen:
            print("FEHLER: Kein Patient oder keine Leistung ausgewählt. Vorgang abgebrochen.")
            return

        patient_id = self.patient_data[0]
        patient_name = f"{self.patient_data[1]} {self.patient_data[2]}"

        # 1. Lösche alle bestehenden Leistungen
        if not self._delete_all_patient_leistungen(patient_id):
            messagebox.showerror("Fehler", f"FEHLER: Fehler beim Löschen bestehender Leistungen für Patient {patient_name}. Neue Termine wurden NICHT eingefügt.")
            return

        # 2. Füge neue Leistungen ein
        insertion_success_count = self._insert_multiple_leistungen(patient_id, events_list)

        if insertion_success_count > 0:
            # Speichere die aktuelle Auswahl für diesen Patienten
            save_last_selected_leistungen(patient_id, self.selected_leistungs_kurznamen)
            messagebox.showinfo("Erfolg", f"{insertion_success_count} Leistung(en) für Patient {patient_name} erfolgreich ERSETZT.")
            self._reset_leistung_selection()
            self.update_leistung_list()
        else:
            messagebox.showwarning("Achtung", "Es konnten keine neuen Leistungen hinzugefügt werden (nach dem Löschen).")
            print("INFO: Es konnten keine neuen Leistungen hinzugefügt werden (nach dem Löschen).")

    def update_leistung_list(self):
# ... (Rest der Klasse bleibt unverändert)
        """Aktualisiert die Liste der Leistungen im Treeview."""
        if not self.patient_data:
            self.leistung_tree.delete(*self.leistung_tree.get_children())
            self.summary_label.config(text="Gesamtsumme: €0.00 | Nicht abgerechnete Leistungen: 0")
            return

        patient_id = self.patient_data[0]
        leistungen = get_patient_leistungen(patient_id)

        self.leistung_tree.delete(*self.leistung_tree.get_children())
        total_sum = 0.0

        for leistung in leistungen:
            leistung_id, datum_db, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag = leistung
            datum_formatiert = datetime.datetime.strptime(datum_db, '%Y-%m-%d').strftime('%d.%m.%Y')
            
            # Darstellung des Betrags (bereits inkl. KM-Geld)
            betrag_str = f"€{einzelbetrag:.2f}"
            total_sum += einzelbetrag

            self.leistung_tree.insert('', tk.END, iid=leistung_id, values=(
                leistung_id, datum_formatiert, uhrzeit_von, uhrzeit_bis, beschreibung, betrag_str
            ))

        self.summary_label.config(text=f"Gesamtsumme: €{total_sum:.2f} | Nicht abgerechnete Leistungen: {len(leistungen)}")

    def select_leistung_for_edit(self, event):
# ... (Rest der Klasse bleibt unverändert)
        """Speichert die ID der ausgewählten Leistung."""
        selected_item = self.leistung_tree.focus()
        if selected_item:
            self.selected_leistung_id = self.leistung_tree.item(selected_item)['values'][0]
        else:
            self.selected_leistung_id = None
        
        # Setze den Button zurück, falls nichts ausgewählt ist
        if not self.selected_leistung_id:
            self.add_leistung_button.config(text="Leistung Hinzufügen (Manuell/Auswahl)", command=self.add_leistung_gui)


    def load_leistung_for_edit(self):
# ... (Rest der Klasse bleibt unverändert)
        """Lädt die ausgewählte Leistung in die Eingabefelder zum Bearbeiten."""
        if not hasattr(self, 'selected_leistung_id') or not self.selected_leistung_id:
            messagebox.showwarning("Achtung", "Bitte wählen Sie eine Leistung aus der Liste aus.")
            return

        leistung_id = self.selected_leistung_id
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("""
        SELECT datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag 
        FROM leistungen 
        WHERE id = ? 
        """, (leistung_id,))
        res = cursor.fetchone()
        conn.close()

        if not res:
            messagebox.showerror("Fehler", f"Leistung ID {leistung_id} konnte nicht in der Datenbank gefunden werden.")
            return

        # [0]datum_db, [1]uhrzeit_von, [2]uhrzeit_bis, [3]beschreibung, [4]einzelbetrag (inkl. KM-Geld)
        # Um den Basis-Betrag anzuzeigen, müssen wir das KM-Geld wieder abziehen:
        km_geld = self.get_current_kilometergeld()
        basis_betrag = res[4] - km_geld

        datum_formatiert = datetime.datetime.strptime(res[0], '%Y-%m-%d').strftime('%d.%m.%Y')
        uhrzeit_von = res[1]
        uhrzeit_bis = res[2]
        # beschreibung = res[3] # Beschreibung wird beim Bearbeiten nicht benötigt, da sie aus den Stammdaten kommt

        betrag_str = f"{basis_betrag:.2f}"

        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, datum_formatiert)
        self.time_from_entry.delete(0, tk.END)
        self.time_from_entry.insert(0, uhrzeit_von)
        self.time_to_entry.delete(0, tk.END)
        self.time_to_entry.insert(0, uhrzeit_bis)
        self.amount_entry.delete(0, tk.END)
        self.amount_entry.insert(0, betrag_str)
        
        # NEU: Beim Bearbeiten alle Buttons abwählen, da der Betrag manuell gesetzt wird
        self._reset_leistung_selection() 

        # Button-Funktion auf Update umstellen
        self.add_leistung_button.config(text=f"Leistung Aktualisieren (ID: {leistung_id})", command=lambda: self.update_leistung_gui(leistung_id))
        print(f"INFO: Leistung ID {leistung_id} zum Bearbeiten geladen. Basisbetrag (€{basis_betrag:.2f}) angezeigt.") # messagebox entfernt


    def update_leistung_gui(self, leistung_id):
# ... (Rest der Klasse bleibt unverändert)
        """Aktualisiert eine bestehende Leistung, nun mit Uhrzeit und Kilometergeld-Zuschlag."""
        datum_str = self.date_entry.get().strip()
        time_from_str = self.time_from_entry.get().strip()
        time_to_str = self.time_to_entry.get().strip()
        betrag_str = self.amount_entry.get().strip().replace(',', '.') 

        km_geld = self.get_current_kilometergeld()
        
        try:
            datum_db = datetime.datetime.strptime(datum_str, '%d.%m.%Y').strftime('%Y-%m-%d')
            betrag_basis = float(betrag_str)
            end_betrag = betrag_basis + km_geld

            if len(time_from_str) < 5 or len(time_to_str) < 5 or ":" not in time_from_str:
                raise ValueError("Uhrzeit muss im Format HH:MM angegeben werden.")

            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            
            # Aktualisiere die Beschreibung, da es sich nun um eine manuelle Bearbeitung handelt
            beschreibung = f"Manuelle Korrektur (ID {leistung_id})"

            cursor.execute("""
            UPDATE leistungen
            SET datum=?, uhrzeit_von=?, uhrzeit_bis=?, beschreibung=?, einzelbetrag=?
            WHERE id=?
            """, (datum_db, time_from_str, time_to_str, beschreibung, end_betrag, leistung_id))
            conn.commit()

            messagebox.showinfo("Erfolg", f"Leistung ID {leistung_id} erfolgreich aktualisiert.")
            self.update_leistung_list()
            
            # Setze den Button zurück auf Hinzufügen-Modus
            self.add_leistung_button.config(text="Leistung Hinzufügen (Manuell/Auswahl)", command=self.add_leistung_gui)
            self.selected_leistung_id = None
            
        except ValueError as e:
            messagebox.showerror("Fehler", f"Ungültiges Datums-, Zeit- oder Betragsformat: {e}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Datenbankfehler beim Aktualisieren: {e}")
            conn.close()

    def delete_leistung_gui(self):
# ... (Rest der Klasse bleibt unverändert)
        """Löscht die aktuell ausgewählte Leistung."""
        if not hasattr(self, 'selected_leistung_id') or not self.selected_leistung_id:
            messagebox.showwarning("Achtung", "Bitte wählen Sie die zu löschende Leistung aus der Liste aus.")
            return

        leistung_id = self.selected_leistung_id
        if messagebox.askyesno("Bestätigen", f"Sind Sie sicher, dass Sie die Leistung ID {leistung_id} löschen möchten?"):
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM leistungen WHERE id = ?", (leistung_id,))
                conn.commit()
                print(f"INFO: Leistung ID {leistung_id} erfolgreich gelöscht.") # messagebox entfernt
                self.update_leistung_list()
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Löschen: {e}")
            finally:
                conn.close()

    def delete_all_leistungen_gui(self):
# ... (Rest der Klasse bleibt unverändert)
        """Löscht ALLE Leistungen des aktuell ausgewählten Patienten."""
        if not self.patient_data:
            messagebox.showwarning("Achtung", "Kein Patient ausgewählt.")
            return

        patient_id = self.patient_data[0]
        patient_name = f"{self.patient_data[1]} {self.patient_data[2]}"
        if messagebox.askyesno("WARNUNG", f"Sind Sie sicher, dass Sie ALLE Leistungen für Patient '{patient_name}' (ID: {patient_id}) löschen möchten? Dieser Schritt kann nicht rückgängig gemacht werden."):
            if self._delete_all_patient_leistungen(patient_id):
                print(f"INFO: Alle Leistungen für Patient '{patient_name}' wurden gelöscht.") # messagebox entfernt
                self.update_leistung_list()

    # --- 4. Stammdaten Leistungen Tab ---
    def setup_stammdaten_tab(self, tab):
# ... (Rest der Klasse bleibt unverändert)
        fields = ["Kurzname (Eindeutig)", "Beschreibung", "Standard Betrag (€)"]
        self.stammdaten_entries = {}

        for i, field in enumerate(fields):
            ttk.Label(tab, text=f"{field}:").grid(row=i, column=0, padx=5, pady=5, sticky='w')
            entry = ttk.Entry(tab, width=60)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky='ew')
            self.stammdaten_entries[field] = entry

        ttk.Button(tab, text="Speichern/Aktualisieren", command=self.save_stammdaten).grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Separator(tab, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky='ew', pady=10)

        self.stammdaten_listbox = tk.Listbox(tab, height=10, width=80)
        self.stammdaten_listbox.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky='nsew')
        self.stammdaten_listbox.bind('<<ListboxSelect>>', self.select_stammdaten_from_list)

        control_frame = ttk.Frame(tab)
        control_frame.grid(row=6, column=0, columnspan=2, pady=10, sticky='ew')
        ttk.Button(control_frame, text="Leistung Löschen", command=self.delete_stammdaten).pack(side=tk.LEFT, padx=10)
        
        tab.grid_rowconfigure(5, weight=1)

    def update_stammdaten_list(self):
# ... (Rest der Klasse bleibt unverändert)
        """Aktualisiert die Liste der Stammdaten."""
        self.stammdaten_listbox.delete(0, tk.END)
        stammdaten_list, stammdaten_dict = get_all_stammdaten_dict()
        for item in stammdaten_list:
            betrag = stammdaten_dict[item]
            self.stammdaten_listbox.insert(tk.END, f"{item} (Standard: €{betrag:.2f})")
            
        self.load_leistung_stammdaten_buttons() # Update auch die Buttons

    def select_stammdaten_from_list(self, event):
# ... (Rest der Klasse bleibt unverändert)
        """Lädt die ausgewählte Stammdatenleistung in die Eingabefelder."""
        selection = self.stammdaten_listbox.curselection()
        if selection:
            item_text = self.stammdaten_listbox.get(selection[0])
            # Extrahiere Kurzname, Beschreibung und Betrag
            match = item_text.split(' (Standard: ')
            full_desc = match[0]
            betrag_str = match[1].replace('€', '').replace(')', '')
            
            kurzname = full_desc.split(' - ')[0]
            beschreibung = full_desc.split(' - ')[1]
            
            self.stammdaten_entries["Kurzname (Eindeutig)"].delete(0, tk.END)
            self.stammdaten_entries["Kurzname (Eindeutig)"].insert(0, kurzname)
            self.stammdaten_entries["Beschreibung"].delete(0, tk.END)
            self.stammdaten_entries["Beschreibung"].insert(0, beschreibung)
            self.stammdaten_entries["Standard Betrag (€)"].delete(0, tk.END)
            self.stammdaten_entries["Standard Betrag (€)"].insert(0, betrag_str)


    def save_stammdaten(self):
# ... (Rest der Klasse bleibt unverändert)
        """Speichert oder aktualisiert Stammdaten."""
        kurzname = self.stammdaten_entries["Kurzname (Eindeutig)"].get().strip()
        beschreibung = self.stammdaten_entries["Beschreibung"].get().strip()
        betrag_str = self.stammdaten_entries["Standard Betrag (€)"].get().strip().replace(',', '.')

        if not kurzname or not beschreibung or not betrag_str:
            messagebox.showwarning("Achtung", "Alle Felder müssen ausgefüllt sein.")
            return

        try:
            betrag = float(betrag_str)
        except ValueError:
            messagebox.showwarning("Achtung", "Betrag muss eine gültige Zahl sein.")
            return

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        try:
            # UPDATE (wenn kurzname schon existiert)
            cursor.execute("""
            UPDATE stammdaten_leistungen 
            SET beschreibung = ?, standard_betrag = ?
            WHERE kurzname = ?
            """, (beschreibung, betrag, kurzname))
            
            if cursor.rowcount == 0:
                # INSERT
                cursor.execute("""
                INSERT INTO stammdaten_leistungen (kurzname, beschreibung, standard_betrag)
                VALUES (?, ?, ?)
                """, (kurzname, beschreibung, betrag))
                messagebox.showinfo("Erfolg", f"Neue Leistung '{kurzname}' erfolgreich erstellt.")
            else:
                messagebox.showinfo("Erfolg", f"Leistung '{kurzname}' erfolgreich aktualisiert.")
                
            conn.commit()
            self.update_stammdaten_list()
            
            for entry in self.stammdaten_entries.values():
                 entry.delete(0, tk.END)
                
        except sqlite3.IntegrityError:
            messagebox.showerror("Fehler", f"Kurzname '{kurzname}' existiert bereits. Bitte ändern Sie den Kurznamen.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Datenbankfehler: {e}")
            
        conn.close()

    def delete_stammdaten(self):
# ... (Rest der Klasse bleibt unverändert)
        """Löscht die ausgewählte Stammdatenleistung."""
        selection = self.stammdaten_listbox.curselection()
        if not selection:
            messagebox.showwarning("Achtung", "Bitte wählen Sie eine Leistung aus der Liste aus.")
            return

        item_text = self.stammdaten_listbox.get(selection[0])
        kurzname = item_text.split(' - ')[0]

        if messagebox.askyesno("Bestätigen", f"Sind Sie sicher, dass Sie die Stammdatenleistung '{kurzname}' löschen möchten?"):
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM stammdaten_leistungen WHERE kurzname = ?", (kurzname,))
                conn.commit()
                messagebox.showinfo("Erfolg", f"Stammdatenleistung '{kurzname}' erfolgreich gelöscht.")
                self.update_stammdaten_list()
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Löschen: {e}")
            finally:
                conn.close()


# --- START DER ANWENDUNG ---
if __name__ == "__main__":
    root = tk.Tk()
    app = HonorarGeneratorApp(root)
    root.mainloop()