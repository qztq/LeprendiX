# verlauf_fenster.py
# Zeigt die Liste der zuletzt bearbeiteten Patienten an.

import tkinter as tk
from tkinter import ttk
from log_data import get_recent_patients

class VerlaufFenster:
    def __init__(self, master):
        self.master = master
        master.title("LeprendiX - Verlauf")
        master.geometry("300x400")
        master.resizable(False, False)

        self.style = ttk.Style()
        self.style.configure('TLabel', font=('Helvetica', 12, 'bold'))
        self.style.configure('TListbox', font=('Helvetica', 10))

        # Titel
        self.title_label = ttk.Label(master, text="Zuletzt Bearbeitete Patienten")
        self.title_label.pack(pady=10)

        # Listbox für den Verlauf
        self.listbox = tk.Listbox(master, width=40, height=15, selectmode=tk.SINGLE, font=('Helvetica', 10))
        self.listbox.pack(padx=10, pady=5)
        
        # Scrollbar hinzufügen
        scrollbar = ttk.Scrollbar(master, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.place(relx=0.9, rely=0.18, relheight=0.67, anchor=tk.NW)


        self.load_verlauf()
        self.update_loop()

    def load_verlauf(self):
        """Lädt die Patientennamen aus der Log-Datei und füllt die Listbox."""
        
        self.listbox.delete(0, tk.END) # Alte Einträge löschen

        recent_patients = get_recent_patients()

        if recent_patients:
            for i, name in enumerate(recent_patients, 1):
                self.listbox.insert(tk.END, f"{i}. {name}")
        else:
            self.listbox.insert(tk.END, "Keine Verlaufseinträge gefunden.")
    

    def update_loop(self):
        self.load_verlauf()
        self.master.after(2000, self.update_loop)  # alle 2 Sekunden



def start_verlauf_fenster():
    """Erstellt und startet das Tkinter-Fenster für den Verlauf."""
    root = tk.Toplevel()
    app = VerlaufFenster(root)
    # Wenn Sie möchten, dass der Benutzer das Hauptprogramm nicht schließen kann, solange der Verlauf offen ist:
    # root.wait_window() 
    # Allerdings ist die parallele Ausführung hier gängiger, daher lassen wir wait_window() weg.
    # root.mainloop() # Mainloop wird in main.py vom Hauptfenster übernommen

if __name__ == "__main__":
    # Testen Sie die Datei separat
    root = tk.Tk()
    root.withdraw() # Das Hauptfenster verstecken, da wir nur das Toplevel-Fenster sehen wollen
    toplevel = tk.Toplevel(root)
    app = VerlaufFenster(toplevel)
    root.mainloop()
    
