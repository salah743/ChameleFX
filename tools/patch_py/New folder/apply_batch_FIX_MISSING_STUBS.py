import os
from pathlib import Path
from fastapi import APIRouter

ROOT = Path(__file__).resolve().parents[2]

# --- Risk Status Router ---
api_dir = ROOT / "app" / "api"
api_dir.mkdir(parents=True, exist_ok=True)
risk_file = api_dir / "ext_risk_status.py"
if not risk_file.exists():
    risk_file.write_text(
        "from fastapi import APIRouter\n\n"
        "router = APIRouter()\n\n"
        "@router.get('/risk/state')\n"
        "async def get_risk_state():\n"
        "    return { 'ok': True, 'state': 'stub' }\n"
    )
    print("[OK] Created", risk_file)

# --- Backtest Tab UI ---
ui_dir = ROOT / "chamelefx" / "ui"
ui_dir.mkdir(parents=True, exist_ok=True)
bt_file = ui_dir / "backtest_tab.py"
if not bt_file.exists():
    bt_file.write_text(
        "import tkinter as tk\n\n"
        "class BacktestTab(tk.Frame):\n"
        "    def __init__(self, master=None, **kwargs):\n"
        "        super().__init__(master, **kwargs)\n"
        "        lbl = tk.Label(self, text='[Backtest Panel Placeholder]')\n"
        "        lbl.pack(fill='both', expand=True)\n"
    )
    print("[OK] Created", bt_file)
