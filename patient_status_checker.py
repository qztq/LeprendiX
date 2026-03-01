import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import sys
import shutil
import json
from config_loader import CONFIG

class PatientStatusApp:
    def __init__(self, master, selection_callback=None, archive_callback=None):
        self.master = master
        self.selection_callback = selection_callback
        self.archive_callback = archive_callback
        master.title("Patienten Status & Archivierung")
        master.geometry("400x780") 
        self.after_id = None
        
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
        self.tree.column('PatientName', width=300, stretch=tk.YES)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        
        self.tree.tag_configure('red', foreground='red', font=('Courier New', 11))
        self.tree.tag_configure('green', foreground='green', font=('Courier New', 11))
        
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        
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
        self._schedule_refresh()
        self.master.bind("<Destroy>", self._on_destroy)

    def on_double_click(self, event):
        if self.selection_callback:
            selection = self.tree.selection()
            if selection:
                # selection[0] ist die patient_id (iid)
                patient_id = selection[0]
                self.selection_callback(str(patient_id))
                # Auswahl nach Doppelklick aufheben
                self.tree.selection_remove(*selection)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = tk.Menu(self.master, tearoff=0)
            menu.add_command(label="📂 Im Explorer öffnen", command=self.open_in_explorer)
            menu.add_command(label="✅ Auf Grün setzen", command=self.set_to_green)
            menu.add_command(label="📦 Archivieren", command=self.archive_selected_patient)
            menu.post(event.x_root, event.y_root)

    def open_in_explorer(self):
        selected_item = self.tree.selection()
        if not selected_item: return
        patient_id = selected_item[0]
        
        try:
            db_name = CONFIG.get('DATABASE_NAME', 'patienten.db')
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT vorname, nachname FROM patienten WHERE id=?", (patient_id,))
            res = cursor.fetchone()
            conn.close()
            
            if res:
                v_name, n_name = res
                folder_name = f"{n_name} {v_name}"
                patient_base_dir = CONFIG.get('PATIENT_BASE_DIR')
                path = os.path.join(patient_base_dir, folder_name)
                
                if os.path.exists(path):
                    if sys.platform == 'win32':
                        os.startfile(path)
                    else:
                        import subprocess
                        subprocess.Popen(['xdg-open', path])
                else:
                    messagebox.showinfo("Info", f"Ordner nicht gefunden:\n{path}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Ordner nicht öffnen: {e}")

    def set_to_green(self):
        selected_item = self.tree.selection()
        if not selected_item: return
        patient_id = selected_item[0]
        
        try:
            db_name = CONFIG.get('DATABASE_NAME', 'patienten.db')
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            cursor.execute("UPDATE patienten SET invoiced_since_reset = 1 WHERE id=?", (patient_id,))
            conn.commit()
            conn.close()
            self.load_patient_statuses()
        except Exception as e:
            messagebox.showerror("Fehler", f"Datenbankfehler: {e}")
    
    def _ensure_archive_dir(self):
        """Stellt sicher, dass der Archiv-Ordner existiert."""
        archive_dir = CONFIG.get('ARCHIVE_DIR')
        if archive_dir and not os.path.exists(archive_dir):
            os.makedirs(archive_dir)

    def _ensure_status_column(self):
        db_name = CONFIG.get('DATABASE_NAME', 'patienten.db')
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT invoiced_since_reset FROM patienten LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE patienten ADD COLUMN invoiced_since_reset INTEGER DEFAULT 0")
            conn.commit()
        
        try:
            cursor.execute("SELECT is_archived FROM patienten LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE patienten ADD COLUMN is_archived INTEGER DEFAULT 0")
            conn.commit()
        finally:
            conn.close()

    def _schedule_refresh(self):
        self.after_id = self.master.after(5000, self._periodic_refresh)

    def _on_destroy(self, event):
        if event.widget == self.master:
            if self.after_id:
                try:
                    self.master.after_cancel(self.after_id)
                except Exception:
                    pass
            self.after_id = None

    def _periodic_refresh(self):
        try:
            if not self.master.winfo_exists():
                return
        except Exception:
            return
        # Nur aktualisieren, wenn der User gerade nichts ausgewählt hat (verhindert Flackern)
        if not self.tree.selection():
            self.load_patient_statuses()
        self._schedule_refresh()
    
    def load_patient_statuses(self):
        # Selektion merken
        current_selection = self.tree.selection()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            db_name = CONFIG.get('DATABASE_NAME', 'patienten.db')
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT id, vorname, nachname, invoiced_since_reset FROM patienten WHERE (is_archived IS NULL OR is_archived = 0) ORDER BY nachname, vorname")
            
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
            db_name = CONFIG.get('DATABASE_NAME', 'patienten.db')
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT vorname, nachname FROM patienten WHERE id=?", (patient_id,))
            res = cursor.fetchone()
            
            if res:
                v_name, n_name = res
                folder_name = f"{n_name} {v_name}"
                
                # 1. Versuch: Standardpfad aus Config
                patient_base_dir = CONFIG.get('PATIENT_BASE_DIR')
                source_path = os.path.join(patient_base_dir, folder_name)
                
                # 2. Versuch: Wenn nicht gefunden, dann fragen
                if not os.path.exists(source_path):
                    messagebox.showinfo("Ordner suchen", 
                        f"Der Standardordner für '{folder_name}' wurde nicht unter '{patient_base_dir}' gefunden.\n"
                        "Bitte wählen Sie den Patientenordner manuell aus.")
                    
                    # Öffnet Verzeichnisauswahl
                    source_path = filedialog.askdirectory(title=f"Ordner für {folder_name} auswählen")
                    
                    if not source_path: # Abgebrochen
                        return

                # Zielpfad im Archiv
                archive_dir = CONFIG.get('ARCHIVE_DIR')
                if not os.path.exists(archive_dir):
                    os.makedirs(archive_dir)
                
                dest_path = os.path.join(archive_dir, os.path.basename(source_path))

                # Verschieben
                if os.path.exists(source_path):
                    # Falls im Archiv schon ein Ordner so heißt, hängen wir einen Zeitstempel an
                    if os.path.exists(dest_path):
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        dest_path = f"{dest_path}_{timestamp}"

                    shutil.move(source_path, dest_path)
                    
                    # Erst wenn das Verschieben geklappt hat, Status auf archiviert setzen (NICHT LÖSCHEN)
                    cursor.execute("UPDATE patienten SET is_archived = 1 WHERE id=?", (patient_id,))
                    
                    # NEU: Prüfen, ob noch andere aktive Patienten den gleichen Nachnamen haben
                    cursor.execute("SELECT COUNT(*) FROM patienten WHERE nachname = ? AND is_archived = 0 AND id != ?", (n_name, patient_id))
                    active_patients_with_same_name = cursor.fetchone()[0]
                    
                    # Nur die Stammdatenleistung archivieren, wenn dies der LETZTE aktive Patient mit dem Namen war
                    if active_patients_with_same_name == 0:
                        cursor.execute("UPDATE stammdaten_leistungen SET is_archived = 1 WHERE kurzname=?", (n_name,))
                    
                    conn.commit()
                    
                    messagebox.showinfo("Erfolg", f"Patient {full_name} wurde erfolgreich ins Archiv verschoben.")
                    self.load_patient_statuses()
                    
                    # Rufen Sie den Callback auf, um die Haupt-GUI zu aktualisieren
                    if self.archive_callback:
                        self.archive_callback()
                else:
                    messagebox.showerror("Fehler", "Der gewählte Ordner existiert nicht.")
                    
        except Exception as e:
            messagebox.showerror("Fehler", f"Archivierung fehlgeschlagen:\n{e}")
        finally:
            conn.close()

    def reset_all_statuses(self):
        if not messagebox.askyesno("Reset", "Alle auf ROT setzen?"):
            return
        db_name = CONFIG.get('DATABASE_NAME', 'patienten.db')
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("UPDATE patienten SET invoiced_since_reset = 0")
        conn.commit()
        conn.close()
        self.load_patient_statuses()


def start_checker():
    """Diese Funktion wird von main.py aufgerufen."""
    root = tk.Tk()
    # Wir erstellen eine Instanz deiner App-Klasse
    app = PatientStatusApp(root)
    root.mainloop()

    
if __name__ == '__main__':
    start_checker()