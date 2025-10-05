# -*- coding: utf-8 -*-
"""
Bundle H — Ops & UX Polish
Adds:
- UI: blotter_tab.py (orders/positions), logs_tab.py (log tails), ops_tab.py (Safe Mode)
- API: ext_orders_blotter.py, ext_logs.py, ext_safe_mode.py
- Wires server safely (after __future__)
- Mounts tabs in Manager (idempotent)
"""
from __future__ import annotations
import json, time, shutil, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
API  = ROOT / "app" / "api"
UI   = CFX / "ui"
RUN  = CFX / "runtime"
TEL  = ROOT / "data" / "telemetry"
LOGS = ROOT / "data" / "logs"

def w(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def b(p: Path):
    if p.exists(): shutil.copy2(p, p.with_suffix(p.suffix + f".bak.{int(time.time())}"))

def place_after_future(txt: str, import_line: str) -> str:
    lines = txt.splitlines()
    n = len(lines); i = 0
    # skip shebang/encoding/comments/blank + docstring
    while i < n and (lines[i].strip()=="" or lines[i].lstrip().startswith("#") or lines[i].startswith("\ufeff")):
        i += 1
    if i < n and lines[i].lstrip().startswith(("'''",'\"\"\"')):
        q = "'''" if lines[i].lstrip().startswith("'''") else '"""'
        i += 1
        while i < n and q not in lines[i]:
            i += 1
        if i < n: i += 1
    # now after docstring; find future block
    j=i; last_future=-1
    while j<n and lines[j].strip().startswith("from __future__ import"):
        last_future=j; j+=1
    idx = (last_future+1) if last_future>=0 else 0
    if import_line in "\n".join(lines): return "\n".join(lines)
    lines.insert(idx, import_line)
    return "\n".join(lines)

def append_include(txt: str, inc: str) -> str:
    if inc in txt: return txt
    if not txt.endswith("\n"): txt += "\n"
    return txt + "\n" + inc + "\n"

def wire_server():
    srv = API / "server.py"
    if not srv.exists(): return
    t = srv.read_text(encoding="utf-8")
    for imp, inc in [
        ("from app.api.ext_orders_blotter import router as orders_blotter_router", "app.include_router(orders_blotter_router)"),
        ("from app.api.ext_logs import router as logs_router", "app.include_router(logs_router)"),
        ("from app.api.ext_safe_mode import router as safe_mode_router", "app.include_router(safe_mode_router)"),
    ]:
        t2 = place_after_future(t, imp)
        t2 = append_include(t2, inc)
        t = t2
    b(srv); srv.write_text(t, encoding="utf-8")

def mount_tabs_in_manager():
    m = CFX / "manager.py"
    if not m.exists(): return
    txt = m.read_text(encoding="utf-8")
    changed = False
    # imports
    if "from chamelefx.ui.blotter_tab import BlotterTab" not in txt:
        txt = "from chamelefx.ui.blotter_tab import BlotterTab\n" + txt
        changed = True
    if "from chamelefx.ui.logs_tab import LogsTab" not in txt:
        txt = "from chamelefx.ui.logs_tab import LogsTab\n" + txt
        changed = True
    if "from chamelefx.ui.ops_tab import OpsTab" not in txt:
        txt = "from chamelefx.ui.ops_tab import OpsTab\n" + txt
        changed = True
    # find a Notebook section and add tabs once
    if "notebook.add(tab_blotter, text=\"Blotter\")" not in txt:
        txt = txt.replace(
            'notebook.add(tab_portfolio, text="Portfolio")',
            'notebook.add(tab_portfolio, text="Portfolio")\n        tab_blotter=BlotterTab(notebook)\n        notebook.add(tab_blotter, text="Blotter")'
        )
        changed = True
    if "notebook.add(tab_logs, text=\"Logs\")" not in txt:
        # add after blotter
        txt = txt.replace(
            'notebook.add(tab_blotter, text="Blotter")',
            'notebook.add(tab_blotter, text="Blotter")\n        tab_logs=LogsTab(notebook)\n        notebook.add(tab_logs, text="Logs")'
        )
        changed = True
    if "notebook.add(tab_ops, text=\"Ops\")" not in txt:
        # add after logs
        txt = txt.replace(
            'notebook.add(tab_logs, text="Logs")',
            'notebook.add(tab_logs, text="Logs")\n        tab_ops=OpsTab(notebook)\n        notebook.add(tab_ops, text="Ops")'
        )
        changed = True
    if changed:
        b(m); m.write_text(txt, encoding="utf-8")

# ----- UI files -----

BLOTTER_TAB = r'''
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import json, requests
from pathlib import Path

API = "http://127.0.0.1:18124"

class BlotterTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=4)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(top, text="Cancel Selected", command=self.cancel_selected).pack(side="left", padx=6)
        ttk.Button(top, text="Replace Size", command=self.replace_selected).pack(side="left", padx=6)

        self.tree_open = ttk.Treeview(self, columns=("id","symbol","side","qty","price","ts"), show="headings", height=10)
        for c,w in [("id",120),("symbol",80),("side",60),("qty",80),("price",90),("ts",160)]:
            self.tree_open.heading(c, text=c.upper()); self.tree_open.column(c, width=w, anchor="center")
        self.tree_open.pack(fill="both", expand=True, padx=6, pady=4)

        ttk.Label(self, text="Recent Fills:").pack(anchor="w", padx=6)
        self.tree_fills = ttk.Treeview(self, columns=("id","symbol","side","qty","price","ts"), show="headings", height=6)
        for c,w in [("id",120),("symbol",80),("side",60),("qty",80),("price",90),("ts",160)]:
            self.tree_fills.heading(c, text=c.upper()); self.tree_fills.column(c, width=w, anchor="center")
        self.tree_fills.pack(fill="both", expand=True, padx=6, pady=4)

        self.after(2000, self.refresh)

    def _load(self, url):
        try:
            r = requests.get(url, timeout=2)
            if r.ok: return r.json()
        except Exception:
            pass
        return {"ok": False}

    def refresh(self):
        openo = self._load(f"{API}/orders/open")
        fills = self._load(f"{API}/orders/recent")
        # open orders
        for i in self.tree_open.get_children(): self.tree_open.delete(i)
        for o in (openo.get("orders") or []):
            self.tree_open.insert("", "end", values=(o.get("id"), o.get("symbol"), o.get("side"), o.get("qty"), o.get("price"), o.get("ts")))
        # recent fills
        for i in self.tree_fills.get_children(): self.tree_fills.delete(i)
        for o in (fills.get("fills") or []):
            self.tree_fills.insert("", "end", values=(o.get("id"), o.get("symbol"), o.get("side"), o.get("qty"), o.get("price"), o.get("ts")))
        self.after(4000, self.refresh)

    def _selected_id(self):
        sel = self.tree_open.selection()
        if not sel: return None
        vals = self.tree_open.item(sel[0]).get("values") or []
        return vals[0] if vals else None

    def cancel_selected(self):
        oid = self._selected_id()
        if not oid: return
        try:
            r = requests.post(f"{API}/orders/cancel", json={"order_id": oid}, timeout=2)
            if not r.ok: messagebox.showwarning("Cancel", "Failed to cancel.")
        except Exception:
            pass

    def replace_selected(self):
        oid = self._selected_id()
        if not oid: return
        # naive replace prompt
        import tkinter.simpledialog as sd
        new_qty = sd.askstring("Replace Size", "New quantity:")
        if not new_qty: return
        try:
            qty = float(new_qty)
            r = requests.post(f"{API}/orders/replace", json={"order_id": oid, "new_qty": qty}, timeout=2)
            if not r.ok: messagebox.showwarning("Replace", "Failed to replace.")
        except Exception:
            pass
'''

LOGS_TAB = r'''
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import requests

API = "http://127.0.0.1:18124"

class LogsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        controls = ttk.Frame(self); controls.pack(fill="x", padx=6, pady=4)
        ttk.Label(controls, text="Source:").pack(side="left")
        self.src = tk.StringVar(value="exec")
        cb = ttk.Combobox(controls, textvariable=self.src, values=("exec","alpha","risk","server"), width=10)
        cb.pack(side="left", padx=6)
        ttk.Button(controls, text="Tail 200", command=self.refresh).pack(side="left")
        self.txt = tk.Text(self, height=22)
        self.txt.pack(fill="both", expand=True, padx=6, pady=4)
        self.after(3000, self.refresh)

    def refresh(self):
        try:
            r = requests.get(f"{API}/logs/tail?source={self.src.get()}&n=200", timeout=2)
            if r.ok:
                self.txt.delete("1.0", "end")
                self.txt.insert("end", r.json().get("tail",""))
        except Exception:
            pass
        self.after(4000, self.refresh)
'''

OPS_TAB = r'''
from __future__ import annotations
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
            pass
        self.after(4000, self.refresh)

    def set_mode(self, enable: bool):
        try:
            requests.post(f"{API}/ops/safe_mode/toggle", json={"enable": bool(enable)}, timeout=2)
        except Exception:
            pass
        self.after(1000, self.refresh)
'''

# ----- API files -----

EXT_ORDERS = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from pathlib import Path
import json, time

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
RUN  = ROOT / "chamelefx" / "runtime"
RUN.mkdir(parents=True, exist_ok=True)

OPEN = RUN / "orders_open.json"
FILLS= RUN / "orders_recent.json"

def _j(p: Path, default):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default

@router.get("/orders/open")
def orders_open():
    return {"ok": True, "orders": _j(OPEN, [])}

@router.get("/orders/recent")
def orders_recent():
    return {"ok": True, "fills": _j(FILLS, [])}

@router.post("/orders/cancel")
def orders_cancel(order_id: str = Body(..., embed=True)):
    # stub: remove from OPEN if present
    arr = _j(OPEN, [])
    arr = [o for o in arr if str(o.get("id")) != str(order_id)]
    OPEN.write_text(json.dumps(arr, indent=2), encoding="utf-8")
    return {"ok": True, "order_id": order_id, "ts": time.time()}

@router.post("/orders/replace")
def orders_replace(order_id: str = Body(..., embed=True),
                   new_qty: float = Body(..., embed=True)):
    # stub: rewrite qty in OPEN
    arr = _j(OPEN, [])
    for o in arr:
        if str(o.get("id")) == str(order_id):
            o["qty"] = float(new_qty)
            o["ts"] = time.time()
    OPEN.write_text(json.dumps(arr, indent=2), encoding="utf-8")
    return {"ok": True, "order_id": order_id, "new_qty": new_qty, "ts": time.time()}
'''

EXT_LOGS = r'''
from __future__ import annotations
from fastapi import APIRouter, Query
from pathlib import Path
import io

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "data" / "logs"

def _tail(path: Path, n: int=200)->str:
    if not path.exists(): return ""
    try:
        # simple tail
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-n:]
        return "".join(lines)
    except Exception:
        return ""

