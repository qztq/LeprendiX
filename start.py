import tkinter as tk
import time
import math
import requests
import webbrowser
import os
import subprocess
import sys
import main

# --- KONFIGURATION ---
GITHUB_USER = "qztq"
REPO_NAME = "LeprendiX"
GITHUB_TOKEN = "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" # BITTE NEUEN TOKEN ERSTELLEN (SICHERHEIT!)
RELEASE_PAGE = f"https://github.com/{GITHUB_USER}/{REPO_NAME}/releases"
API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/tags"


def get_resource_path(relative_path):
    """ Ermittelt den Pfad zur Datei, egal ob Skript oder EXE """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller temporärer Ordner
        return os.path.join(sys._MEIPASS, relative_path)
    # Normaler Ordner (Entwicklung)
    return os.path.join(os.path.abspath("."), relative_path)

class CustomMsgBox(tk.Toplevel):
    """Eigene Neon-Style Yes/No Box."""
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.result = False
        self.overrideredirect(True)
        self.configure(bg='#1a1a1a', highlightbackground="#00f2ff", highlightthickness=2)
        w, h = 400, 200
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{int(sw/2-w/2)}+{int(sh/2-h/2)}")
        self.transient(parent)
        self.grab_set()
        tk.Label(self, text=title, font=("Segoe UI", 14, "bold"), fg="#00f2ff", bg='#1a1a1a', pady=10).pack()
        tk.Label(self, text=message, font=("Segoe UI", 11), fg="white", bg='#1a1a1a', wraplength=350, pady=20).pack()
        btn_frame = tk.Frame(self, bg='#1a1a1a')
        btn_frame.pack(side="bottom", pady=20)
        tk.Button(btn_frame, text=" JA ", font=("Segoe UI", 10, "bold"), bg="#00f2ff", fg="black",
                  relief="flat", width=12, command=self.yes).pack(side="left", padx=10)
        tk.Button(btn_frame, text=" NEIN ", font=("Segoe UI", 10, "bold"), bg="#333333", fg="white",
                  relief="flat", width=12, command=self.no).pack(side="left", padx=10)

    def yes(self): self.result = True; self.destroy()
    def no(self): self.result = False; self.destroy()

