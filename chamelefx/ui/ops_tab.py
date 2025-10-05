from __future__ import annotations
from chamelefx.log import get_logger
import tkinter as tk
from tkinter import ttk
import requests

API = "http://127.0.0.1:18124"

class OpsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        top = ttk.LabelFrame(self, text="Safe Mode")
        top.pack(fill="x", padx=6, pady=6)
        self.state = tk.StringVar(value="UNKNOWN")
        ttk.Label(top, text="State:").pack(side="left", padx=6)
        ttk.Label(top, textvariable=self.state).pack(side="left", padx=6)
        ttk.Button(top, text="Enable", command=lambda: self.set_mode(True)).pack(side="left", padx=6)
        ttk.Button(top, text="Disable", command=lambda: self.set_mode(False)).pack(side="left", padx=6)
        self.after(1500, self.refresh)

    def refresh(self):
        try:
            r = requests.get(f"{API}/ops/safe_mode/status", timeout=2)
            if r.ok:
                self.state.set("ON" if r.json().get("enabled") else "OFF")
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
        self.after(4000, self.refresh)

    def set_mode(self, enable: bool):
        try:
            requests.post(f"{API}/ops/safe_mode/toggle", json={"enable": bool(enable, timeout=5.0)}, timeout=2)
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
        self.after(1000, self.refresh)
