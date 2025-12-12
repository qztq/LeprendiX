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

from log_data import log_patient_name 

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


# --- HILFSFUNKTIONEN FÜR DRUCK, DB und API ---

def print_document_silently(file_path):
    """
    Versucht, die angegebene Datei direkt an den Standarddrucker zu senden.
    
    HINWEIS: Das Verhalten (Dialog unterdrücken) ist stark abhängig von
    dem installierten Standardprogramm für .docx-Dateien auf dem OS.
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
    """Sucht Patienten und gibt ID und alle 12 Adressfelder (inkl. Kilometergeld) zurück."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    search_term = f'%{search_name}%'
    # Wichtig: Kilometergeld ist Spalte 12 (Index 11)
    cursor.execute("""
    SELECT id, vorname, nachname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld
    FROM patienten 
    WHERE nachname LIKE ? OR vorname LIKE ?
    """, (search_term, search_term))
    results = cursor.fetchall()
    conn.close()
    return results

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

def fill_template(patient_id, patient_data_tuple):
    """Füllt die Word-Vorlage mit den Patientendaten und Leistungen und speichert sie."""
    
    # patient_data_tuple hat 12 Elemente: Index 0=id, ..., 11=kilometergeld
    _, vorname, nachname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld = patient_data_tuple
    
    leistungen_liste = get_patient_leistungen_for_template(patient_id)
    
    heute = datetime.date.today().strftime("%d.%m.%Y")
    honorar_nummer = f"HN-{datetime.date.today().year}-{datetime.date.today().month:02d}-{patient_id:03d}" 
    
    try:
        document = Document(TEMPLATE_FILE)
    except FileNotFoundError:
        raise FileNotFoundError(f"Die Vorlagendatei '{TEMPLATE_FILE}' wurde nicht gefunden.")
    
    total_betrag = 0.0
    
    # Statische Platzhalter
    replacements = {
        '{{Rechnungsnummer}}': honorar_nummer,
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
            paragraph.text = paragraph.text.replace('{{Gesamt_Betrag}}', gesamt_betrag_str)

    # --- Speichern des Dokuments ---
    log_patient_name(f"{nachname}_{vorname}")
    patient_folder_name = f"{nachname}_{vorname}"
    patient_output_path = os.path.join(OUTPUT_FOLDER, patient_folder_name)
    os.makedirs(patient_output_path, exist_ok=True)
    
    output_filename = f"Honorarnote Krankenkasse {honorar_nummer}.docx"
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

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        self.tab_generate = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_generate, text='📝 Honorarnote Generieren')
        self.setup_generate_tab(self.tab_generate)

        self.tab_patient = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_patient, text='👤 Patienten Verwalten')
        self.setup_patient_tab(self.tab_patient)

        self.tab_leistung = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_leistung, text='➕ Leistungen Hinzufügen/Prüfen')
        self.setup_leistung_tab(self.tab_leistung)
        
        self.tab_stammdaten = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_stammdaten, text='⚙️ Stammdaten Leistungen')
        self.setup_stammdaten_tab(self.tab_stammdaten)
        
        self.update_patient_info() 
        self.load_leistung_stammdaten_for_combobox() 


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
        
        # TODO: Archivierungsbutton hier einfügen, der alle abgerechneten Leistungen markiert

        tab.grid_rowconfigure(1, weight=1)

    def search_patients(self):
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
        selection = self.results_listbox.curselection()
        if selection:
            index = selection[0]
            self.patient_data = self.results_listbox.patient_data_list[index] 
            self.update_patient_info()
            
            # Automatisch zum Leistungs-Tab wechseln und Liste aktualisieren
            self.notebook.select(self.tab_leistung)
            self.update_leistung_list() 

    def update_patient_info(self):
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
            output_path = fill_template(patient_id, self.patient_data) 
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
            # 1. Generiere die Honorarnote
            output_path = fill_template(self.patient_data[0], self.patient_data) 
            
            # 2. Versuche, sie sofort zu drucken
            success, message = print_document_silently(output_path)
            
            if success:
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
            "Kilometergeld (€)" # NEUES FELD
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
        
        # patient_data_tuple: Index 0=id, 1=vorname, ..., 10=diagnose, 11=kilometergeld
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
        messagebox.showinfo("Laden", f"Patient '{patient_data_tuple[1]} {patient_data_tuple[2]}' geladen. Bitte Daten bearbeiten und 'Aktualisieren' klicken.")

    def clear_patient_form(self, clear_defaults=True):
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
                # HINZUFÜGEN
                cursor.execute("""
                INSERT INTO patienten (nachname, vorname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nachname, vorname, strasse, hausnummer, adresszusatz, plz, ort, anrede, versicherungsnummer, diagnose, kilometergeld))
                
                conn.commit()
                messagebox.showinfo("Erfolg", f"Neuer Patient '{vorname} {nachname}' erfolgreich gespeichert.")
                self.clear_patient_form()
                
        except sqlite3.IntegrityError:
            # Wird bei INSERT oder bei Konflikt mit ANDEREM Patienten beim UPDATE ausgelöst
            messagebox.showerror("Fehler", f"Patient '{vorname} {nachname}' mit dieser PLZ existiert bereits in der Datenbank.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Datenbankfehler: {e}")
            
        conn.close()


    # --- 3. Leistungen Hinzufügen/Prüfen Tab (Mit Uhrzeiten und Teamup) ---
    def setup_leistung_tab(self, tab):
        
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
        ttk.Button(date_time_frame, text="📅 Termine aus Teamup laden", command=self.open_teamup_search).pack(side=tk.LEFT, padx=20)


        # Zweite Zeile: Leistung wählen
        ttk.Label(tab, text="Leistung wählen:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.leistung_combobox = ttk.Combobox(tab, width=50, state='readonly')
        self.leistung_combobox.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky='we')
        self.leistung_combobox.bind('<<ComboboxSelected>>', self.load_betrag_from_stammdaten) 
        
        # Dritte Zeile: Betrag
        ttk.Label(tab, text="Basis Betrag (€) + KM-Geld:").grid(row=3, column=0, padx=5, pady=5, sticky='w')
        self.amount_entry = ttk.Entry(tab, width=15)
        self.amount_entry.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        self.add_leistung_button = ttk.Button(tab, text="Leistung Hinzufügen", command=self.add_leistung_gui)
        self.add_leistung_button.grid(row=4, column=0, columnspan=2, pady=10, sticky='w', padx=5)
        
        # NEU: Patient abschließen Button
        ttk.Button(tab, text="Patient Abschließen (zu Generierung)", 
                   command=lambda: self.notebook.select(self.tab_generate)).grid(row=4, column=1, columnspan=2, pady=10, sticky='e', padx=5)


        # --- Treeview und Steuerungs-Buttons ---
        ttk.Label(tab, text="Aktuelle offene Leistungen:").grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        
        self.leistung_tree = ttk.Treeview(tab, columns=('ID', 'Datum', 'Beschreibung', 'Betrag'), show='headings')
        self.leistung_tree.heading('ID', text='ID')
        self.leistung_tree.heading('Datum', text='Datum/Uhrzeit') 
        self.leistung_tree.heading('Beschreibung', text='Beschreibung')
        self.leistung_tree.heading('Betrag', text='Betrag (Inkl. KM-Geld)') # Hinweis auf KM-Geld
        self.leistung_tree.column('ID', width=40, anchor='center') 
        self.leistung_tree.column('Datum', width=160)
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
        """Ruft das Kilometergeld des aktuell ausgewählten Patienten ab."""
        if not self.patient_data:
            return 0.0
        
        # Kilometergeld ist Spalte 12, Index 11 in patient_data
        km_geld = self.patient_data[11] if len(self.patient_data) > 11 and self.patient_data[11] is not None else 0.0
        return km_geld

    def open_teamup_search(self):
        """Öffnet einen Dialog zum Suchen und Auswählen von Teamup-Einträgen. Erlaubt Mehrfachauswahl."""
        
        if not self.patient_data:
            messagebox.showwarning("Achtung", "Bitte wählen Sie zuerst einen Patienten im ersten Tab aus.")
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
        
        results_tree = ttk.Treeview(search_window, columns=('Titel', 'Datum', 'Von', 'Bis'), 
                                    selectmode='extended', 
                                    show='headings')
        results_tree.heading('Titel', text='Titel')
        results_tree.heading('Datum', text='Datum')
        results_tree.heading('Von', text='Von')
        results_tree.heading('Bis', text='Bis')
        results_tree.column('Datum', width=90)
        results_tree.column('Von', width=60, anchor='center')
        results_tree.column('Bis', width=60, anchor='center')
        results_tree.pack(pady=5, padx=10, fill='both', expand=True)

        self._teamup_event_data = [] 

        def perform_search(search_term_override=None):
            """Führt die API-Suche aus und füllt das Treeview."""
            term = search_term_override or search_entry.get().strip()
            
            if not term:
                messagebox.showwarning("Eingabe", "Bitte geben Sie einen Suchbegriff ein.")
                return
            
            for item in results_tree.get_children():
                results_tree.delete(item)
            
            events = search_teamup_events(term)
            self._teamup_event_data = events

            if not events:
                results_tree.insert('', tk.END, values=('Keine Termine gefunden.', '', '', ''))
                return

            for i, (title, date_str, time_from, time_to) in enumerate(events):
                results_tree.insert('', tk.END, values=(title, date_str, time_from, time_to), iid=i)
        
        def search_by_patient_name():
             if self.patient_data:
                 patient_lastname = self.patient_data[2]
                 search_entry.delete(0, tk.END)
                 search_entry.insert(0, patient_lastname)
                 perform_search(patient_lastname)
             else:
                 messagebox.showwarning("Achtung", "Kein Patient ausgewählt.")

        
        # --- FUNKTION ZUERST DEFINIEREN ---
        def load_selected_event(event=None):
            """Speichert ALLE ausgewählten Termine als separate Leistungen."""
            
            selected_ids = results_tree.selection() 
            
            if not selected_ids:
                messagebox.showwarning("Auswahl", "Bitte wählen Sie mindestens einen Termin aus.")
                return

            if not self.leistung_combobox.get():
                messagebox.showwarning("Fehlende Daten", "Bitte wählen Sie im Hauptfenster eine Leistung aus, die für alle Termine verwendet werden soll.")
                return

            selected_events_to_add = []
            
            for selected_id in selected_ids:
                try:
                    index = int(selected_id)
                    event_data = self._teamup_event_data[index] 
                    selected_events_to_add.append(event_data)
                except (IndexError, ValueError):
                    continue

            if not selected_events_to_add:
                messagebox.showwarning("Fehler", "Keine gültigen Termine zur Übernahme gefunden.")
                return
            
            self.add_multiple_leistungen_from_teamup(selected_events_to_add)
            
            search_window.destroy()
            
        # --- HIER WIRD DIE FUNKTION ALS COMMAND VERWENDET ---
        control_frame = ttk.Frame(search_window)
        control_frame.pack(pady=10)

        ttk.Button(control_frame, text="Suchen (Manuell)", command=lambda: perform_search()).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(control_frame, text=f"Nachname ({initial_search_term}) suchen", 
                   command=search_by_patient_name, 
                   state=tk.NORMAL if self.patient_data else tk.DISABLED).pack(side=tk.LEFT, padx=10)

        ttk.Button(search_window, text=f"Termin(e) Übernehmen & Speichern", 
                   command=load_selected_event).pack(pady=5) 
        
        results_tree.bind('<Double-1>', lambda event: load_selected_event())
        
        search_window.update_idletasks()
        width = search_window.winfo_width()
        height = search_window.winfo_height()
        x = (search_window.winfo_screenwidth() // 2) - (width // 2)
        y = (search_window.winfo_screenheight() // 2) - (height // 2)
        search_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        if self.patient_data:
             perform_search(initial_search_term) 


    def load_leistung_stammdaten_for_combobox(self):
        """Lädt die Stammdaten und befüllt die Combobox."""
        stammdaten_list, stammdaten_dict = get_all_stammdaten_dict()
        self.stammdaten_betraege = stammdaten_dict 
        self.leistung_combobox['values'] = stammdaten_list
        if stammdaten_list:
             self.leistung_combobox.set(stammdaten_list[0])
             self.load_betrag_from_stammdaten() 

    def load_betrag_from_stammdaten(self, event=None):
        """Aktualisiert das Betragsfeld basierend auf der Auswahl in der Combobox."""
        selected_key = self.leistung_combobox.get()
        if selected_key in self.stammdaten_betraege:
            betrag = self.stammdaten_betraege[selected_key]
            self.amount_entry.delete(0, tk.END)
            self.amount_entry.insert(0, f"{betrag:.2f}")

    def add_leistung_gui(self):
        """Fügt neue Leistung in die DB ein, nun mit Uhrzeit und Kilometergeld-Zuschlag."""
        if not self.patient_data:
            messagebox.showwarning("Warnung", "Bitte wählen Sie zuerst einen Patienten aus.")
            return

        patient_id = self.patient_data[0]
        datum_str = self.date_entry.get().strip()
        time_from_str = self.time_from_entry.get().strip()
        time_to_str = self.time_to_entry.get().strip()    
        betrag_str = self.amount_entry.get().strip().replace(',', '.')
        selected_leistung = self.leistung_combobox.get() 
        
        if not selected_leistung:
             messagebox.showwarning("Achtung", "Bitte wählen Sie eine Leistung aus den Stammdaten.")
             return
             
        beschreibung = selected_leistung.split(" - ", 1)[1] 
        
        try:
            datetime.datetime.strptime(datum_str, '%d.%m.%Y')
            datum_db = datetime.datetime.strptime(datum_str, '%d.%m.%Y').strftime('%Y-%m-%d')
            betrag = float(betrag_str)
            
            # --- Kilometergeld HINZUFÜGEN ---
            km_geld = self.get_current_kilometergeld()
            end_betrag = betrag + km_geld 
            
            if len(time_from_str) < 5 or len(time_to_str) < 5 or ":" not in time_from_str:
                 raise ValueError("Uhrzeit muss im Format HH:MM angegeben werden.")
                 
        except ValueError as e:
            messagebox.showwarning("Fehler", f"Ungültiges Datum, Betrag oder Uhrzeit: {e}")
            return

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        try:
            cursor.execute("""
            INSERT INTO leistungen (patient_id, datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (patient_id, datum_db, time_from_str, time_to_str, beschreibung, end_betrag))
            
            conn.commit()
            messagebox.showinfo("Erfolg", f"Leistung vom {datum_str} (Gesamt: €{end_betrag:.2f}) erfolgreich hinzugefügt.")
            self.amount_entry.delete(0, tk.END)
            self.update_leistung_list()
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Datenbankfehler: {e}")
            
        conn.close()

    def add_multiple_leistungen_from_teamup(self, events_list):
        """
        Fügt mehrere Leistungen gleichzeitig in die DB ein, basierend auf der Teamup-Auswahl.
        """
        if not self.patient_data:
            messagebox.showwarning("Fehler", "Kein Patient ausgewählt. Vorgang abgebrochen.")
            return

        patient_id = self.patient_data[0]
        selected_leistung = self.leistung_combobox.get() 
        betrag_str = self.amount_entry.get().strip().replace(',', '.')
        
        if not selected_leistung or not betrag_str:
            messagebox.showwarning("Fehler", "Bitte wählen Sie Leistung und Betrag im Hauptfenster aus, bevor Sie Termine übernehmen.")
            return
            
        try:
            basis_betrag = float(betrag_str)
            beschreibung = selected_leistung.split(" - ", 1)[1]
            
            # --- Kilometergeld HINZUFÜGEN ---
            km_geld = self.get_current_kilometergeld()
            end_betrag = basis_betrag + km_geld
            
        except ValueError:
            messagebox.showerror("Fehler", "Ungültiger Betrag.")
            return

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        success_count = 0
        
        for title, date_str, time_from, time_to in events_list:
            try:
                # Datum in DB-Format konvertieren (von TT.MM.JJJJ zu YYYY-MM-DD)
                datum_db = datetime.datetime.strptime(date_str, '%d.%m.%Y').strftime('%Y-%m-%d')
                
                cursor.execute("""
                INSERT INTO leistungen (patient_id, datum, uhrzeit_von, uhrzeit_bis, beschreibung, einzelbetrag)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (patient_id, datum_db, time_from, time_to, beschreibung, end_betrag)) 
                
                success_count += 1
                
            except Exception as e:
                print(f"Fehler beim Speichern des Termins {date_str}: {e}")
        
        conn.commit()
        conn.close()
        
        if success_count > 0:
            messagebox.showinfo("Erfolg", f"{success_count} Leistung(en) für Patient {self.patient_data[2]} erfolgreich hinzugefügt.\n(Je €{end_betrag:.2f})")
            self.update_leistung_list()
        else:
            messagebox.showwarning("Ergebnis", "Es konnten keine neuen Leistungen hinzugefügt werden.")


    def update_leistung_list(self):
        """Aktualisiert die Liste der Leistungen im Treeview."""
        self.update_patient_info() 

        if not self.patient_data:
            for item in self.leistung_tree.get_children():
                self.leistung_tree.delete(item)
            self.leistung_tree.insert('', tk.END, values=('---', 'Bitte Patient auswählen', '---', '---'))
            return

        patient_id = self.patient_data[0]
        
        for item in self.leistung_tree.get_children():
            self.leistung_tree.delete(item)

        leistungen = get_patient_leistungen(patient_id) 
        
        if not leistungen:
            self.leistung_tree.insert('', tk.END, values=('---', 'Keine offenen Leistungen gefunden', '---', '---'))
            return

        total_sum = 0
        for leistung_id, datum_db, uhrzeit_von, uhrzeit_bis, beschreibung, betrag in leistungen: 
            datum_formatiert = datetime.datetime.strptime(datum_db, '%Y-%m-%d').strftime('%d.%m.%Y')
            
            datum_uhrzeit_anzeige = f"{datum_formatiert} ({uhrzeit_von}-{uhrzeit_bis})" 
            
            betrag_formatiert = f"€ {betrag:.2f}"
            
            self.leistung_tree.insert('', tk.END, values=(leistung_id, datum_uhrzeit_anzeige, beschreibung, betrag_formatiert), iid=leistung_id)
            total_sum += betrag
            
        self.leistung_tree.insert('', tk.END, values=('', '---', 'Gesamtbetrag (offen) ---', f"€ {total_sum:.2f}"), tags=('total',))
        self.leistung_tree.tag_configure('total', font=('Helvetica', 10, 'bold'))

    def select_leistung_for_edit(self, event):
        """Speichert die ID der ausgewählten Leistung für die Bearbeitung/Löschung."""
        # Sicherstellen, dass die Auswahl keine 'total'-Zeile ist
        focus_id = self.leistung_tree.focus()
        if focus_id and focus_id != '':
            item_values = self.leistung_tree.item(focus_id, 'values')
            if item_values and item_values[0] != '---' and item_values[0] != '':
                 self.selected_leistung_id = focus_id
        
    def load_leistung_for_edit(self):
        """Lädt ausgewählte Leistung in die Eingabefelder zum Bearbeiten."""
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
        beschreibung = res[3]
        
        betrag_str = f"{basis_betrag:.2f}"

        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, datum_formatiert)
        self.time_from_entry.delete(0, tk.END)
        self.time_from_entry.insert(0, uhrzeit_von)
        self.time_to_entry.delete(0, tk.END)
        self.time_to_entry.insert(0, uhrzeit_bis)
        self.amount_entry.delete(0, tk.END)
        self.amount_entry.insert(0, betrag_str)
        
        found_match = False
        for item in self.leistung_combobox['values']:
             if beschreibung in item: 
                 self.leistung_combobox.set(item)
                 found_match = True
                 break
        
        if not found_match:
             messagebox.showwarning("Stammdaten", "Beschreibung konnte nicht in Stammdaten gefunden werden. Bitte Leistung manuell wählen.")
             
        # Button-Funktion auf Update umstellen
        self.add_leistung_button.config(text=f"Leistung Aktualisieren (ID: {leistung_id})", command=lambda: self.update_leistung_gui(leistung_id))
        messagebox.showinfo("Laden", f"Leistung ID {leistung_id} zum Bearbeiten geladen. Basisbetrag (€{basis_betrag:.2f}) angezeigt.")

    def update_leistung_gui(self, leistung_id):
        """Aktualisiert eine bestehende Leistung, nun mit Uhrzeit und Kilometergeld-Zuschlag."""
        datum_str = self.date_entry.get().strip()
        time_from_str = self.time_from_entry.get().strip()
        time_to_str = self.time_to_entry.get().strip()
        betrag_str = self.amount_entry.get().strip().replace(',', '.') # Basisbetrag
        selected_leistung = self.leistung_combobox.get()
        
        if not selected_leistung:
             messagebox.showwarning("Achtung", "Bitte wählen Sie eine Leistung aus den Stammdaten.")
             return
             
        beschreibung = selected_leistung.split(" - ", 1)[1] 
        
        try:
            datetime.datetime.strptime(datum_str, '%d.%m.%Y')
            datum_db = datetime.datetime.strptime(datum_str, '%d.%m.%Y').strftime('%Y-%m-%d')
            basis_betrag = float(betrag_str)
            
            # --- Kilometergeld HINZUFÜGEN ---
            km_geld = self.get_current_kilometergeld()
            end_betrag = basis_betrag + km_geld
            
            if len(time_from_str) < 5 or len(time_to_str) < 5 or ":" not in time_from_str:
                 raise ValueError("Uhrzeit muss im Format HH:MM angegeben werden.")
                 
        except ValueError as e:
            messagebox.showwarning("Fehler", f"Ungültiges Datum, Betrag oder Uhrzeit: {e}")
            return

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        try:
            cursor.execute("""
            UPDATE leistungen 
            SET datum = ?, uhrzeit_von = ?, uhrzeit_bis = ?, beschreibung = ?, einzelbetrag = ?
            WHERE id = ?
            """, (datum_db, time_from_str, time_to_str, beschreibung, end_betrag, leistung_id))
            
            conn.commit()
            messagebox.showinfo("Erfolg", f"Leistung ID {leistung_id} erfolgreich aktualisiert (Gesamt: €{end_betrag:.2f}).")
            self.update_leistung_list()
            self.add_leistung_button.config(text="Leistung Hinzufügen", command=self.add_leistung_gui) # Button zurücksetzen
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Datenbankfehler beim Aktualisieren: {e}")
            
        conn.close()

    def delete_leistung_gui(self):
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
                messagebox.showinfo("Erfolg", f"Leistung ID {leistung_id} erfolgreich gelöscht.")
                self.update_leistung_list()
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Löschen: {e}")
            finally:
                conn.close()

    def delete_all_leistungen_gui(self):
        """Löscht ALLE Leistungen des aktuell ausgewählten Patienten."""
        if not self.patient_data:
            messagebox.showwarning("Achtung", "Kein Patient ausgewählt.")
            return

        patient_id = self.patient_data[0]
        patient_name = f"{self.patient_data[1]} {self.patient_data[2]}"
        
        if messagebox.askyesno("WARNUNG", f"Sind Sie sicher, dass Sie ALLE Leistungen für Patient '{patient_name}' (ID: {patient_id}) löschen möchten? Dieser Schritt kann nicht rückgängig gemacht werden."):
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM leistungen WHERE patient_id = ?", (patient_id,))
                conn.commit()
                messagebox.showinfo("Erfolg", f"Alle Leistungen für Patient '{patient_name}' wurden gelöscht.")
                self.update_leistung_list()
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Löschen: {e}")
            finally:
                conn.close()


    # --- 4. Stammdaten Leistungen Tab ---
    def setup_stammdaten_tab(self, tab):
        fields = ["Kurzname (Eindeutig)", "Beschreibung", "Standard Betrag (€)"]
        self.stammdaten_entries = {}

        for i, field in enumerate(fields):
            ttk.Label(tab, text=f"{field}:").grid(row=i, column=0, padx=5, pady=5, sticky='w')
            entry = ttk.Entry(tab, width=40)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky='we')
            self.stammdaten_entries[field] = entry
            
        ttk.Button(tab, text="Leistung Speichern / Aktualisieren", command=self.add_stammdaten_leistung).grid(row=len(fields), column=0, columnspan=2, pady=10)

        ttk.Label(tab, text="Bestehende Stammdaten (Klicken zum Bearbeiten):").grid(row=len(fields)+1, column=0, columnspan=2, padx=5, pady=5, sticky='w')
        
        self.stammdaten_tree = ttk.Treeview(tab, columns=('Kurzname', 'Beschreibung', 'Betrag'), show='headings')
        self.stammdaten_tree.heading('Kurzname', text='Kurzname')
        self.stammdaten_tree.heading('Beschreibung', text='Beschreibung')
        self.stammdaten_tree.heading('Betrag', text='Betrag')
        self.stammdaten_tree.column('Kurzname', width=100)
        self.stammdaten_tree.column('Betrag', width=100, anchor='e')
        self.stammdaten_tree.grid(row=len(fields)+2, column=0, columnspan=2, padx=5, pady=5, sticky='nsew')
        
        self.stammdaten_tree.bind('<<TreeviewSelect>>', self.load_stammdaten_for_edit)
        
        tab.grid_rowconfigure(len(fields)+2, weight=1)
        
        self.update_stammdaten_list()
        
    def update_stammdaten_list(self):
        """Aktualisiert das Treeview mit allen Stammdaten."""
        for item in self.stammdaten_tree.get_children():
            self.stammdaten_tree.delete(item)
            
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT kurzname, beschreibung, standard_betrag FROM stammdaten_leistungen ORDER BY kurzname")
        results = cursor.fetchall()
        conn.close()

        for kurzname, beschreibung, betrag in results:
             self.stammdaten_tree.insert('', tk.END, values=(kurzname, beschreibung, f"€ {betrag:.2f}"), iid=kurzname)
             
        self.load_leistung_stammdaten_for_combobox()

    def load_stammdaten_for_edit(self, event):
        """Lädt ausgewählte Stammdaten in die Eingabefelder zum Bearbeiten."""
        selected_item = self.stammdaten_tree.focus() 
        
        if selected_item:
            kurzname = selected_item 
            
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT beschreibung, standard_betrag FROM stammdaten_leistungen WHERE kurzname = ?", (kurzname,))
            res = cursor.fetchone()
            conn.close()
            
            if res:
                self.stammdaten_entries["Kurzname (Eindeutig)"].delete(0, tk.END)
                self.stammdaten_entries["Kurzname (Eindeutig)"].insert(0, kurzname)
                self.stammdaten_entries["Beschreibung"].delete(0, tk.END)
                self.stammdaten_entries["Beschreibung"].insert(0, res[0])
                self.stammdaten_entries["Standard Betrag (€)"].delete(0, tk.END)
                self.stammdaten_entries["Standard Betrag (€)"].insert(0, f"{res[1]:.2f}")
                
    def add_stammdaten_leistung(self):
        """Fügt neue Leistung hinzu oder aktualisiert bestehende."""
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


# --- START DER ANWENDUNG ---
if __name__ == "__main__":
    root = tk.Tk()
    app = HonorarGeneratorApp(root)
    root.mainloop()