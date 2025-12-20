import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import shutil
import json
from config_loader import DATABASE_NAME, PATIENT_BASE_DIR, ARCHIVE_DIR




DATABASE_NAME = DATABASE_NAME
PATIENT_BASE_DIR = PATIENT_BASE_DIR
ARCHIVE_DIR = ARCHIVE_DIR

class PatientStatusApp:
    def __init__(self, master):
        self.master = master
        master.title("Patienten Status & Archivierung")
        master.geometry("600x750") 
        
        self._ensure_status_column()
        self._ensure_archive_dir()

        ttk.Label(master, text="Patienten-Status (Rot: Offen | Grün: Erstellt)", 
                  font=('Arial', 10, 'bold')).pack(pady=10)
        
        # Frame für Treeview und Scrollbar
        tree_frame = ttk.Frame(master)
        tree_frame.pack(padx=10, fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=('PatientID', 'PatientName'), show='headings', height=20)
        self.tree.heading('PatientID', text='ID')
        self.tree.column('PatientID', width=40, stretch=tk.NO, anchor='center') 
        self.tree.heading('PatientName', text='Patienten Name')
        self.tree.column('PatientName', width=450, stretch=tk.YES)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        
        self.tree.tag_configure('red', foreground='red', font=('Courier New', 11))
        self.tree.tag_configure('green', foreground='green', font=('Courier New', 11))
        
        # --- BUTTONS ---
        button_frame = ttk.Frame(master)
        button_frame.pack(pady=10, fill='x', padx=10)

        # Archivieren Button (für selektierte Zeile)
        self.archive_btn = ttk.Button(button_frame, text="📁 Ausgewählten Patienten archivieren", 
                                     command=self.archive_selected_patient)
        self.archive_btn.pack(side=tk.LEFT, expand=True, fill='x', padx=5)

        # Reset Button
        ttk.Button(button_frame, text="🔄 Alle auf Rot", 
                   command=self.reset_all_statuses).pack(side=tk.LEFT, expand=True, fill='x', padx=5)

        self.load_patient_statuses() 
        self.master.after(5000, self._periodic_refresh) 

    
    def _ensure_archive_dir(self):
        """Stellt sicher, dass der Archiv-Ordner existiert."""
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)

    def _ensure_status_column(self):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT invoiced_since_reset FROM patienten LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE patienten ADD COLUMN invoiced_since_reset INTEGER DEFAULT 0")
            conn.commit()
        finally:
            conn.close()

    def _periodic_refresh(self):
        # Nur aktualisieren, wenn der User gerade nichts ausgewählt hat (verhindert Flackern)
        if not self.tree.selection():
            self.load_patient_statuses()
        self.master.after(5000, self._periodic_refresh) 
    
    def load_patient_statuses(self):
        # Selektion merken
        current_selection = self.tree.selection()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT id, vorname, nachname, invoiced_since_reset FROM patienten ORDER BY nachname, vorname")
            
            for p_id, vorname, nachname, status in cursor.fetchall():
                display_name = f"{nachname} {vorname}"
                tag = 'green' if status == 1 else 'red' 
                self.tree.insert('', tk.END, iid=p_id, values=(p_id, display_name), tags=(tag,))
        except Exception as e:
            print(f"Fehler beim Laden: {e}")
        finally:
            conn.close()

    def archive_selected_patient(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Auswahl fehlt", "Bitte wählen Sie einen Patienten aus.")
            return

        patient_id = selected_item[0]
        full_name = self.tree.item(patient_id, 'values')[1]
        
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT vorname, nachname FROM patienten WHERE id=?", (patient_id,))
            res = cursor.fetchone()
            
            if res:
                v_name, n_name = res
                folder_name = f"{n_name} {v_name}"
                
                # 1. Versuch: Standardpfad (Desktop)
                source_path = os.path.join(PATIENT_BASE_DIR, folder_name)
                
                # 2. Versuch: Wenn nicht auf Desktop, dann fragen
                if not os.path.exists(source_path):
                    messagebox.showinfo("Ordner suchen", 
                        f"Der Standardordner für '{folder_name}' wurde nicht auf dem Desktop gefunden.\n"
                        "Bitte wählen Sie den Patientenordner manuell aus.")
                    
                    # Öffnet Verzeichnisauswahl
                    source_path = filedialog.askdirectory(title=f"Ordner für {folder_name} auswählen")
                    
                    if not source_path: # Abgebrochen
                        return

                # Zielpfad im Archiv
                if not os.path.exists(ARCHIVE_DIR):
                    os.makedirs(ARCHIVE_DIR)
                
                dest_path = os.path.join(ARCHIVE_DIR, os.path.basename(source_path))

                # Verschieben
                if os.path.exists(source_path):
                    # Falls im Archiv schon ein Ordner so heißt, hängen wir einen Zeitstempel an
                    if os.path.exists(dest_path):
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        dest_path = f"{dest_path}_{timestamp}"

                    shutil.move(source_path, dest_path)
                    
                    # Erst wenn das Verschieben geklappt hat, aus DB löschen
                    cursor.execute("DELETE FROM patienten WHERE id=?", (patient_id,))
                    conn.commit()
                    
                    messagebox.showinfo("Erfolg", f"Patient {full_name} wurde erfolgreich ins Archiv verschoben.")
                    self.load_patient_statuses()
                else:
                    messagebox.showerror("Fehler", "Der gewählte Ordner existiert nicht.")
                    
        except Exception as e:
            messagebox.showerror("Fehler", f"Archivierung fehlgeschlagen:\n{e}")
        finally:
            conn.close()

    def reset_all_statuses(self):
        if not messagebox.askyesno("Reset", "Alle auf ROT setzen?"):
            return
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE patienten SET invoiced_since_reset = 0")
        conn.commit()
        conn.close()
        self.load_patient_statuses()

if __name__ == '__main__':
    root = tk.Tk()
    app = PatientStatusApp(root)
    root.mainloop()