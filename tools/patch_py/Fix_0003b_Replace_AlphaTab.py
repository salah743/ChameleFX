
from pathlib import Path
from patchlib import project_root, backup_write

ROOT = project_root(Path(__file__))
p = ROOT / "chamelefx/ui/alpha_tab.py"
if not p.exists():
    print(f"[WARN] {p} not found")
else:
    new_src = """from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import json, os, threading

try:
    import requests
except Exception:
    requests = None

def _default_base():
    cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return (
            cfg.get("api", {}).get("base")
            or cfg.get("app", {}).get("api_base")
            or cfg.get("server", {}).get("base_url")
            or "http://127.0.0.1:18124"
        )
    except Exception:
        return "http://127.0.0.1:18124"

class AlphaTab(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        top = tk.Frame(self); top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="API Base:").pack(side="left")
        self.api_entry = tk.Entry(top, width=36)
        self.api_entry.insert(0, _default_base())
        self.api_entry.pack(side="left", padx=6)

        tk.Label(top, text="Symbol:").pack(side="left", padx=(12,0))
        self.sym_var = tk.StringVar(value="EURUSD")
        opts = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "XAUUSD"]
        tk.OptionMenu(top, self.sym_var, *opts).pack(side="left", padx=6)

        btns = tk.Frame(top); btns.pack(side="right")
        tk.Button(btns, text="Compute Features", command=self.compute_features).pack(side="left", padx=4)
        tk.Button(btns, text="Preview Sizing", command=self.preview_sizing).pack(side="left", padx=4)

        # second row controls
        row2 = tk.Frame(self); row2.pack(fill="x", padx=8, pady=(0,6))
        tk.Label(row2, text="Weight:").pack(side="left")
        self.e_weight = tk.Entry(row2, width=7); self.e_weight.insert(0, "0.25"); self.e_weight.pack(side="left", padx=6)
        tk.Label(row2, text="Lots (auto):").pack(side="left")
        self.e_lots_auto = tk.Entry(row2, width=10); self.e_lots_auto.configure(state="readonly"); self.e_lots_auto.pack(side="left", padx=6)

        # table for features
        self.tbl = ttk.Treeview(self, columns=("k","v"), show="headings", height=14)
        self.tbl.heading("k", text="FEATURE"); self.tbl.column("k", width=180, anchor="w")
        self.tbl.heading("v", text="VALUE"); self.tbl.column("v", width=120, anchor="e")
        self.tbl.pack(fill="both", expand=True, padx=8, pady=6)

    def _base(self) -> str:
        return (self.api_entry.get() or "http://127.0.0.1:18124").rstrip("/")

    def _selected_symbol(self) -> str:
        return self.sym_var.get() or "EURUSD"

    def compute_features(self):
        if not requests:
            return
        sym = self._selected_symbol()
        try:
            j = requests.post(self._base() + "/alpha/features/compute", json={"symbol": sym}, timeout=5.0).json()
        except Exception:
            return
        self.tbl.delete(*self.tbl.get_children())
        data = j.get("norm") or j.get("raw") or {}
        for k, v in sorted(data.items()):
            try:
                vv = f"{float(v):.4f}"
            except Exception:
                vv = str(v)
            self.tbl.insert("", "end", values=(k, vv))

    def preview_sizing(self):
        if not requests:
            return
        sym = self._selected_symbol()
        try:
            w = float(self.e_weight.get() or 0.25)
        except Exception:
            w = 0.25
        try:
            pr = requests.post(self._base() + "/sizing/regime/preview", json={"symbol": sym, "weight": w}, timeout=5.0).json()
            lots = pr.get("lots", None)
            if lots is not None:
                self.e_lots_auto.configure(state='normal')
                self.e_lots_auto.delete(0, 'end')
                self.e_lots_auto.insert(0, f"{float(lots):.2f}")
                self.e_lots_auto.configure(state='readonly')
        except Exception:
            pass
"""
    backup_write(p, new_src)
    print("[OK] alpha_tab.py replaced with clean implementation")
