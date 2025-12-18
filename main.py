import subprocess
import sys
import os
import threading
import runpy
import pickle
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk

# --- KONFIGURATION & DESIGN ---
COLOR_PRIMARY = "#2c3e50"
COLOR_SECONDARY = "#34495e"
COLOR_ACCENT = "#27ae60"
COLOR_TEXT = "#ecf0f1"
COLOR_HIGHLIGHT = "#3498db"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

LOGO_PATH = resource_path("logo.png")

# --- CREDENTIALS LADEN ---
def load_credentials():
    cred_path = resource_path("credentials.dat")
    if os.path.exists(cred_path):
        try:
            with open(cred_path, "rb") as f:
                return pickle.load(f)
        except:
            return None
    return None

USER_CREDS = load_credentials()

# --- HELFER-FUNKTIONEN ---
def scroll_to_section(text_widget, section_tag):
    """Scrollt den Dokumentationstext zur gewählten Sektion."""
    idx = text_widget.search(section_tag, "1.0", tk.END)
    if idx:
        text_widget.see(idx)
        text_widget.tag_add("highlight", idx, f"{idx} lineend")
        text_widget.after(500, lambda: text_widget.tag_remove("highlight", "1.0", tk.END))

# --- LADEBILDSCHIRM (SPLASH) ---
# --- LADEBILDSCHIRM (SPLASH) VERBESSERT ---
def show_loading_screen(root):
    loading_win = tk.Toplevel(root)
    loading_win.title("Lade LeprendiX...")
    loading_win.geometry("450x220")
    loading_win.configure(bg=COLOR_SECONDARY)
    loading_win.overrideredirect(True)
    
    # Zwingt das Fenster in den Vordergrund
    loading_win.attributes("-topmost", True)
    
    # Zentrierung
    root.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() // 2) - 225
    y = root.winfo_y() + (root.winfo_height() // 2) - 110
    loading_win.geometry(f"+{int(x)}+{int(y)}")

    tk.Label(loading_win, text="LeprendiX", font=("Segoe UI", 24, "bold"), 
             fg=COLOR_ACCENT, bg=COLOR_SECONDARY).pack(pady=(40, 5))
    tk.Label(loading_win, text="System wird gestartet...", 
             font=("Segoe UI", 10), fg=COLOR_TEXT, bg=COLOR_SECONDARY).pack()

    progress = ttk.Progressbar(loading_win, mode="indeterminate", length=350)
    progress.pack(pady=30)
    progress.start(15) 
    
    # Wichtig: Fenster heben und Zeichnen erzwingen
    loading_win.lift()
    loading_win.update()
    
    return loading_win

def launch_application(root):
    # 1. Splash Screen erstellen
    splash = show_loading_screen(root)
    root.withdraw() 
    
    def run_tasks():
        try:
            gui_script = resource_path("gui_generator.py")
            checker_script = resource_path("patient_status_checker.py")
            
            # Hintergrund-Checker starten
            threading.Thread(target=lambda: runpy.run_path(checker_script, run_name="__main__"), daemon=True).start()
            
            # Timer zum Schließen des Splash-Screens im Haupt-Thread registrieren
            # Wir nutzen root.after, damit das Zerstören sicher im GUI-Thread passiert
            root.after(3000, lambda: splash.destroy() if splash.winfo_exists() else None)
            
            # Hauptanwendung starten (Dies blockiert diesen Thread)
            runpy.run_path(gui_script, run_name="__main__")
            
            # Sobald die GUI-Anwendung geschlossen wird, das Control Center beenden
            root.destroy()
            
        except Exception as e:
            # Im Fehlerfall Splash weg und Login wieder her
            root.after(0, lambda: splash.destroy() if splash.winfo_exists() else None)
            messagebox.showerror("Fehler", f"Start fehlgeschlagen:\n{e}")
            root.deiconify()

    # Den Lade-Thread starten
    threading.Thread(target=run_tasks, daemon=True).start()

# --- PROGRAMMSTART LOGIK ---
def launch_application(root):
    # 1. Splash Screen erstellen (mit Topmost-Fix)
    splash = tk.Toplevel(root)
    splash.title("Lade LeprendiX...")
    splash.geometry("450x220")
    splash.configure(bg=COLOR_SECONDARY)
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)
    
    # Zentrieren
    root.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() // 2) - 225
    y = root.winfo_y() + (root.winfo_height() // 2) - 110
    splash.geometry(f"+{int(x)}+{int(y)}")

    tk.Label(splash, text="LeprendiX", font=("Segoe UI", 24, "bold"), fg=COLOR_ACCENT, bg=COLOR_SECONDARY).pack(pady=(40, 5))
    progress = ttk.Progressbar(splash, mode="indeterminate", length=350)
    progress.pack(pady=30)
    progress.start(15)

    # 2. DAS IST DER ENTSCHEIDENDE TEIL:
    # Wir sagen dem Hauptfenster JETZT, dass es in 3 Sekunden den Splash löschen soll.
    # Dieser Befehl wartet nicht auf den Thread!
    root.after(3000, lambda: splash.destroy() if splash.winfo_exists() else None)

    # 3. Haupt-Control-Center ausblenden
    root.withdraw() 
    
    def run_tasks():
        try:
            gui_script = resource_path("gui_generator.py")
            checker_script = resource_path("patient_status_checker.py")
            
            # Hintergrund-Checker
            threading.Thread(target=lambda: runpy.run_path(checker_script, run_name="__main__"), daemon=True).start()
            
            # Startet die GUI (blockiert diesen Thread)
            runpy.run_path(gui_script, run_name="__main__")
            
            # Beendet das Control Center endgültig beim Schließen der GUI
            root.quit() 
        except Exception as e:
            root.after(0, lambda: splash.destroy() if splash.winfo_exists() else None)
            messagebox.showerror("Fehler", f"Start fehlgeschlagen:\n{e}")
            root.deiconify()

    # Threading starten
    threading.Thread(target=run_tasks, daemon=True).start()

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
        img = Image.open(LOGO_PATH).resize((350, 150), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        tk.Label(t1, image=img_tk, bg=COLOR_PRIMARY).pack(pady=20)

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

    # --- TAB 2: DATENBANK ---
    t2 = tk.Frame(nb, bg=COLOR_PRIMARY)
    nb.add(t2, text="  DATENBANK  ")
    
    # Ein zentrierter Container-Frame mit pack statt place
    db_container = tk.Frame(t2, bg=COLOR_PRIMARY)
    db_container.pack(expand=True) # Zentriert den Inhalt vertikal und horizontal
    
    tk.Label(db_container, text="Datenbank-Initialisierung", 
             font=("Segoe UI", 18, "bold"), fg=COLOR_TEXT, bg=COLOR_PRIMARY).pack(pady=20)
    
    db_p_ent = tk.Entry(db_container, show="*", width=30, bg=COLOR_SECONDARY, 
                        fg="white", font=("Arial", 14), justify="center", relief="flat")
    db_p_ent.pack(pady=10, ipady=8)
    
    def do_setup():
        if USER_CREDS and db_p_ent.get() == USER_CREDS.get("password"):
            try:
                # Nutze runpy statt subprocess für die EXE-Kompatibilität
                setup_script = resource_path("db_setup.py")
                runpy.run_path(setup_script, run_name="__main__")
                messagebox.showinfo("Erfolg", "Datenbank bereit.")
            except Exception as e: 
                messagebox.showerror("Fehler", f"Setup fehlgeschlagen:\n{e}")
        else: 
            messagebox.showerror("Fehler", "Passwort falsch.")
            
    tk.Button(db_container, text="Setup ausführen", bg="#e67e22", fg="white", 
              font=("Segoe UI", 11, "bold"), relief="flat", padx=30, pady=12, 
              command=do_setup).pack(pady=20)

    # --- TAB 3: DOKUMENTATION ---
    t3 = tk.Frame(nb, bg=COLOR_PRIMARY)
    nb.add(t3, text="  DOKUMENTATION  ")

    sidebar = tk.Frame(t3, bg=COLOR_SECONDARY, width=250)
    sidebar.pack(side="left", fill="y", padx=(10, 0), pady=10)
    sidebar.pack_propagate(False)

    content_f = tk.Frame(t3, bg=COLOR_PRIMARY)
    content_f.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    scroll = tk.Scrollbar(content_f)
    scroll.pack(side="right", fill="y")

    doc_t = tk.Text(content_f, wrap="word", padx=30, pady=30, font=("Segoe UI", 11), 
                    bg=COLOR_SECONDARY, fg=COLOR_TEXT, relief="flat", yscrollcommand=scroll.set)
    doc_t.pack(fill="both", expand=True)
    scroll.config(command=doc_t.yview)

    sections = [
        ("🛠️ 1. Einleitung", "SEC_INTRO", "Systemdokumentation für LeprendiX...\n\n"),
        ("⚙️ 2. Installation", "SEC_INST", "Initialisieren Sie zuerst die Datenbank...\n\n"),
        ("👤 3. Patienten", "SEC_PAT", "Verwaltung über das Hauptfenster...\n\n")
    ]

    for title, tag, content in sections:
        btn = tk.Button(sidebar, text=title, font=("Segoe UI", 10), bg=COLOR_SECONDARY, fg=COLOR_TEXT,
                        relief="flat", anchor="w", cursor="hand2", activebackground=COLOR_PRIMARY,
                        command=lambda t=tag: scroll_to_section(doc_t, t))
        btn.pack(fill="x", padx=10, pady=2)
        doc_t.insert(tk.END, title + "\n", tag)
        doc_t.insert(tk.END, content)

    doc_t.tag_configure("highlight", background=COLOR_HIGHLIGHT, foreground="white")
    doc_t.config(state="disabled")

    root.mainloop()

if __name__ == "__main__":
    create_main()