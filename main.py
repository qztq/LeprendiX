# launcher.py

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
from PIL import Image, ImageTk 

# --- KONFIGURATION ---
SPLASH_IMAGE_PATH = 'splash_image.png'
MAIN_SCRIPT_NAME = 'gui_generator.py' 

class AppLauncher:
    def __init__(self, master):
        self.master = master
        master.title("Anwendungs-Launcher")
        master.resizable(False, False)
        
        # NEU: Fenstersteuerelemente ausblenden (Entfernt die Titelzeile und Buttons)
        master.overrideredirect(True) 
        
        # NEU: Standardbreite und -höhe festlegen
        initial_width = 600
        initial_height = 450
        self.center_window(initial_width, initial_height)

        self.setup_ui()

    def setup_ui(self):
        """Erstellt das Layout mit Bild, Start- und Beenden-Button."""
        
        # --- Bild-Bereich ---
        try:
            # 1. Bild laden und auf max. 560 Breite skalieren (damit es in das 600px breite Fenster passt)
            img = Image.open(SPLASH_IMAGE_PATH)
            
            max_width = 560 # NEU: Breiteres Limit
            if img.width > max_width:
                height = int(img.height * (max_width / img.width))
                img = img.resize((max_width, height))
            
            self.splash_photo = ImageTk.PhotoImage(img)
            
            self.image_label = ttk.Label(self.master, image=self.splash_photo)
            self.image_label.pack(padx=20, pady=20)
            
            # Fenster nach Bildgröße neu zentrieren (Wichtig, da die Höhe des Fensters sich an das Bild anpasst)
            self.master.update_idletasks()
            width = self.master.winfo_width()
            height = self.master.winfo_height()
            self.center_window(width, height)
            
        except FileNotFoundError:
            self.image_label = ttk.Label(self.master, text=f"ACHTUNG: '{SPLASH_IMAGE_PATH}' nicht gefunden!", foreground='red')
            self.image_label.pack(padx=20, pady=20)
        except Exception as e:
            self.image_label = ttk.Label(self.master, text=f"Fehler beim Laden des Bildes: {e}", foreground='red')
            self.image_label.pack(padx=20, pady=20)


        # --- Buttons ---
        button_frame = ttk.Frame(self.master)
        button_frame.pack(pady=10, padx=20)

        # Start-Button
        ttk.Button(button_frame, text="▶️ LebrendiX starten", command=self.start_main_app, style='TButton', width=25).pack(side=tk.LEFT, padx=10)
        
        # Beenden-Button
        ttk.Button(button_frame, text="❌ Beenden", command=self.master.quit, width=15).pack(side=tk.LEFT, padx=10)

        # Stil für den Haupt-Button
        style = ttk.Style()
        style.configure('TButton', font=('Helvetica', 12, 'bold'), padding=10)

    def start_main_app(self):
        """Schließt den Launcher und startet die Hauptanwendung."""
        
        # Fenster schließen, bevor das neue gestartet wird
        self.master.destroy() 
        
        try:
            subprocess.Popen([sys.executable, MAIN_SCRIPT_NAME])
        except Exception as e:
            # Da das Hauptfenster bereits zerstört ist, ist eine MessageBox hier schwierig.
            # Ein externer Fehlerdialog wäre besser. Wir geben es auf der Konsole aus.
            print(f"FATALER STARTFEHLER: Konnte das Hauptskript '{MAIN_SCRIPT_NAME}' nicht starten. Fehler: {e}")
            

    def center_window(self, width, height):
        """Zentriert das Fenster auf dem Bildschirm und setzt die Größe."""
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        self.master.geometry(f'{width}x{height}+{x}+{y}')


if __name__ == "__main__":
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("Die 'Pillow' (PIL) Bibliothek ist nicht installiert. Bitte installieren Sie sie mit: pip install Pillow")
        sys.exit(1)
        
    root = tk.Tk()
    app = AppLauncher(root)
    root.mainloop()