class NeonTraceSplash:
    def __init__(self):
        self.root = tk.Tk()
        self.running = True
        self.root.overrideredirect(True)
        self.root.configure(bg='#0a0a0a')

        w, h = 550, 400 
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{int(sw/2-w/2)}+{int(sh/2-h/2)}")

        self.canvas = tk.Canvas(self.root, width=w, height=h, bg='#0a0a0a', highlightthickness=0)
        self.canvas.pack()

        # UI Elemente
        self.canvas.create_text(w/2 - 30, h/2 - 20, text="Leprendi", font=("Segoe UI", 45, "bold"), fill="#f8f9fa")
        self.wait_text = self.canvas.create_text(w/2, h - 40, text="Ladevorgang...", font=("Segoe UI", 12, "italic"), fill="#555555")

        cx, cy = w/2 + 130, h/2 - 20
        s = 35  

        self.canvas.create_line(cx-s, cy-s, cx+s, cy+s, fill="#1a1a1a", width=15, capstyle="round")
        self.canvas.create_line(cx+s, cy-s, cx-s, cy+s, fill="#1a1a1a", width=15, capstyle="round")

        self.points = [(cx-s, cy-s), (cx+s, cy+s), (cx+s, cy-s), (cx-s, cy+s)]
        self.dot = self.canvas.create_oval(0,0,0,0, fill="#00f2ff", outline="#70f3ff", width=2)
        
        self.trail_length = 12 
        self.trail_dots = [self.canvas.create_oval(0,0,0,0, fill="#004d4d", outline="") for _ in range(self.trail_length)]
        self.history = []

        self.update_checked = False
        self.final_action_done = False # Neu: Merker für die letzte Sekunde
        self.start_time = time.time()
        self.animate()
        self.root.mainloop()
        

    

    def get_local_version(self):
        try:
            with open("version.txt", "r") as f:
                v = f.read().strip()
                print(f"[DEBUG] Lokale Version: {v}")
                return v
        except:
            return "0.0.0"

    def check_for_updates(self):
        print("\n--- UPDATE CHECK ---")
        local_v = self.get_local_version()
        try:
            headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
            response = requests.get(API_URL, headers=headers, timeout=5)
            if response.status_code == 200:
                tags = response.json()
                if tags:
                    latest_tag = tags[0]['name'].replace('v', '')
                    clean_local = local_v.replace('v', '')
                    
                    def to_tup(v): return tuple(map(int, v.split('.')))
                    
                    print(f"[DEBUG] Vergleich: GitHub({latest_tag}) vs Lokal({clean_local})")
                    if to_tup(latest_tag) > to_tup(clean_local):
                        print("[DEBUG] Update verfügbar!")
                        self.root.attributes('-topmost', False)
                        msg = CustomMsgBox(self.root, "Update verfügbar", f"Neu: {latest_tag}\nLokal: {local_v}\nJetzt updaten?")
                        self.root.wait_window(msg)
                        if msg.result: webbrowser.open(RELEASE_PAGE)
                    else:
                        print("[DEBUG] Kein Update nötig (Lokal >= GitHub).")
        except Exception as e:
            print(f"[DEBUG] Fehler beim Update-Check: {e}")
        print("--- CHECK BEENDET ---\n")

    def final_action(self):
        """Wird 1 Sekunde vor dem Ende ausgeführt."""
        print("[DEBUG] Bereite Start vor...")
        self.running = False  # Animation stoppen
        
        # Wir speichern uns die Referenz auf das Root-Objekt
        root_ref = self.root
        
        try:
            # 1. Das Splash-Fenster komplett zerstören
            # .destroy() beendet die mainloop von start.py
            root_ref.destroy()
            print("[DEBUG] Splash-Screen geschlossen.")

            # 2. JETZT erst main importieren und starten
            # Da root_ref.destroy() die aktuelle mainloop beendet,
            # rufen wir die neue mainloop von main.py direkt danach auf.
            import main
            print("[DEBUG] Starte Hauptprogramm...")
            main.create_main()
            
        except Exception as e:
            print(f"[DEBUG] Fehler beim Übergang: {e}")

    def animate(self):
        if not self.running or not self.canvas.winfo_exists():
            return
        
        try:
            elapsed = time.time() - self.start_time

            # 1. Update Check nach 3 Sekunden
            if not self.update_checked and elapsed > 3.0:
                self.update_checked = True
                self.canvas.itemconfig(self.wait_text, text="Prüfe auf Updates...")
                self.check_for_updates()
                self.canvas.itemconfig(self.wait_text, text="Bitte warten...")

            # 2. Finale Aktion genau 1 Sekunde vor dem Ende (bei 8.5s)
            if not self.final_action_done and elapsed > 8.5:
                self.final_action_done = True
                self.final_action()
                return

            # 3. Programm beenden nach 9.5s
            if elapsed > 9.5: 
                print("[DEBUG] Splash beendet.")
                self.root.destroy()
                return

            # Animation (Langsam)
            speed = (math.sin(elapsed * 0.7) + 1.1) * 0.5
            t = (elapsed * speed) % 2.0
            p1, p2 = (self.points[0], self.points[1]) if t < 1.0 else (self.points[2], self.points[3])
            pos_t = t if t < 1.0 else t - 1.0

            cur_x = p1[0] + (p2[0] - p1[0]) * pos_t
            cur_y = p1[1] + (p2[1] - p1[1]) * pos_t

            self.history.insert(0, (cur_x, cur_y))
            if len(self.history) > self.trail_length + 1: self.history.pop()

            for i, dot_id in enumerate(self.trail_dots):
                if i < len(self.history):
                    hx, hy = self.history[i]
                    r = (self.trail_length - i) * 0.6 
                    self.canvas.coords(dot_id, hx-r, hy-r, hx+r, hy+r)

            r_main = 5 + math.sin(elapsed * 5) * 1.2
            self.canvas.coords(self.dot, cur_x-r_main, cur_y-r_main, cur_x+r_main, cur_y+r_main)

            if self.running and self.root.winfo_exists():
                self.root.after(30, self.animate)
        
        except (tk.TclError, AttributeError):
            # Falls während der Berechnung das Fenster geschlossen wurde
            self.running = False

if __name__ == "__main__":
    NeonTraceSplash()