@router.get("/logs/tail")
def logs_tail(source: str = Query("exec"), n: int = Query(200)):
    LOGS.mkdir(parents=True, exist_ok=True)
    fname = {
        "exec": "execution.log",
        "alpha":"alpha.log",
        "risk": "risk.log",
        "server":"server.log",
    }.get(source, "server.log")
    p = LOGS / fname
    return {"ok": True, "source": source, "tail": _tail(p, n)}
'''

EXT_SAFE = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from pathlib import Path
import json, time

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
RUN  = ROOT / "chamelefx" / "runtime"
RUN.mkdir(parents=True, exist_ok=True)
STATE = RUN / "safe_mode.json"

def _get():
    try: return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception: return {"enabled": False, "ts": 0}

def _set(enabled: bool):
    d = {"enabled": bool(enabled), "ts": time.time()}
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
    tmp.replace(STATE)
    return d

@router.get("/ops/safe_mode/status")
def safe_mode_status():
    return _get()

@router.post("/ops/safe_mode/toggle")
def safe_mode_toggle(enable: bool = Body(..., embed=True)):
    d = _set(enable)
    # optional: if enabling, reduce risk & disable costly venues quickly
    try:
        if d["enabled"]:
            # write a risk hint file (consumed by your pretrade/risk layer if wired)
            (RUN / "risk_hint.json").write_text(json.dumps({"risk_multiplier":0.5}, indent=2), encoding="utf-8")
            # disable an alt venue quickly (if present)
            from chamelefx.router import state as RS
            RS.disable("MT5_ALT", 900)
        else:
            (RUN / "risk_hint.json").write_text(json.dumps({"risk_multiplier":1.0}, indent=2), encoding="utf-8")
            from chamelefx.router import state as RS
            RS.enable("MT5_ALT")
    except Exception:
        pass
    return {"ok": True, "state": d}
'''

def ensure_runtime_files():
    RUN.mkdir(parents=True, exist_ok=True)
    TEL.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    # init arrays if absent
    for p,default in [
        (RUN/"orders_open.json", []),
        (RUN/"orders_recent.json", []),
        (RUN/"positions.json", []),
        (RUN/"account.json", {"equity": 100000.0, "balance": 100000.0}),
    ]:
        if not p.exists():
            p.write_text(json.dumps(default, indent=2), encoding="utf-8")

def main():
    ensure_runtime_files()
    # UI
    w(UI/"blotter_tab.py", BLOTTER_TAB)
    w(UI/"logs_tab.py",    LOGS_TAB)
    w(UI/"ops_tab.py",     OPS_TAB)
    # API
    w(API/"ext_orders_blotter.py", EXT_ORDERS)
    w(API/"ext_logs.py",           EXT_LOGS)
    w(API/"ext_safe_mode.py",      EXT_SAFE)
    # Wire server + mount tabs
    wire_server()
    mount_tabs_in_manager()
    print("[BundleH] Ops & UX Polish installed, wired, and mounted.")

if __name__ == "__main__":
    main()
