# leprendix/gui/control_center.py
import tkinter as tk
from .theme import COLOR_PRIMARY, COLOR_SECONDARY

class CollapsiblePane(tk.Frame):
    """Eine aufklappbare Frame-Komponente für Einstellungen."""
    def __init__(self, parent, title, expanded=False, bg_color=COLOR_PRIMARY):
        super().__init__(parent, bg=bg_color)
        self.columnconfigure(0, weight=1)
        self._variable = tk.BooleanVar(value=expanded)
        self._title = title
        self._bg = bg_color
        
        self._button = tk.Button(self, text=f"{'▼' if expanded else '▶'} {title}", 
                                 command=self._toggle, relief="flat", 
                                 bg=COLOR_SECONDARY, fg="white", 
                                 font=("Segoe UI", 12, "bold"), anchor="w", padx=10, pady=5)
        self._button.grid(row=0, column=0, sticky="ew", pady=(5,0))
        
        self.frame = tk.Frame(self, bg=self._bg)
        if expanded:
            self.frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
            
    def _toggle(self):
        if self._variable.get():
            self.frame.grid_remove()
            self._variable.set(False)
            self._button.configure(text=f"▶ {self._title}")
        else:
            self.frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
            self._variable.set(True)
            self._button.configure(text=f"▼ {self._title}")