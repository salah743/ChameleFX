from __future__ import annotations
# Manager_Components/diagnostics.py
"""
Diagnostics & Crash-Proofing component
- Hooks Tk.report_callback_exception when Safe Mode is ON.
- Logs to logs/diagnostics.log and writes runtime/diagnostics.json snapshot.
- Shows a small floating red badge with live error/recovery counters.
- Adds "Diagnostics" menu (Safe Mode toggle, Simulate Exception, Open files).
"""

import os, sys, json, time, traceback, webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = APP_DIR / "logs"
RUNTIME_DIR = APP_DIR / "runtime"
SNAP = RUNTIME_DIR / "diagnostics.json"
LOGF = LOGS_DIR / "diagnostics.log"

class DiagnosticsComponent:
    name = "Diagnostics"

    def __init__(self, app):
        self.app = app
        self.root: tk.Tk = app  # type: ignore
        self.safe_mode = True
        self._orig_hook = None
        self._badge = None
        self._counters = {
            "ui_errors": 0,
            "recoveries": 0,
            "last_error": None,
            "safe_mode": True,
        }
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        self._load_snapshot()

    # ---- bootstrap ----------------------------------------------------------
    def on_init(self):
        self._ensure_menu()
        self._attach_hook()
        self._spawn_badge()
        self._save_snapshot()

    # ---- menu ---------------------------------------------------------------
    def _ensure_menu(self):
        menubar = getattr(self.root, "_menubar", None)
        if menubar is None:
            menubar = tk.Menu(self.root)
            self.root.winfo_toplevel().winfo_toplevel().config(menu=menubar)
            self.root._menubar = menubar

        # Avoid duplicate menu
        for i in range(menubar.index("end") + 1 if menubar.index("end") is not None else 0):
            if menubar.type(i) == "cascade":
                if menubar.entrycget(i, "label") == "Diagnostics":
                    return

        m = tk.Menu(menubar, tearoff=0)
        m.add_checkbutton(label="Safe Mode (catch UI errors)", onvalue=True, offvalue=False,
                          variable=tk.BooleanVar(value=self.safe_mode),
                          command=self._toggle_safe_mode)
        m.add_separator()
        m.add_command(label="Simulate Exception", command=self._simulate_exception)
        m.add_separator()
        m.add_command(label="Open diagnostics.json", command=lambda: self._open_path(SNAP))
        m.add_command(label="Open logs folder", command=lambda: self._open_path(LOGS_DIR, folder=True))
        m.add_separator()
        m.add_command(label="Reset Counters", command=self._reset)
        menubar.add_cascade(label="Diagnostics", menu=m)
        self._menu = m

    # ---- hooks & handling ---------------------------------------------------
    def _attach_hook(self):
        if self.safe_mode:
            if self._orig_hook is None:
                self._orig_hook = self.root.report_callback_exception
            self.root.report_callback_exception = self._hook
        else:
            if self._orig_hook is not None:
                self.root.report_callback_exception = self._orig_hook

    def _hook(self, exc, val, tb):
        # Count + persist + log + badge update
        self._counters["ui_errors"] += 1
        self._counters["last_error"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_snapshot()
        self._log_exception(exc, val, tb)
        self._update_badge()
        # Try to keep UI alive
        try:
            # Show compact toast-like warning
            self._toast(f"UI recovered from error:\n{val}", kind="warn")
            self._counters["recoveries"] += 1
            self._save_snapshot()
            self._update_badge()
        except Exception:
            pass

    # ---- badge --------------------------------------------------------------
    def _spawn_badge(self):
        # tiny top-right floating window, always-on-top
        self._badge = tk.Toplevel(self.root)
        self._badge.withdraw()
        self._badge.overrideredirect(True)
        self._badge.attributes("-topmost", True)
        frame = tk.Frame(self._badge, bg="#7f1d1d", bd=0, highlightthickness=0)
        frame.pack(fill="both", expand=True)
        self._lbl = tk.Label(frame, text="", font=("Segoe UI", 8, "bold"), bg="#7f1d1d", fg="#fff")
        self._lbl.pack(padx=8, pady=4)
        # position after main window settles
        self.root.after(600, self._place_badge)
        self._update_badge()

    def _place_badge(self):
        try:
            self._badge.deiconify()
            self._badge.update_idletasks()
            # place near top-right of root
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            self._badge.geometry(f"+{rx + rw - 130}+{ry + 60}")
        except Exception:
            pass

    def _update_badge(self):
        if not self._badge: return
        txt = f"Diagnostics  |  Errors: {self._counters['ui_errors']}  •  Recoveries: {self._counters['recoveries']}"
        if self._counters["last_error"]:
            txt += f"  •  Last: {self._counters['last_error']}"
        self._lbl.config(text=txt)

    # ---- UI helpers ---------------------------------------------------------
    def _toast(self, msg: str, kind: str = "info", timeout_ms: int = 2500):
        # small timed window
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        bg = {"info":"#0f766e","warn":"#b45309","err":"#991b1b"}.get(kind, "#0f766e")
        frm = tk.Frame(win, bg=bg); frm.pack()
        tk.Label(frm, text=msg, font=("Segoe UI", 8, "bold"), bg=bg, fg="#fff", justify="left").pack(padx=10, pady=8)
        self.root.after(10, lambda: win.geometry(f"+{self.root.winfo_rootx()+40}+{self.root.winfo_rooty()+40}"))
        self.root.after(timeout_ms, win.destroy)

    # ---- persistence & logging ----------------------------------------------
    def _load_snapshot(self):
        try:
            if SNAP.exists():
                self._counters.update(json.loads(SNAP.read_text(encoding="utf-8")) or {})
            self.safe_mode = bool(self._counters.get("safe_mode", True))
        except Exception:
            pass

    def _save_snapshot(self):
        try:
            self._counters["safe_mode"] = bool(self.safe_mode)
            SNAP.write_text(json.dumps(self._counters, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _log_exception(self, exc, val, tb):
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            with LOGF.open("a", encoding="utf-8") as f:
                f.write("="*70 + "\n")
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "  UI callback exception\n")
                traceback.print_exception(exc, val, tb, file=f)
        except Exception:
            pass

    # ---- actions -------------------------------------------------------------
    def _toggle_safe_mode(self):
        self.safe_mode = not self.safe_mode
        self._attach_hook()
        self._save_snapshot()
        self._toast(f"Safe Mode {'ENABLED' if self.safe_mode else 'disabled'}", "info")

    def _simulate_exception(self):
        def boom():
            raise RuntimeError("Simulated UI exception for diagnostics test")
        # Schedule on Tk loop to hit report_callback_exception
        self.root.after(50, boom)

    def _open_path(self, p: Path, folder: bool = False):
        try:
            p = p.resolve()
            if folder:
                if os.name == "nt":
                    os.startfile(str(p))
                else:
                    webbrowser.open(str(p))
            else:
                if not p.exists():
                    p.write_text("{}", encoding="utf-8")
                if os.name == "nt":
                    os.startfile(str(p))
                else:
                    webbrowser.open(str(p))
        except Exception as e:
            messagebox.showerror("Open", f"Failed to open: {p}\n{e}")

# factory ----------------------------------------------------------
def create(app):
    return DiagnosticsComponent(app)
