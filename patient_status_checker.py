# patient_status_checker.py - BEREINIGTE ENDVERSION
# Zeigt den Status der Honorarnotenerstellung pro Patient an und erlaubt den Reset.

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import sys

# --- KONFIGURATION ---
DATABASE_NAME = 'patienten.db'

class PatientStatusApp:
    def __init__(self, master):
        self.master = master
        master.title("Patienten Status: Honorarnote erstellt?")
        master.geometry("500x650") 
        
        self._ensure_status_column()

        ttk.Label(master, text="Patienten-Status (Rot: Honorarnote offen | Grün: Honorarnote erstellt)", 
                  font=('Arial', 10, 'bold')).pack(pady=10)
        
        # Treeview (ersetzt Listbox)
        self.tree = ttk.Treeview(master, columns=('PatientID', 'PatientName'), show='headings', height=25)
        
        self.tree.heading('PatientID', text='ID')
        self.tree.column('PatientID', width=40, stretch=tk.NO, anchor='center') 
        
        self.tree.heading('PatientName', text='Patienten Name')
        self.tree.column('PatientName', width=410, stretch=tk.YES)
        
        # Scrollbar hinzufügen
        scrollbar = ttk.Scrollbar(master, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(padx=10, fill="both", expand=True, side=tk.LEFT)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        
        # Konfigurieren der Tags für die Farben
        self.tree.tag_configure('red', foreground='red', font=('Courier New', 12))
        self.tree.tag_configure('green', foreground='green', font=('Courier New', 12))
        
        # Lade die Initialdaten
        self.load_patient_statuses() 
        
        # --- SICHTBARER RESET-KNOPF ---
        ttk.Button(master, text="⚠️ ALLE PATIENTEN AUF ROT ZURÜCKSETZEN ⚠️", 
                   command=self.reset_all_statuses, style='Danger.TButton').pack(pady=10, padx=10, fill='x')
                   
        style = ttk.Style()
        style.configure('Danger.TButton', foreground='red', font=('Arial', 10, 'bold'))

        # --- LIVE-AKTUALISIERUNG START ---
        # Führt den ersten Refresh nach 5000ms aus und speichert die Job-ID
        self.master.after_id = self.master.after(5000, self._periodic_refresh) 


    def _ensure_status_column(self):
        # ... (Unverändert) ...
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT invoiced_since_reset FROM patienten LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE patienten ADD COLUMN invoiced_since_reset INTEGER DEFAULT 0")
            conn.commit()
            print("INFO: Spalte 'invoiced_since_reset' in patienten-Tabelle hinzugefügt.")
        finally:
            conn.close()

    # --- KORRIGIERT: PERIODISCHE AKTUALISIERUNG ---
    def _periodic_refresh(self):
        """Aktualisiert die Liste alle 5 Sekunden (5000ms)."""
        self.load_patient_statuses()
        # Setzt den nächsten Timer und speichert seine ID (wichtig für after_cancel, falls benötigt)
        self.master.after_id = self.master.after(5000, self._periodic_refresh) 
    
    # --- load_patient_statuses (unverändert) ---
    def load_patient_statuses(self):
        """Lädt alle Patienten aus der DB und zeigt ihren Status an."""
        
        # Vorherige Einträge löschen
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            # ID, Vorname, Nachname, Status
            cursor.execute("SELECT id, vorname, nachname, invoiced_since_reset FROM patienten ORDER BY nachname, vorname")
            
            for patient_id, vorname, nachname, status in cursor.fetchall():
                display_name = f"{nachname} {vorname}"
                # Status 1 = Grün (Abgerechnet), Null = Rot (Offen)
                tag = 'green' if status == 1 else 'red' 
                
                # Fügen Sie die Zeile mit ID und Name in das Treeview ein
                self.tree.insert('', tk.END, values=(patient_id, display_name), tags=(tag,))
                
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Laden der Patientendaten: {e}")
        finally:
            conn.close()

    # --- reset_all_statuses (unverändert) ---
    def reset_all_statuses(self):
        """Setzt den Status aller Patienten auf 0 (Rot/Offen)."""
        if not messagebox.askyesno("Status Reset Bestätigen", 
                                   "Sollen wirklich ALLE Patienten auf den Status 'ROT' (Honorar offen) zurückgesetzt werden?"):
            return

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            # Setze alle Status auf 0 (Rot/Offen)
            cursor.execute("UPDATE patienten SET invoiced_since_reset = 0")
            conn.commit()
            messagebox.showinfo("Reset erfolgreich", "Der Status aller Patienten wurde erfolgreich auf 'ROT' zurückgesetzt.")
            self.load_patient_statuses() # Liste neu laden
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Zurücksetzen des Status: {e}")
        finally:
            conn.close()


# --- START DER ANWENDUNG ---
if __name__ == '__main__':
    root = tk.Tk()
    # Der after_id Parameter muss dem root-Objekt zugewiesen werden, auch wenn er nicht verwendet wird,
    # um Fehler zu vermeiden, falls er im Code verbleibt.
    root.after_id = None 
    app = PatientStatusApp(root)
    root.mainloop()