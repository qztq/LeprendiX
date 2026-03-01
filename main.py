import subprocess
import sys
import os
import threading
import runpy
import pickle
import tkinter as tk
import sqlite3
from tkinter import messagebox, ttk, filedialog
import requests
from PIL import Image, ImageTk
import json
import datetime
import webbrowser
import time
import math
import shutil
import logging
import tempfile
import traceback # Für Crash-Handling

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
import crash_handler
import setup_wizard

# --- LOGGING SETUP ---
def setup_logging():
    # Use a user-writable directory for logs to avoid PermissionError
    app_name = "LeprendiX"
    if sys.platform == "win32":
        base_path = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
    else:
        base_path = os.path.join(os.path.expanduser("~"), ".local", "share")
    
    log_dir = os.path.join(base_path, app_name, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "leprendix.log")
    except Exception:
        log_file = os.path.join(tempfile.gettempdir(), "leprendix.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"=== LeprendiX gestartet (Log: {log_file}) ===")

# --- WATCHDOG KLASSE (FREEZE DETECTION) ---
class AppWatchdog:
    """
    Überwacht den Haupt-Thread. Wenn dieser für 'timeout_sec' Sekunden blockiert,
    wird der Crash-Handler ausgelöst.
    """
    def __init__(self, root, check_interval_ms=1000, timeout_sec=20):
        self.root = root
        self.check_interval_ms = check_interval_ms
        self.timeout_sec = timeout_sec
        self.last_heartbeat = time.time()
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)

    def start(self):
        self.monitor_thread.start()
        self._schedule_heartbeat()

    def stop(self):
        self.running = False

    def _schedule_heartbeat(self):
        if not self.running:
            return
        # Heartbeat aktualisieren (dies läuft im Main-Thread)
        self.last_heartbeat = time.time()
        try:
            self.root.after(self.check_interval_ms, self._schedule_heartbeat)
        except Exception:
            pass # Falls root zerstört wurde

    def _monitor_loop(self):
        while self.running:
            time.sleep(1)
            # Prüfen, ob der letzte Heartbeat zu lange her ist
            if time.time() - self.last_heartbeat > self.timeout_sec:
                self._trigger_freeze_handling()
                break

    def _trigger_freeze_handling(self):
        logging.critical("WATCHDOG: Programm reagiert nicht mehr (Freeze detected).")
        
        # Crash-Log schreiben
        crash_file = crash_handler.CRASH_FILE
        try:
            with open(crash_file, "w", encoding="utf-8") as f:
                f.write("KRITISCHER FEHLER: PROGRAMM EINGEFROREN (FREEZE)\n")
                f.write("================================================\n")
                f.write("Der Watchdog hat festgestellt, dass die Benutzeroberfläche seit über 20 Sekunden nicht mehr reagiert.\n")
                f.write("Mögliche Ursachen: Endlosschleife, blockierende Netzwerkabfrage oder Deadlock.\n")
                f.write(f"Zeitstempel: {datetime.datetime.now()}\n")
        except Exception:
            pass

        # Crash Handler starten
        crash_handler.start_crash_handler_process()
        
        # Prozess hart beenden (os._exit killt sofort, sys.exit wirft nur Exception)
        os._exit(1)

# --- KONFIGURATION & DESIGN ---
COLOR_SIDEBAR = "#1e1f22"    # Dark sidebar background
COLOR_BG_MAIN = "#2b2d31"    # Main content area background
COLOR_PANEL = "#383a40"      # Background for cards, entries
COLOR_ACCENT = "#23a55a"     # Vibrant green for highlights
COLOR_SECONDARY = "#5865F2"  # Secondary action color
COLOR_TEXT = "#dbdee1"       # Primary text color
COLOR_TEXT_DIM = "#949ba4"   # Secondary/dimmed text
COLOR_DANGER = "#da373c"     # Red for danger/logout
LOGO_PATH = resource_path("logo.png")

# --- GITHUB CONFIG FOR RELEASE NOTES ---
GITHUB_USER = "qztq"
REPO_NAME = "LeprendiX"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/releases"
GITHUB_TOKEN = CONFIG.get("GITHUB_TOKEN", "")


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

