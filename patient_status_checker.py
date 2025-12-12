# patient_status_checker.py - KORRIGIERT
# Zeigt den Status der Honorarnotenerstellung pro Patient an und erlaubt den Reset.

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import sys

# --- KONFIGURATION ---
# Muss mit der Einstellung in gui_generator.py übereinstimmen
DATABASE_NAME = 'patienten.db'

class PatientStatusApp:
    def __init__(self, master):
        self.master = master
        master.title("Patienten Status: Honorarnote erstellt?")
        master.geometry("500x600")
        
        # Sicherstellen, dass die notwendige Spalte existiert (falls gui_generator.py noch nicht lief)
        self._ensure_status_column()

        ttk.Label(master, text="Patienten-Status (Rot: Honorarnote offen | Grün: Honorarnote erstellt)", 
                  font=('Arial', 10, 'bold')).pack(pady=10)
        
        # Listbox-Ersatz: ttk.Treeview für zuverlässige Farb-Tags
        self.tree = ttk.Treeview(master, columns=('PatientName',), show='headings', height=25)
        self.tree.heading('PatientName', text='Patienten Name')
        self.tree.column('PatientName', width=450, stretch=tk.YES)
        
        # Scrollbar hinzufügen (optional, aber empfohlen für lange Listen)
        scrollbar = ttk.Scrollbar(master, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Layout anpassen, um Scrollbar zu berücksichtigen
        self.tree.pack(padx=10, fill="both", expand=True, side=tk.LEFT)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        
        # Konfigurieren der Tags für die Farben
        # Treeview unterstützt tag_configure direkt
        self.tree.tag_configure('red', foreground='red', font=('Courier New', 12))
        self.tree.tag_configure('green', foreground='green', font=('Courier New', 12))
        
        self.reset_button = ttk.Button(master, 
                                       text="🔴 Status ALLER Patienten auf ROT (OFFEN) zurücksetzen", 
                                       command=self.reset_all_statuses)
        self.reset_button.pack(pady=20, padx=10)
        
        self.load_patient_statuses()

    def _ensure_status_column(self):
        """
        Stellt sicher, dass die Spalte 'invoiced_since_reset' existiert.
        """
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            # Testet, ob die Spalte vorhanden ist
            cursor.execute("SELECT invoiced_since_reset FROM patienten LIMIT 1")
        except sqlite3.OperationalError:
            # Spalte existiert nicht, füge sie hinzu
            cursor.execute("ALTER TABLE patienten ADD COLUMN invoiced_since_reset INTEGER DEFAULT 0")
            conn.commit()
            if 'win' not in sys.platform: # Verhindert doppelte Ausgabe auf Mac/Linux
                 print("INFO: Spalte 'invoiced_since_reset' in patienten-Tabelle hinzugefügt.")
        finally:
            conn.close()

    def load_patient_statuses(self):
        """Lädt alle Patienten und deren Status aus der DB und zeigt sie an."""
        
        # Treeview leeren
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            # Selektiere Name und den Status (0=Rot, 1=Grün)
            cursor.execute("SELECT vorname, nachname, invoiced_since_reset FROM patienten ORDER BY nachname, vorname")
            patients = cursor.fetchall()
            
            if not patients:
                self.tree.insert('', tk.END, values=("Keine Patienten in der Datenbank gefunden.",), tags=('red',))
                return

            for vorname, nachname, status in patients:
                display_name = f"{nachname}, {vorname}"
                # 1 = Grün, 0 oder Null = Rot
                tag = 'green' if status == 1 else 'red' 
                
                # Fügen Sie die Zeile in das Treeview ein und weisen Sie den Tag zu
                self.tree.insert('', tk.END, values=(display_name,), tags=(tag,))
                
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Laden der Patientendaten: {e}")
        finally:
            conn.close()

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
if __name__ == "__main__":
    root = tk.Tk()
    app = PatientStatusApp(root)
    root.mainloop()