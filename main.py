import subprocess
import sys
import os
import threading
import runpy
import pickle
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageTk
import json
import datetime

def get_base_path():
    """ Ermittelt den Pfad zum Ordner, in dem die EXE oder das Skript liegt """
    if getattr(sys, 'frozen', False):
        # Pfad der EXE im "One Directory" Modus
        return os.path.dirname(sys.executable)
    else:
        # Pfad im Editor
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
os.chdir(BASE_DIR)

def resource_path(relative_path):
    """ Hilfsfunktion für interne Ressourcen (wie Logos im _MEIPASS) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = BASE_DIR
    return os.path.join(base_path, relative_path)


from config_loader import CONFIG
import gui_generator
import patient_status_checker

# --- KONFIGURATION & DESIGN ---
COLOR_PRIMARY = "#2c3e50"
COLOR_SECONDARY = "#34495e"
COLOR_ACCENT = "#27ae60"
COLOR_TEXT = "#ecf0f1"
COLOR_HIGHLIGHT = "#3498db"
LOGO_PATH = resource_path("logo.png")

# --- CREDENTIALS LADEN ---
def load_credentials():
    cred_path = os.path.join(BASE_DIR, "credentials.dat")
    if os.path.exists(cred_path):
        try:
            with open(cred_path, "rb") as f:
                return pickle.load(f)
        except:
            return None
    return None

USER_CREDS = load_credentials()


def show_loading_screen(root):
    loading_win = tk.Toplevel(root)
    loading_win.title("Lade LeprendiX...")
    loading_win.geometry("450x220")
    loading_win.configure(bg=COLOR_SECONDARY)
    loading_win.overrideredirect(True)
    loading_win.attributes("-topmost", True)
    
    root.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() // 2) - 225
    y = root.winfo_y() + (root.winfo_height() // 2) - 110
    loading_win.geometry(f"+{int(x)}+{int(y)}")

    tk.Label(loading_win, text="LeprendiX", font=("Segoe UI", 24, "bold"), 
             fg=COLOR_ACCENT, bg=COLOR_SECONDARY).pack(pady=(40, 5))
    
    progress = ttk.Progressbar(loading_win, mode="indeterminate", length=350)
    progress.pack(pady=30)
    progress.start(15) 
    loading_win.lift()
    return loading_win

# In main.py
def launch_application(root):
    splash = show_loading_screen(root)
    root.withdraw() 
    
    def finalize_start():
        # 1. Splash zerstören
        if splash.winfo_exists():
            splash.destroy()
        
        # Hauptanwendung (Generator) starten
        gen_root = tk.Tk()
        app_gen = gui_generator.HonorarGeneratorApp(gen_root)
        
       
        gen_root.mainloop()
        
        
        
        # Sobald das Hauptfenster geschlossen wird, beenden wir auch den unsichtbaren root
        root.destroy()

    # Wir warten 2 Sekunden mit dem Splash und rufen dann finalize_start im Main-Thread auf
    root.after(2000, finalize_start)
    root.mainloop()

# --- HAUPTFENSTER ---
def create_main():
    root = tk.Tk()
    root.title("LeprendiX - Control Center")
    root.geometry("1150x850")
    root.configure(bg=COLOR_PRIMARY)

    # Styles
    style = ttk.Style()
    style.theme_use('default')
    style.configure("TNotebook", background=COLOR_PRIMARY, borderwidth=0)
    style.configure("TNotebook.Tab", background=COLOR_SECONDARY, foreground=COLOR_TEXT, 
                    padding=[25, 10], font=("Segoe UI", 10, "bold"))
    style.map("TNotebook.Tab", background=[("selected", COLOR_PRIMARY)], foreground=[("selected", COLOR_ACCENT)])

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=20, pady=20)

    # --- TAB 1: ÜBERSICHT ---
    t1 = tk.Frame(nb, bg=COLOR_PRIMARY)
    nb.add(t1, text="  ÜBERSICHT  ")

    if os.path.exists(LOGO_PATH):
        # 1. Bild öffnen
        img = Image.open(LOGO_PATH)
        
        # 2. Proportionale Skalierung berechnen (z.B. maximale Breite 500px)
        max_width = 500
        w_percent = (max_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        
        # 3. Resize mit berechneten Werten (Beibehaltung des Seitenverhältnisses)
        img = img.resize((max_width, h_size), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        
        # 4. Label zentrieren
        # Durch pack(expand=True) wird das Label im verfügbaren Raum zentriert
        logo_label = tk.Label(t1, image=img_tk, bg=COLOR_PRIMARY)
        logo_label.image = img_tk  # Referenz behalten (Garbage Collection Schutz)
        logo_label.pack(pady=40, expand=False) # expand=False, falls es oben kleben soll, True für echte Mitte

    # Login Bereich
    login_f = tk.Frame(t1, bg=COLOR_SECONDARY, padx=40, pady=30, highlightbackground=COLOR_ACCENT, highlightthickness=1)
    login_f.pack(pady=10)

    tk.Label(login_f, text="SYSTEM-LOGIN", font=("Segoe UI", 14, "bold"), fg=COLOR_ACCENT, bg=COLOR_SECONDARY).pack(pady=(0, 20))
    
    tk.Label(login_f, text="Benutzername:", fg=COLOR_TEXT, bg=COLOR_SECONDARY).pack(anchor="w")
    u_ent = tk.Entry(login_f, width=30, bg=COLOR_PRIMARY, fg="white", relief="flat", insertbackground="white")
    u_ent.pack(pady=(5, 15), ipady=5)
    u_ent.insert(0, "bhag")

    tk.Label(login_f, text="Passwort:", fg=COLOR_TEXT, bg=COLOR_SECONDARY).pack(anchor="w")
    p_ent = tk.Entry(login_f, show="*", width=30, bg=COLOR_PRIMARY, fg="white", relief="flat", insertbackground="white")
    p_ent.pack(pady=(5, 20), ipady=5)

    def do_login(event=None):
        if not USER_CREDS:
            messagebox.showerror("Fehler", "Datei 'credentials.dat' fehlt!")
            return
        if u_ent.get() == USER_CREDS.get("user") and p_ent.get() == USER_CREDS.get("password"):
            launch_application(root)
        else:
            messagebox.showerror("Fehler", "Logindaten inkorrekt.")

    tk.Button(login_f, text="ANMELDEN & STARTEN", bg=COLOR_ACCENT, fg="white", font=("Segoe UI", 11, "bold"),
              relief="flat", cursor="hand2", padx=20, pady=10, command=do_login).pack(fill="x")
    root.bind('<Return>', do_login)




    # --- TAB 2: DATENBANK & EINSTELLUNGEN ---
    t2 = tk.Frame(nb, bg=COLOR_PRIMARY)
    nb.add(t2, text="   EINSTELLUNGEN   ")

    # Ein zentrierter Container-Frame
    db_container = tk.Frame(t2, bg=COLOR_PRIMARY)
    db_container.pack(expand=True, fill="both", padx=20)

    # --- Teil 1: Datenbank-Initialisierung ---
    tk.Label(db_container, text="Datenbank-Initialisierung", 
            font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT, bg=COLOR_PRIMARY).pack(pady=(20, 10))

    db_p_ent = tk.Entry(db_container, show="*", width=30, bg=COLOR_SECONDARY, 
                        fg="white", font=("Arial", 12), justify="center", relief="flat")
    db_p_ent.pack(pady=5, ipady=5)

    def do_setup():
        if USER_CREDS and db_p_ent.get() == USER_CREDS.get("password"):
            try:
                setup_script = resource_path("db_setup.py")
                runpy.run_path(setup_script, run_name="__main__")
                messagebox.showinfo("Erfolg", "Datenbank bereit.")
            except Exception as e: 
                messagebox.showerror("Fehler", f"Setup fehlgeschlagen:\n{e}")
        else: 
            messagebox.showerror("Fehler", "Passwort falsch.")
            
    tk.Button(db_container, text="Datenbank Setup", bg="#e67e22", fg="white", 
            font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=8, 
            command=do_setup).pack(pady=10)

    # Trennlinie
    tk.Frame(db_container, height=2, bg=COLOR_SECONDARY, bd=0).pack(fill="x", pady=20)

    # --- Teil 2: Pfad-Einstellungen (JSON) ---
    tk.Label(db_container, text="Pfad-Konfiguration", 
            font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT, bg=COLOR_PRIMARY).pack(pady=10)

    # Frames für die Pfadanzeige
    def create_path_row(label_text, config_key):
        row = tk.Frame(db_container, bg=COLOR_PRIMARY)
        row.pack(fill="x", pady=5)
        
        tk.Label(row, text=label_text, fg=COLOR_TEXT, bg=COLOR_PRIMARY, font=("Segoe UI", 10, "bold"), width=15, anchor="w").pack(side="left")
        
        # Label zur Anzeige des aktuellen Pfads
        path_var = tk.StringVar(value=CONFIG.get(config_key, "Nicht gesetzt"))
        lbl = tk.Label(row, textvariable=path_var, fg="#bdc3c7", bg=COLOR_SECONDARY, font=("Consolas", 9), anchor="w", padx=10)
        lbl.pack(side="left", fill="x", expand=True, padx=10, ipady=3)
        
        def change_path():
            new_path = filedialog.askdirectory(initialdir=path_var.get())
            if new_path:
                new_path = new_path.replace("/", "\\") # Windows-Format
                # 1. Variable im Programm aktualisieren
                CONFIG[config_key] = new_path
                path_var.set(new_path)
                # 2. In JSON speichern
                try:
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(CONFIG, f, indent=4)
                    messagebox.showinfo("Gespeichert", f"{label_text} wurde aktualisiert.")
                except Exception as e:
                    messagebox.showerror("Fehler", f"Speichern fehlgeschlagen: {e}")

        tk.Button(row, text="Ändern", bg=COLOR_SECONDARY, fg="white", font=("Segoe UI", 8), 
                relief="flat", command=change_path, padx=10).pack(side="right")

    # Erzeuge die Zeilen für die beiden Hauptpfade
    create_path_row("Patienten-Ordner:", "PATIENT_BASE_DIR")
    create_path_row("Archiv-Ordner:", "ARCHIVE_DIR")

    # --- TAB 3: DOKUMENTATION ---
    t3 = tk.Frame(nb, bg=COLOR_PRIMARY)
    nb.add(t3, text="  DOKUMENTATION  ")

    # --- Sidebar für Navigation & Suche ---
    sidebar = tk.Frame(t3, bg=COLOR_SECONDARY, width=300)
    sidebar.pack(side="left", fill="y", padx=(10, 0), pady=10)
    sidebar.pack_propagate(False)

    # Sucheingabe
    tk.Label(sidebar, text="Suche:", bg=COLOR_SECONDARY, fg=COLOR_TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
    search_var = tk.StringVar()
    search_entry = tk.Entry(sidebar, textvariable=search_var, bg=COLOR_PRIMARY, fg="white", insertbackground="white", relief="flat")
    search_entry.pack(fill="x", padx=10, pady=(0, 10))

    # Liste der Kapitel
    tk.Label(sidebar, text="Inhalt:", bg=COLOR_SECONDARY, fg=COLOR_TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(5, 5))
    
    # Listbox mit Scrollbar
    list_frame = tk.Frame(sidebar, bg=COLOR_SECONDARY)
    list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    nav_scroll = tk.Scrollbar(list_frame)
    nav_scroll.pack(side="right", fill="y")
    
    nav_list = tk.Listbox(list_frame, bg=COLOR_PRIMARY, fg=COLOR_TEXT, selectbackground=COLOR_ACCENT, 
                          selectforeground="white", relief="flat", yscrollcommand=nav_scroll.set, font=("Segoe UI", 10))
    nav_list.pack(side="left", fill="both", expand=True)
    nav_scroll.config(command=nav_list.yview)

    # --- Content Bereich ---
    content_f = tk.Frame(t3, bg=COLOR_PRIMARY)
    content_f.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    scroll = tk.Scrollbar(content_f)
    scroll.pack(side="right", fill="y")

    doc_t = tk.Text(content_f, wrap="word", padx=30, pady=30, font=("Segoe UI", 11), 
                    bg=COLOR_SECONDARY, fg=COLOR_TEXT, relief="flat", yscrollcommand=scroll.set)
    doc_t.pack(fill="both", expand=True)
    scroll.config(command=doc_t.yview)

    # --- Dokumentations-Inhalt ---
    sections = [
        ("1. Einleitung", "SEC_1", "Willkommen bei LeprendiX.\nDiese Software dient zur Verwaltung von Patienten und zur Erstellung von Honorarnoten.\n\n"),
        ("2. Installation & Setup", "SEC_2", "Vor der ersten Nutzung muss die Datenbank initialisiert werden.\nGehen Sie dazu in den Tab 'Einstellungen' und nutzen Sie das Datenbank-Passwort.\n\n"),
        ("3. Patientenverwaltung", "SEC_3", "Im Tab 'Patienten Verwalten' können Sie neue Patienten anlegen, bearbeiten oder löschen.\nNutzen Sie die Suche, um bestehende Datensätze zu laden.\n\n"),
        ("4. Honorarnoten", "SEC_4", "Im Tab 'Honorarnote Generieren' wählen Sie einen Patienten aus und erstellen das Dokument.\nEs wird automatisch eine Word-Datei erzeugt und (optional) gedruckt.\n\n"),
        ("5. Leistungen & Teamup", "SEC_5", "Leistungen können manuell oder via Teamup-Kalender importiert werden.\nStellen Sie sicher, dass der API-Key in der Konfiguration hinterlegt ist.\n\n"),
        ("6. Archivierung", "SEC_6", "Über den 'Status-Checker' können abgerechnete Patienten ins Archiv verschoben werden.\nDies hält die aktive Datenbank sauber.\n\n"),
        ("7. Einstellungen", "SEC_7", "Hier können Pfade für Speicherorte und Backups angepasst werden.\n\n"),
        ("8. Troubleshooting", "SEC_8", "Bei Fehlern prüfen Sie bitte die Log-Dateien oder kontaktieren Sie den Support.\n\n")
    ]

    title_to_tag = {}

    for title, tag, content in sections:
        doc_t.insert(tk.END, title + "\n", ("heading", tag))
        doc_t.insert(tk.END, content, ("content",))
        title_to_tag[title] = tag
        nav_list.insert(tk.END, title)

    doc_t.tag_configure("heading", font=("Segoe UI", 14, "bold"), foreground=COLOR_ACCENT, spacing3=10)
    doc_t.tag_configure("content", spacing1=5, spacing3=15)
    doc_t.config(state="disabled")

    def on_nav_select(event):
        selection = nav_list.curselection()
        if selection:
            title = nav_list.get(selection[0])
            tag = title_to_tag.get(title)
            if tag:
                doc_t.see(f"{tag}.first")

    nav_list.bind('<<ListboxSelect>>', on_nav_select)

    def filter_list(*args):
        search_term = search_var.get().lower()
        nav_list.delete(0, tk.END)
        for title, _, _ in sections:
            if search_term in title.lower():
                nav_list.insert(tk.END, title)

    search_var.trace("w", filter_list)

    root.mainloop()

if __name__ == "__main__":
    create_main()