def get_release_notes():
    """Fetches and formats the latest release notes from GitHub."""
    notes_content = "Release-Informationen konnten nicht geladen werden.\n\n" \
                    "Bitte prüfen Sie Ihre Internetverbindung oder besuchen Sie die Releases-Seite manuell."
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        # Get latest 5 releases
        response = requests.get(RELEASES_API_URL, headers=headers, timeout=5, params={"per_page": 5})
        response.raise_for_status()
        releases = response.json()
        
        if not releases:
            return "Derzeit sind keine Release-Informationen auf GitHub verfügbar."

        formatted_notes = ""
        for release in releases:
            tag_name = release.get('tag_name', 'N/A')
            name = release.get('name', tag_name) # Fallback to tag_name if name is empty
            published_at_iso = release.get('published_at')
            body = release.get('body', 'Keine Beschreibung vorhanden.')

            # Format date
            if published_at_iso:
                # GitHub API returns ISO 8601 format (e.g., "2024-01-15T10:00:00Z")
                dt_utc = datetime.datetime.fromisoformat(published_at_iso.replace('Z', '+00:00'))
                published_at_str = dt_utc.strftime("%d.%m.%Y")
            else:
                published_at_str = "N/A"

            # Build the string for one release
            formatted_notes += f"Version: {name}\n"
            formatted_notes += f"Datum: {published_at_str}\n"
            formatted_notes += "--------------------------------------------------\n"
            
            clean_body = body.replace('\r\n', '\n').strip()
            formatted_notes += clean_body + "\n\n\n"
            
        return formatted_notes if formatted_notes else notes_content

    except requests.exceptions.RequestException as e:
        return f"{notes_content}\n\nFehlerdetails: {e}"
    except Exception as e:
        return f"{notes_content}\n\nFehlerdetails: {e}"

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=200, height=200, radius=25, bg=COLOR_ACCENT, fg="white", font=("Segoe UI", 12, "bold"), hover_bg=None):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0)
        self.command = command
        self.text = text
        self.radius = radius
        self.bg_color = bg
        self.fg_color = fg
        self.font = font
        self.hover_bg = hover_bg if hover_bg else self._adjust_color(bg)
        
        self.rect = None
        self.text_item = None
        
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
    def _draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 5: w = int(self["width"])
        if h < 5: h = int(self["height"])
        
        self.rect = self._create_rounded_rect(0, 0, w, h, self.radius, fill=self.bg_color, outline="")
        self.text_item = self.create_text(w/2, h/2, text=self.text, fill=self.fg_color, font=self.font)
        
        self.tag_bind(self.rect, "<Button-1>", self._on_click)
        self.tag_bind(self.text_item, "<Button-1>", self._on_click)
        self.tag_bind(self.rect, "<Enter>", self._on_enter)
        self.tag_bind(self.text_item, "<Enter>", self._on_enter)
        self.tag_bind(self.rect, "<Leave>", self._on_leave)
        self.tag_bind(self.text_item, "<Leave>", self._on_leave)

    def _create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = (x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1)
        return self.create_polygon(points, **kwargs, smooth=True)

    def _on_enter(self, event):
        if self.rect: self.itemconfig(self.rect, fill=self.hover_bg)
        
    def _on_leave(self, event):
        if self.rect: self.itemconfig(self.rect, fill=self.bg_color)
        
    def _on_click(self, event=None):
        if self.command: self.command()

    def _adjust_color(self, color):
        # Simple hover color adjustment (lighter)
        if color == COLOR_ACCENT: return "#2ecc71"
        if color == COLOR_DANGER: return "#e74c3c"
        if color == COLOR_SIDEBAR: return "#2b2d31"
        return "#555555"


class LoginSplash(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.running = True
        self.overrideredirect(True)
        self.configure(bg=COLOR_BG_MAIN)

        w, h = 550, 400 
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.attributes("-topmost", True)

        self.canvas = tk.Canvas(self, width=w, height=h, bg=COLOR_BG_MAIN, highlightthickness=0)
        self.canvas.pack()

        # UI Elemente from start.py
        self.canvas.create_text(w/2 - 30, h/2 - 20, text="Leprendi", font=("Segoe UI", 45, "bold"), fill=COLOR_TEXT)
        self.wait_text = self.canvas.create_text(w/2, h - 40, text="Anwendung wird gestartet...", font=("Segoe UI", 12, "italic"), fill=COLOR_TEXT_DIM)

        cx, cy = w/2 + 130, h/2 - 20
        s = 35  

        self.canvas.create_line(cx-s, cy-s, cx+s, cy+s, fill=COLOR_SIDEBAR, width=15, capstyle="round")
        self.canvas.create_line(cx+s, cy-s, cx-s, cy+s, fill=COLOR_SIDEBAR, width=15, capstyle="round")

        self.points = [(cx-s, cy-s), (cx+s, cy+s), (cx+s, cy-s), (cx-s, cy+s)]
        self.dot = self.canvas.create_oval(0,0,0,0, fill=COLOR_ACCENT, outline=COLOR_ACCENT, width=2)
        
        self.trail_length = 12 
        self.trail_dots = [self.canvas.create_oval(0,0,0,0, fill=COLOR_SIDEBAR, outline="") for _ in range(self.trail_length)]
        self.history = []
        
        self.start_time = time.time()
        self.animate()

    def animate(self):
        if not self.running or not self.winfo_exists():
            return
        
        try:
            elapsed = time.time() - self.start_time

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

            if self.running and self.winfo_exists():
                self.after(30, self.animate)
        
        except (tk.TclError, AttributeError):
            self.running = False

    def stop(self):
        self.running = False
        self.destroy()

def launch_gui_generator():
    """Startet das Hauptmodul für Rechnungen."""
    gen_root = tk.Toplevel()
    app_gen = gui_generator.HonorarGeneratorApp(gen_root)
    # Note: mainloop is handled by the main launcher root

    # Wir warten 2 Sekunden mit dem Splash und rufen dann finalize_start im Main-Thread auf

class CollapsiblePane(ttk.Frame):
    def __init__(self, parent, title="", expanded=False):
        super().__init__(parent)
        self.expanded = expanded
        self.title = title
        
        self.title_frame = tk.Frame(self, bg="#444444")
        self.title_frame.pack(fill="x", expand=True)
        
        self.toggle_btn = tk.Label(self.title_frame, text="▼" if expanded else "▶", bg="#444444", fg="white", width=3)
        self.toggle_btn.pack(side="left")
        
        self.lbl = tk.Label(self.title_frame, text=title, bg="#444444", fg="white", font=("Segoe UI", 10, "bold"))
        self.lbl.pack(side="left", fill="x", expand=True)
        
        self.sub_frame = tk.Frame(self, bg=COLOR_PANEL)
        
        self.title_frame.bind("<Button-1>", self.toggle)
        self.toggle_btn.bind("<Button-1>", self.toggle)
        self.lbl.bind("<Button-1>", self.toggle)
        
        if expanded:
            self.sub_frame.pack(fill="x", expand=True, padx=10, pady=5)

    def toggle(self, event=None):
        self.expanded = not self.expanded
        if self.expanded:
            self.sub_frame.pack(fill="x", expand=True, padx=10, pady=5)
            self.toggle_btn.config(text="▼")
        else:
            self.sub_frame.pack_forget()
            self.toggle_btn.config(text="▶")
    
    @property
    def frame(self):
        return self.sub_frame

STATUS_CHECKER_WIN = None
def launch_status_checker():
    """Startet den Status Checker als Toplevel."""
    global STATUS_CHECKER_WIN
    if STATUS_CHECKER_WIN and STATUS_CHECKER_WIN.winfo_exists():
        STATUS_CHECKER_WIN.lift()
        return
    checker_root = tk.Toplevel()
    app_checker = patient_status_checker.PatientStatusApp(checker_root)
    checker_root.app = app_checker
    STATUS_CHECKER_WIN = checker_root

def launch_material_orders():
    messagebox.showinfo("Info", "Materialbestellungen - Dieses Modul ist derzeit in Entwicklung.")

def launch_gui_generator(root_to_hide=None):
    """Startet das Hauptmodul für Rechnungen."""
    if root_to_hide:
        root_to_hide.withdraw()

    gen_root = tk.Toplevel()
    app_gen = gui_generator.HonorarGeneratorApp(gen_root)
    
    def on_gen_close():
        app_gen.on_closing()
        if root_to_hide:
            root_to_hide.destroy()
            
    gen_root.protocol("WM_DELETE_WINDOW", on_gen_close)


class MediaBar(tk.Canvas):
    def __init__(self, parent, items, width=800, height=220, bg=COLOR_BG_MAIN):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.items = items
        self.current_index = 0
        self.timer_id = None
        
        # Action Button (wird via create_window eingebettet)
        self.action_btn = RoundedButton(self, text="Mehr erfahren", width=160, height=45, bg=COLOR_ACCENT, font=("Segoe UI", 10, "bold"))
        
        self.bind("<Configure>", self._on_resize)
        self._cycle()

    def _on_resize(self, event):
        # Bei Resize neu zeichnen (aktuelles Item)
        if self.items:
            idx = self.current_index - 1 if self.current_index > 0 else len(self.items) - 1
            self._draw_item(self.items[idx])

    def _cycle(self):
        if not self.items: return
        item = self.items[self.current_index]
        self._draw_item(item)
        self.current_index = (self.current_index + 1) % len(self.items)
        self.timer_id = self.after(6000, self._cycle)

    def _draw_item(self, item):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10: w = int(self["width"])
        if h < 10: h = int(self["height"])
        
        # 1. Hintergrund (Farbe oder Bild)
        bg_color = item.get("color", "#2c3e50")
        image_path = item.get("image", None)
        
        self.create_rectangle(0, 0, w, h, fill=bg_color, outline="")
        
        if image_path and os.path.exists(image_path):
            try:
                pil_img = Image.open(image_path)
                # Resize logic (cover)
                img_w, img_h = pil_img.size
                ratio = max(w/img_w, h/img_h)
                new_size = (int(img_w*ratio), int(img_h*ratio))
                pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                # Crop center
                left = (new_size[0] - w)/2
                top = (new_size[1] - h)/2
                pil_img = pil_img.crop((left, top, left+w, top+h))
                
                self.tk_img = ImageTk.PhotoImage(pil_img) # Referenz halten
                self.create_image(0, 0, image=self.tk_img, anchor="nw")
            except Exception as e:
                print(f"MediaBar Image Error: {e}")

        # 2. Text & Content (Schatten für Lesbarkeit)
        title = item.get("title", "")
        text = item.get("text", "")
        
        # Titel (Schatten + Text)
        self.create_text(42, h//2 - 48, text=title, font=("Segoe UI", 26, "bold"), fill="black", anchor="w")
        self.create_text(40, h//2 - 50, text=title, font=("Segoe UI", 26, "bold"), fill="white", anchor="w")
        
        # Beschreibung
        self.create_text(42, h//2 + 12, text=text, font=("Segoe UI", 12), fill="black", anchor="w", width=w*0.6)
        self.create_text(40, h//2 + 10, text=text, font=("Segoe UI", 12), fill="#dddddd", anchor="w", width=w*0.6)
        
        # 3. Button
        link = item.get("link", "")
        if link:
            self.action_btn.command = lambda: webbrowser.open(link)
            self.create_window(40, h - 50, window=self.action_btn, anchor="nw")

def create_main():
    setup_logging() 
    crash_handler.install_exception_handler()
    
    if hasattr(threading, 'excepthook'):
        threading.excepthook = lambda args: crash_handler.global_exception_handler(args.exc_type, args.exc_value, args.exc_traceback)
    
    root = tk.Tk()
    root.report_callback_exception = crash_handler.global_exception_handler
    root.withdraw() 
    
    setup_wizard.check_and_run_setup(root)
    
    global USER_CREDS
    USER_CREDS = load_credentials()
    
    root.title("LeprendiX Launcher")
    
    w, h = 1100, 850
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = int((ws/2) - (w/2)) + 100
    y = int((hs/2) - (h/2))
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.configure(bg=COLOR_BG_MAIN)

    watchdog = AppWatchdog(root)
    watchdog.start()

    # --- AUTHENTICATION CHECK ---
    auth_enabled = CONFIG.get("AUTH_ENABLED", False)

    def get_kpi_data():
        db_path = os.path.join(BASE_DIR, "patienten.db")
        if not os.path.exists(db_path):
            return {"total_patients": "N/A", "open_invoices": "N/A"}

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM patienten WHERE is_archived = 0 OR is_archived IS NULL")
            total_patients = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM patienten WHERE invoiced_since_reset = 0 AND (is_archived = 0 OR is_archived IS NULL)")
            open_invoices = cursor.fetchone()[0]
            
            conn.close()
            return {"total_patients": total_patients, "open_invoices": open_invoices}
        except sqlite3.OperationalError:
            return {"total_patients": "DB?", "open_invoices": "DB?"}
        except Exception:
            return {"total_patients": "Fehler", "open_invoices": "Fehler"}

    class Dashboard(tk.Frame):
        def __init__(self, master):
            super().__init__(master, bg=COLOR_BG_MAIN)
            self.master = master
            self.pages = {}
            self.nav_buttons = {}
            self.active_button = None

            self._create_widgets()
            self.show_page("dashboard")

        def _create_widgets(self):
            self.sidebar_frame = tk.Frame(self, bg=COLOR_SIDEBAR, width=240)
            self.sidebar_frame.pack(side="left", fill="y")
            self.sidebar_frame.pack_propagate(False)

            self.main_frame = tk.Frame(self, bg=COLOR_BG_MAIN)
            self.main_frame.pack(side="left", fill="both", expand=True)

            self._create_sidebar_content()
            self._create_main_content()

        def _create_sidebar_content(self):
            # Logo
            logo_frame = tk.Frame(self.sidebar_frame, bg=COLOR_SIDEBAR)
            logo_frame.pack(pady=30, padx=20, fill='x')
            if os.path.exists(LOGO_PATH):
                img = Image.open(LOGO_PATH).resize((50, 50), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img)
                logo_lbl = tk.Label(logo_frame, image=img_tk, bg=COLOR_SIDEBAR)
                logo_lbl.image = img_tk
                logo_lbl.pack(side="left")
            tk.Label(logo_frame, text="LeprendiX", font=("Segoe UI", 18, "bold"), fg=COLOR_TEXT, bg=COLOR_SIDEBAR).pack(side="left", padx=10)

            # Navigation
            nav_frame = tk.Frame(self.sidebar_frame, bg=COLOR_SIDEBAR)
            nav_frame.pack(pady=20, padx=20, fill='x')

            nav_items = [
                ("dashboard", "\U0001F3E0", "Dashboard"),
                ("rechnungen", "\U0001F4DD", "Rechnungen"),
                ("material", "\U0001F4E6", "Materialbestellungen")
            ]

            for name, icon, text in nav_items:
                btn = tk.Button(nav_frame, text=f" {icon}  {text}", font=("Segoe UI", 12), fg=COLOR_TEXT_DIM, bg=COLOR_SIDEBAR,
                                relief="flat", anchor="w", padx=15, pady=10,
                                activebackground=COLOR_PANEL, activeforeground=COLOR_TEXT,
                                command=lambda n=name: self.show_page(n))
                btn.pack(fill='x', pady=4)
                self.nav_buttons[name] = btn

            # Bottom controls
            bottom_frame = tk.Frame(self.sidebar_frame, bg=COLOR_SIDEBAR)
            bottom_frame.pack(side="bottom", fill='x', pady=20, padx=20)

            settings_btn = tk.Button(bottom_frame, text=" \U00002699  Einstellungen", font=("Segoe UI", 11), fg=COLOR_TEXT_DIM, bg=COLOR_SIDEBAR,
                                     relief="flat", anchor="w", padx=15, pady=10,
                                     activebackground=COLOR_PANEL, activeforeground=COLOR_TEXT,
                                     command=lambda: self.show_page("settings"))
            settings_btn.pack(fill='x', pady=2)
            self.nav_buttons["settings"] = settings_btn

            exit_btn = tk.Button(bottom_frame, text=" \U0001F6AA  Beenden", font=("Segoe UI", 11), fg=COLOR_DANGER, bg=COLOR_SIDEBAR,
                                 relief="flat", anchor="w", padx=15, pady=10,
                                 activebackground=COLOR_PANEL, activeforeground="white",
                                 command=self.master.destroy)
            exit_btn.pack(fill='x', pady=2)

        def _create_main_content(self):
            self.pages["dashboard"] = self._create_dashboard_page(self.main_frame)
            self.pages["rechnungen"] = self._create_module_page(self.main_frame, "Rechnungen", "Rechnungs-Generator öffnen", lambda: launch_gui_generator(self.master))
            self.pages["material"] = self._create_module_page(self.main_frame, "Materialbestellungen", "Modul öffnen", launch_material_orders)
            self.pages["settings"] = self._create_settings_page(self.main_frame)

        def _create_dashboard_page(self, parent):
            page = tk.Frame(parent, bg=COLOR_BG_MAIN, padx=40, pady=30)
            
            # Media Bar
            media_items = [
                {
                    "title": "LeprendiX 1.7.3", 
                    "text": "A new, slick design that's easier on the eyes and more intuitive to navigate. Try it out now!",
                    "color": "#2c3e50",
                    "link": "https://sarbright-server.web.app/"
                },
                {
                    "title": "Try the Android companion app!", 
                    "text": "Upload patient date in a snap!",
                    "color": "#8e44ad",
                    "link": "https://github.com/qztq/LeprendiX/releases"
                },
                {
                    "title": "LeprendiX", 
                    "text": "For a better world.",
                    "color": "#5351A0",
                    "link": ""
                }
            ]
            MediaBar(page, media_items).pack(fill='x', pady=(0, 20))

            tk.Label(page, text="Welcome to LeprenidX!", font=("Segoe UI", 28, "bold"), fg=COLOR_TEXT, bg=COLOR_BG_MAIN).pack(anchor="w")
            tk.Label(page, text="What do you want to do today?", font=("Segoe UI", 14), fg=COLOR_TEXT_DIM, bg=COLOR_BG_MAIN).pack(anchor="w", pady=(0, 30))

            # KPI Cards
            kpi_frame = tk.Frame(page, bg=COLOR_BG_MAIN)
            kpi_frame.pack(fill='x', pady=20)
            
            kpi_data = get_kpi_data()

            def create_kpi_card(parent, title, value, color):
                card = tk.Frame(parent, bg=COLOR_PANEL, height=120)
                card.pack(side="left", fill="x", expand=True, padx=10)
                card.pack_propagate(False)
                
                tk.Frame(card, bg=color, width=5).pack(side="left", fill="y")
                
                tk.Label(card, text=value, font=("Segoe UI", 36, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL).pack(pady=(15, 0))
                tk.Label(card, text=title, font=("Segoe UI", 11), fg=COLOR_TEXT_DIM, bg=COLOR_PANEL).pack()

            create_kpi_card(kpi_frame, "Alle Patienten:", kpi_data["total_patients"], "#3498db")
            create_kpi_card(kpi_frame, "Nicht geschriebene Patienten:", kpi_data["open_invoices"], "#e67e22")

            # Quick Actions
            tk.Label(page, text="Schnellzugriff", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT, bg=COLOR_BG_MAIN).pack(anchor="w", pady=(40, 10))
            
            actions_frame = tk.Frame(page, bg=COLOR_BG_MAIN)
            actions_frame.pack(fill='x')

            RoundedButton(actions_frame, text="HIER STARTEN -->", command=lambda: launch_gui_generator(self.master), width=400, height=60, bg=COLOR_ACCENT).pack(fill='x', pady=10)
            RoundedButton(actions_frame, text="Materialbestellungen -->", command=launch_material_orders, width=400, height=60, bg=COLOR_SECONDARY).pack(fill='x', pady=10)

            return page

        def _create_module_page(self, parent, title, button_text, command):
            page = tk.Frame(parent, bg=COLOR_BG_MAIN, padx=40, pady=30)
            tk.Label(page, text=title, font=("Segoe UI", 28, "bold"), fg=COLOR_TEXT, bg=COLOR_BG_MAIN).pack(anchor="w", pady=(0, 30))
            
            container = tk.Frame(page, bg=COLOR_PANEL)
            container.pack(fill='both', expand=True)

            RoundedButton(container, text=button_text, command=command, width=400, height=80, bg=COLOR_ACCENT, font=("Segoe UI", 16, "bold")).place(relx=0.5, rely=0.5, anchor="center")
            return page

        def _create_settings_page(self, parent):
            page = tk.Frame(parent, bg=COLOR_BG_MAIN)
            
            # Header
            tk.Label(page, text="Einstellungen", font=("Segoe UI", 28, "bold"), fg=COLOR_TEXT, bg=COLOR_BG_MAIN).pack(anchor="w", padx=40, pady=(30, 20))

            # Scrollable Container
            canvas = tk.Canvas(page, bg=COLOR_BG_MAIN, highlightthickness=0)
            scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
            scroll_frame = tk.Frame(canvas, bg=COLOR_BG_MAIN)

            scroll_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox("all")
                )
            )

            canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

            def _configure_canvas(event):
                canvas.itemconfig(canvas_window, width=event.width)
            
            canvas.bind("<Configure>", _configure_canvas)
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True, padx=40)
            scrollbar.pack(side="right", fill="y")

            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            page.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

            # --- KATEGORIE 1: ALLGEMEIN & SICHERHEIT ---
            cat_gen = CollapsiblePane(scroll_frame, "Allgemein & Sicherheit", expanded=True)
            cat_gen.pack(fill="x", pady=5, padx=5)
            
            # Auth Toggle
            auth_var = tk.BooleanVar(value=CONFIG.get("AUTH_ENABLED", False))
            def toggle_auth():
                CONFIG["AUTH_ENABLED"] = auth_var.get()
                try:
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(CONFIG, f, indent=4)
                except Exception as e:
                    messagebox.showerror("Fehler", f"Speichern fehlgeschlagen: {e}")

            cb_auth = tk.Checkbutton(cat_gen.frame, text="Passwortschutz beim Start aktivieren", variable=auth_var, 
                                     bg=COLOR_PANEL, fg="white", selectcolor=COLOR_BG_MAIN, activebackground=COLOR_BG_MAIN, activeforeground="white",
                                     command=toggle_auth)
            cb_auth.pack(anchor="w", pady=10)

            def create_config_entry(parent, label_text, config_key, show_char=None):
                row = tk.Frame(parent, bg=COLOR_PANEL)
                row.pack(fill="x", pady=5)
                tk.Label(row, text=label_text, fg=COLOR_TEXT, bg=COLOR_PANEL, font=("Segoe UI", 10, "bold"), width=30, anchor="w").pack(side="left")
                
                var = tk.StringVar(value=CONFIG.get(config_key, ""))
                entry = tk.Entry(row, textvariable=var, bg="#333333", fg="white", relief="flat", show=show_char)
                entry.pack(side="left", fill="x", expand=True, padx=10, ipady=3)
                
                def save_val():
                    CONFIG[config_key] = var.get().strip()
                    try:
                        with open("config.json", "w", encoding="utf-8") as f:
                            json.dump(CONFIG, f, indent=4)
                        messagebox.showinfo("Gespeichert", f"{label_text} gespeichert.")
                    except Exception as e:
                        messagebox.showerror("Fehler", f"Speichern fehlgeschlagen: {e}")
                        
                tk.Button(row, text="Speichern", bg="#444444", fg="white", font=("Segoe UI", 8), 
                        relief="flat", command=save_val, padx=10).pack(side="right")

            create_config_entry(cat_gen.frame, "Hotkey Hauptaktion (Enter):", "HOTKEY_ENTER")
            create_config_entry(cat_gen.frame, "Hotkey Tab-Wechsel:", "HOTKEY_SWITCH_TAB")

            # --- KATEGORIE 2: DATENBANK & PFADE ---
            cat1 = CollapsiblePane(scroll_frame, "Datenbank & Pfade", expanded=False)
            cat1.pack(fill="x", pady=5, padx=5)
            
            # Datenbank Init
            tk.Label(cat1.frame, text="Datenbank-Initialisierung (Admin-Passwort benötigt)", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL).pack(pady=(10, 5), anchor="w")

            db_p_ent = tk.Entry(cat1.frame, show="*", width=30, bg="#333333", 
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
                    
            tk.Button(cat1.frame, text="Datenbank Setup ausführen", bg="#e67e22", fg="white", 
                    font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=8, 
                    command=do_setup).pack(pady=10)

            # Pfad Konfiguration
            tk.Label(cat1.frame, text="Speicherorte", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL).pack(pady=(25, 5), anchor="w")

            # Frames für die Pfadanzeige
            def create_path_row(parent, label_text, config_key):
                row = tk.Frame(parent, bg=COLOR_PANEL)
                row.pack(fill="x", pady=5)
                
                tk.Label(row, text=label_text, fg=COLOR_TEXT, bg=COLOR_PANEL, font=("Segoe UI", 10, "bold"), width=20, anchor="w").pack(side="left")
                
                # Label zur Anzeige des aktuellen Pfads
                path_var = tk.StringVar(value=CONFIG.get(config_key, "Nicht gesetzt"))
                lbl = tk.Label(row, textvariable=path_var, fg="#bdc3c7", bg="#333333", font=("Consolas", 9), anchor="w", padx=10)
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

                tk.Button(row, text="Ändern", bg="#444444", fg="white", font=("Segoe UI", 8), 
                        relief="flat", command=change_path, padx=10).pack(side="right")

            # Erzeuge die Zeilen für die beiden Hauptpfade
            create_path_row(cat1.frame, "Patienten-Ordner:", "PATIENT_BASE_DIR")
            create_path_row(cat1.frame, "Archiv-Ordner:", "ARCHIVE_DIR")

            # --- KATEGORIE 3: INTEGRATIONEN (API) ---
            cat2 = CollapsiblePane(scroll_frame, "Integrationen (API)", expanded=False)
            cat2.pack(fill="x", pady=5, padx=5)
            create_config_entry(cat2.frame, "Teamup API Key:", "TEAMUP_API_KEY", show_char="*")
            create_config_entry(cat2.frame, "Teamup Calendar ID:", "TEAMUP_CALENDAR_ID")

            # --- KATEGORIE 4: STANDARDWERTE ---
            cat3 = CollapsiblePane(scroll_frame, "Standardwerte & Editor", expanded=False)
            cat3.pack(fill="x", pady=5, padx=5)

            create_config_entry(cat3.frame, "Standard Diagnose:", "DEFAULT_DIAGNOSE")
            create_config_entry(cat3.frame, "Standard Anrede:", "DEFAULT_ANREDE")
            create_config_entry(cat3.frame, "Schnellwahl Beträge:", "QUICK_AMOUNTS")

            # --- Auto-Date Selector Settings ---
            date_frame = tk.Frame(cat3.frame, bg=COLOR_PANEL)
            date_frame.pack(fill="x", pady=5)
            
            tk.Label(date_frame, text="Datums-Modus (Teamup/Suche):", fg=COLOR_TEXT, bg=COLOR_PANEL, font=("Segoe UI", 10, "bold"), width=30, anchor="w").pack(side="left")
            
            date_mode_var = tk.StringVar(value=CONFIG.get("AUTO_DATE_SELECTOR", "Auto"))
            date_mode_combo = ttk.Combobox(date_frame, textvariable=date_mode_var, values=["Auto", "Manual"], state="readonly", width=10)
            date_mode_combo.pack(side="left", padx=10)
            
            # Manual Dates Row
            manual_date_frame = tk.Frame(cat3.frame, bg=COLOR_PANEL)
            manual_date_frame.pack(fill="x", pady=5)
            
            tk.Label(manual_date_frame, text="Manuell (YYYY-MM-DD):", fg=COLOR_TEXT, bg=COLOR_PANEL, width=30, anchor="w").pack(side="left")
            manual_start_var = tk.StringVar(value=CONFIG.get("MANUAL_DATE_START", ""))
            tk.Entry(manual_date_frame, textvariable=manual_start_var, width=12).pack(side="left", padx=5)
            
            tk.Label(manual_date_frame, text="bis", fg=COLOR_TEXT, bg=COLOR_PANEL).pack(side="left")
            manual_end_var = tk.StringVar(value=CONFIG.get("MANUAL_DATE_END", ""))
            tk.Entry(manual_date_frame, textvariable=manual_end_var, width=12).pack(side="left", padx=5)
            
            def save_date_settings():
                CONFIG["AUTO_DATE_SELECTOR"] = date_mode_var.get()
                CONFIG["MANUAL_DATE_START"] = manual_start_var.get()
                CONFIG["MANUAL_DATE_END"] = manual_end_var.get()
                try:
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(CONFIG, f, indent=4)
                    messagebox.showinfo("Gespeichert", "Datumseinstellungen gespeichert.")
                except Exception as e:
                    messagebox.showerror("Fehler", f"Speichern fehlgeschlagen: {e}")

            tk.Button(manual_date_frame, text="Speichern", bg="#444444", fg="white", font=("Segoe UI", 8), 
                    relief="flat", command=save_date_settings, padx=10).pack(side="right", padx=10)

            # --- KATEGORIE 5: WARTUNG & BACKUPS ---
            cat4 = CollapsiblePane(scroll_frame, "Wartung & Backups", expanded=False)
            cat4.pack(fill="x", pady=5, padx=5)
                    
            # Reminder
            tk.Label(cat4.frame, text="⚠️ WICHTIG: Bitte erstellen Sie regelmäßig Backups!", 
                    font=("Segoe UI", 10, "bold"), fg="#e74c3c", bg=COLOR_PANEL).pack(pady=(0, 10), anchor="w")

            # Backup Liste
            backup_list_frame = tk.LabelFrame(cat4.frame, text="Verfügbare Backups", bg=COLOR_PANEL, fg=COLOR_TEXT)
            backup_list_frame.pack(fill="x", pady=5, padx=10)
            
            backup_listbox = tk.Listbox(backup_list_frame, height=5, bg="#333333", fg="white", relief="flat")
            backup_listbox.pack(side="left", fill="x", expand=True, padx=5, pady=5)
            
            backup_scroll = tk.Scrollbar(backup_list_frame, command=backup_listbox.yview)
            backup_scroll.pack(side="right", fill="y", pady=5)
            backup_listbox.config(yscrollcommand=backup_scroll.set)

            def refresh_backups():
                backup_listbox.delete(0, tk.END)
                backup_dir = os.path.join(BASE_DIR, "backups")
                if os.path.exists(backup_dir):
                    try:
                        files = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")], reverse=True)
                        for f in files:
                            backup_listbox.insert(tk.END, f)
                    except Exception as e:
                        print(f"Fehler beim Listen der Backups: {e}")

            def create_backup():
                db_path = os.path.join(BASE_DIR, "patienten.db")
                if not os.path.exists(db_path):
                    messagebox.showerror("Fehler", "Datenbank nicht gefunden.")
                    return
                
                backup_dir = os.path.join(BASE_DIR, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(backup_dir, f"patienten_backup_{timestamp}.db")
                
                try:
                    shutil.copy2(db_path, backup_path)
                    messagebox.showinfo("Backup", f"Backup erfolgreich erstellt:\n{backup_path}")
                    refresh_backups()
                except Exception as e:
                    messagebox.showerror("Fehler", f"Backup fehlgeschlagen: {e}")

            def restore_backup():
                selection = backup_listbox.curselection()
                if not selection:
                    messagebox.showwarning("Auswahl", "Bitte wählen Sie ein Backup aus der Liste.")
                    return
                
                filename = backup_listbox.get(selection[0])
                backup_path = os.path.join(BASE_DIR, "backups", filename)
                db_path = os.path.join(BASE_DIR, "patienten.db")
                
                if messagebox.askyesno("Wiederherstellen", f"ACHTUNG: Möchten Sie die Datenbank wirklich auf den Stand von '{filename}' zurücksetzen?\n\nAlle Änderungen seit diesem Backup gehen verloren!"):
                    try:
                        shutil.copy2(backup_path, db_path)
                        messagebox.showinfo("Erfolg", "Datenbank wurde erfolgreich wiederhergestellt.")
                    except Exception as e:
                        messagebox.showerror("Fehler", f"Wiederherstellung fehlgeschlagen: {e}")

            def open_app_dir():
                try:
                    os.startfile(BASE_DIR) if sys.platform == 'win32' else subprocess.Popen(['xdg-open', BASE_DIR])
                except Exception as e:
                    messagebox.showerror("Fehler", f"Konnte Ordner nicht öffnen: {e}")

            def open_log_dir():
                app_name = "LeprendiX"
                if sys.platform == "win32":
                    base_path = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
                else:
                    base_path = os.path.join(os.path.expanduser("~"), ".local", "share")
                
                log_dir = os.path.join(base_path, app_name, "logs")
                
                if os.path.exists(log_dir):
                    try:
                        os.startfile(log_dir) if sys.platform == 'win32' else subprocess.Popen(['xdg-open', log_dir])
                    except Exception as e:
                        messagebox.showerror("Fehler", f"Konnte Log-Ordner nicht öffnen: {e}")
                else:
                    messagebox.showinfo("Info", f"Log-Ordner existiert noch nicht:\n{log_dir}")

            btn_frame = tk.Frame(cat4.frame, bg=COLOR_PANEL)
            btn_frame.pack(pady=5)
            tk.Button(btn_frame, text="Backup erstellen", bg="#444444", fg="white", font=("Segoe UI", 10), relief="flat", command=create_backup, padx=15, pady=5).pack(side="left", padx=5)
            tk.Button(btn_frame, text="Backup wiederherstellen", bg="#e67e22", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", command=restore_backup, padx=15, pady=5).pack(side="left", padx=5)
            tk.Button(btn_frame, text="Ordner öffnen", bg="#444444", fg="white", font=("Segoe UI", 10), relief="flat", command=open_app_dir, padx=15, pady=5).pack(side="left", padx=5)
            tk.Button(btn_frame, text="Logs öffnen", bg="#444444", fg="white", font=("Segoe UI", 10), relief="flat", command=open_log_dir, padx=15, pady=5).pack(side="left", padx=5)

            refresh_backups()
            
            return page

        def show_page(self, page_name):
            if self.active_button:
                self.active_button.config(bg=COLOR_SIDEBAR, fg=COLOR_TEXT_DIM)

            for page in self.pages.values():
                page.pack_forget()

            page_to_show = self.pages.get(page_name)
            if page_to_show:
                page_to_show.pack(fill="both", expand=True)

            button_to_activate = self.nav_buttons.get(page_name)
            if button_to_activate:
                button_to_activate.config(bg=COLOR_PANEL, fg=COLOR_TEXT)
                self.active_button = button_to_activate

    def show_launcher():
        # Clear root window
        for widget in root.winfo_children():
            widget.destroy()
        dashboard = Dashboard(root)
        dashboard.pack(fill="both", expand=True)

    def show_login():
        login_frame = tk.Frame(root, bg=COLOR_BG_MAIN)
        login_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(login_frame, text="SYSTEM LOCKED", font=("Segoe UI", 24, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_MAIN).pack(pady=20)
        
        tk.Label(login_frame, text="Benutzername", fg=COLOR_TEXT_DIM, bg=COLOR_BG_MAIN).pack(anchor="w")
        u_ent = tk.Entry(login_frame, width=30, bg=COLOR_PANEL, fg="white", relief="flat", font=("Segoe UI", 12))
        u_ent.pack(pady=(5, 15), ipady=5)
        if USER_CREDS: u_ent.insert(0, USER_CREDS.get("user", ""))
        
        tk.Label(login_frame, text="Passwort", fg=COLOR_TEXT_DIM, bg=COLOR_BG_MAIN).pack(anchor="w")
        p_ent = tk.Entry(login_frame, show="*", width=30, bg=COLOR_PANEL, fg="white", relief="flat", font=("Segoe UI", 12))
        p_ent.pack(pady=(5, 20), ipady=5)
        
        def try_login(e=None):
            if not USER_CREDS:
                messagebox.showerror("Fehler", "Keine Benutzerdaten gefunden.")
                return
            if u_ent.get() == USER_CREDS.get("user") and p_ent.get() == USER_CREDS.get("password"):
                login_frame.destroy()
                show_launcher()
            else:
                messagebox.showerror("Zugriff verweigert", "Falsche Anmeldedaten.")
                p_ent.delete(0, tk.END)
        
        RoundedButton(login_frame, text="UNLOCK", command=try_login, width=200, height=50, bg=COLOR_ACCENT).pack(pady=20)
        
        root.bind('<Return>', try_login)

    # --- STARTUP LOGIC ---
    if auth_enabled:
        show_login()
    else:
        show_launcher()

    def on_closing():
        watchdog.stop()
        root.destroy()
        sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.deiconify() # Fenster jetzt anzeigen (fertig geladen)
    root.mainloop()

if __name__ == "__main__":
    if "--crash-handler" in sys.argv:
        crash_handler.main()
    else:
        create_main()