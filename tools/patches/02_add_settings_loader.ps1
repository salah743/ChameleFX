# manager.py — ChameleFX unified dashboard (no external deps)
# Features: live signal/positions, color P/L & risk badges, collapsible logs,
#           one-click Panic/Unpanic, MT5 + service controls, auto-refresh.

import os, sys, json, time, math, threading, subprocess
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

def find_repo_root():
    here = Path(__file__).resolve()
    for p in [here.parent, here.parent.parent, here.parent.parent.parent]:
        if (p / "runtime").exists() and (p / "logs").exists():
            return p
    # Last resort to your standard layout
    return Path(r"D:\ChameleFX")

ROOT   = find_repo_root()
RUNTIME= ROOT / "runtime"
LOGS   = ROOT / "logs"
TOOLS  = ROOT / "tools"
APP    = ROOT / "app"

PY     = ROOT / "py-portable" / "python" / "python.exe"
PYW    = ROOT / "py-portable" / "python" / "pythonw.exe"
MT5_EXE= Path(r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe")

# Files we consume
SIG_MAIN          = RUNTIME / "signal.json"
POS_FILE          = RUNTIME / "positions.json"          # produced by positions_writer.py
STATS_FILE        = RUNTIME / "last_stats.json"         # produced by health/stats tools
RISK_LIMITS_FILE  = RUNTIME / "risk_limits.json"        # optional
MUTE_FLAG         = RUNTIME / "mute_trading.flag"
MUTE_MT5_FLAG     = RUNTIME / "mute_mt5.flag"

# Logs we tail
EXEC_LOG_GLOB     = LOGS.glob("**/*executor*.log")
STRAT_LOG_GLOB    = LOGS.glob("**/*.log")  # we’ll filter to keltner/ema_adx/etc later

def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default

def write_text(p, s):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(s, encoding="utf-8")

def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def color_for_pl(v):
    try:
        f = float(v)
    except Exception:
        return ("#111", "#ccc")  # fg, bg
    if f > 0:  return ("#0a0", "#d8f5d0")
    if f < 0:  return ("#a00", "#ffd7d7")
    return ("#333", "#eee")

def color_for_risk_breach(is_breach):
    return ("#fff", "#d9534f") if is_breach else ("#111", "#cde9ff")

def is_process_running(match_substrings):
    try:
        # wmic is present by default on Win; light and no deps
        out = subprocess.check_output(["wmic", "process", "get", "CommandLine"], creationflags=0x08000000)
        text = out.decode("utf-8", errors="ignore").lower()
        return any(s.lower() in text for s in match_substrings)
    except Exception:
        return False

def start_pyw(script):
    try:
        subprocess.Popen([str(PYW), "-u", str(script)], cwd=str(ROOT), creationflags=0x00000008)
    except Exception as e:
        messagebox.showerror("Start error", f"Could not start {script}:\n{e}")

def stop_match(match_words):
    try:
        # tasklist | findstr is simple and ships with Windows
        tl = subprocess.check_output(["tasklist", "/v", "/fo", "csv"], creationflags=0x08000000).decode("utf-8", errors="ignore")
        lines = tl.splitlines()
        pids = []
        for line in lines[1:]:
            # "Image Name","PID","Session Name","Session#","Mem Usage","Status","User Name","CPU Time","Window Title"
            low = line.lower()
            if all(w.lower() in low for w in match_words):
                cols = [c.strip('"') for c in line.split(",")]
                if len(cols) > 2:
                    pids.append(cols[1])
        for pid in pids:
            subprocess.call(["taskkill", "/PID", pid, "/F"], creationflags=0x08000000)
    except Exception:
        pass

def toggle_flag(flag_path, want_present: bool):
    flag_path = Path(flag_path)
    if want_present:
        write_text(flag_path, iso_now()+"\n")
    else:
        try:
            flag_path.unlink(missing_ok=True)
        except Exception:
            pass

def find_latest_log(name_contains):
    newest = None
    newest_mtime = -1
    for p in LOGS.rglob("*.log"):
        low = p.name.lower()
        if any(k in low for k in name_contains):
            try:
                m = p.stat().st_mtime
                if m > newest_mtime:
                    newest_mtime = m
                    newest = p
            except Exception:
                pass
    return newest

def tail_file(path, n=80):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return "(no log)"

# ===== GUI =====
class Manager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ChameleFX Manager")
        self.geometry("1100x760")
        self.configure(bg="#f9fafb")
        try:
            self.iconbitmap(default="")  # harmless if fails
        except Exception:
            pass

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        # Top bar: signal + badges
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        self.lbl_symbol = ttk.Label(top, text="SYMBOL: —", font=("Segoe UI", 14, "bold"))
        self.lbl_action = ttk.Label(top, text="ACTION: —", font=("Segoe UI", 14))
        self.lbl_reason = ttk.Label(top, text="reason: —", font=("Segoe UI", 10))
        self.lbl_ts     = ttk.Label(top, text="ts: —", font=("Segoe UI", 10))

        self.badge_pl   = tk.Label(top, text="P/L: —", font=("Segoe UI", 12, "bold"), padx=10, pady=4)
        self.badge_risk = tk.Label(top, text="RISK: OK", font=("Segoe UI", 12, "bold"), padx=10, pady=4)

        self.lbl_symbol.grid(row=0, column=0, sticky="w", padx=(0,12))
        self.lbl_action.grid(row=0, column=1, sticky="w", padx=(0,12))
        self.badge_pl.grid(  row=0, column=2, sticky="w", padx=(0,12))
        self.badge_risk.grid(row=0, column=3, sticky="w", padx=(0,12))
        self.lbl_reason.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4,0))
        self.lbl_ts.grid(    row=1, column=3, sticky="e", pady=(4,0))

        # Controls
        ctrl = ttk.Frame(self, padding=(10,0,10,10))
        ctrl.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(ctrl, text="Panic (Mute Trading)", command=self.on_panic).pack(side=tk.LEFT, padx=(0,8))
        ttk.Button(ctrl, text="Unmute (Go Live)", command=self.on_unmute).pack(side=tk.LEFT, padx=(0,12))
        ttk.Button(ctrl, text="Restart Services", command=self.on_restart_services).pack(side=tk.LEFT, padx=(0,12))
        ttk.Button(ctrl, text="Open MT5", command=self.on_open_mt5).pack(side=tk.LEFT, padx=(0,12))
        ttk.Button(ctrl, text="Kill MT5", command=self.on_kill_mt5).pack(side=tk.LEFT, padx=(0,12))

        self.lbl_flags = ttk.Label(ctrl, text="flags: —", font=("Consolas", 9))
        self.lbl_flags.pack(side=tk.RIGHT)

        # Positions table
        posf = ttk.LabelFrame(self, text="Open Positions", padding=10)
        posf.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

        cols = ("ticket","symbol","type","volume","price","sl","tp","profit")
        self.pos = ttk.Treeview(posf, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (100,80,70,80,100,100,100,100)):
            self.pos.heading(c, text=c.upper())
            self.pos.column(c, width=w, anchor="center")
        self.pos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(posf, orient="vertical", command=self.pos.yview)
        self.pos.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Collapsible logs
        logf = ttk.LabelFrame(self, text="Logs (collapsible)", padding=10)
        logf.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

        self.log_open = False
        self.btn_toggle = ttk.Button(logf, text="Show logs", command=self.toggle_logs)
        self.btn_toggle.pack(side=tk.TOP, anchor="w")

        self.txt = tk.Text(logf, height=12, bg="#0d1117", fg="#e6edf3", insertbackground="#e6edf3", font=("Consolas", 10))
        self.txt.configure(state=tk.DISABLED)

        # Periodic refresh
        self.after(300, self.refresh_loop)

    # —— Controls ——
    def on_panic(self):
        toggle_flag(MUTE_FLAG, True)
        messagebox.showwarning("Muted", "Trading muted (panic flag present).")

    def on_unmute(self):
        toggle_flag(MUTE_FLAG, False)
        # ensure executor/mux/positions writer are up
        self._ensure_services()
        messagebox.showinfo("Unmuted", "Trading unmuted (go live).")

    def on_restart_services(self):
        self._restart_services()
        messagebox.showinfo("Restarted", "Services restarted.")

    def on_open_mt5(self):
        try:
            subprocess.Popen([str(MT5_EXE)], creationflags=0x00000008)
        except Exception as e:
            messagebox.showerror("MT5", f"Failed to open MT5:\n{e}")

    def on_kill_mt5(self):
        subprocess.call(["taskkill","/IM","terminal64.exe","/F"], creationflags=0x08000000)

    def toggle_logs(self):
        self.log_open = not self.log_open
        if self.log_open:
            self.btn_toggle.configure(text="Hide logs")
            self.txt.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(6,0))
        else:
            self.btn_toggle.configure(text="Show logs")
            self.txt.pack_forget()

    # —— Service helpers ——
    def _restart_services(self):
        # stop current
        stop_match(["pythonw.exe","keltner.py"])
        stop_match(["pythonw.exe","signal_mux.py"])
        stop_match(["pythonw.exe","go_live_executor.py"])
        # start again
        self._ensure_services()

    def _ensure_services(self):
        if not is_process_running(["keltner.py"]):
            start_pyw(APP / "strategies" / "keltner.py")
        if not is_process_running(["signal_mux.py"]):
            start_pyw(TOOLS / "signal_mux.py")
        if not is_process_running(["go_live_executor.py"]):
            start_pyw(TOOLS / "go_live_executor.py")
        if not is_process_running(["positions_writer.py"]):
            start_pyw(TOOLS / "positions_writer.py")

    # —— Loop ——
    def refresh_loop(self):
        try:
            # signal
            sig = read_json(SIG_MAIN, {})
            sym = sig.get("symbol","—")
            act = sig.get("action","—")
            reason = sig.get("reason","—")
            ts  = sig.get("ts","—")
            self.lbl_symbol.configure(text=f"SYMBOL: {sym}")
            self.lbl_action.configure(text=f"ACTION: {act}")
            self.lbl_reason.configure(text=f"reason: {reason}")
            self.lbl_ts.configure(text=f"ts: {ts}")

            # positions and P/L
            total_pl = 0.0
            rows = read_json(POS_FILE, [])
            if isinstance(rows, dict) and "positions" in rows:
                rows = rows["positions"]
            self.pos.delete(*self.pos.get_children())
            for r in rows or []:
                ticket = r.get("ticket","")
                symbol = r.get("symbol","")
                typ    = r.get("type","")
                vol    = r.get("volume",0)
                price  = r.get("price_open") or r.get("price", "")
                sl     = r.get("sl","")
                tp     = r.get("tp","")
                profit = r.get("profit",0.0)
                try:
                    total_pl += float(profit or 0)
                except Exception:
                    pass
                self.pos.insert("", tk.END, values=(ticket,symbol,typ,vol,price,sl,tp,profit))

            fg,bg = color_for_pl(total_pl)
            self.badge_pl.configure(text=f"P/L: {total_pl:.2f}", fg=fg, bg=bg)

            # risk badge
            stats = read_json(STATS_FILE, {}) or {}
            daily_pl = stats.get("daily_pl", total_pl)
            lim = read_json(RISK_LIMITS_FILE, {}) or {}
            dlim = float(lim.get("daily_loss_limit", 0) or 0)
            breach = (dlim > 0 and daily_pl <= -dlim)
            rfg,rbg = color_for_risk_breach(breach)
            self.badge_risk.configure(text=("RISK: BREACH" if breach else "RISK: OK"), fg=rfg, bg=rbg)

            # flags label
            flags = []
            if MUTE_FLAG.exists(): flags.append("mute_trading.flag")
            if MUTE_MT5_FLAG.exists(): flags.append("mute_mt5.flag")
            self.lbl_flags.configure(text=f"flags: {', '.join(flags) if flags else 'none'}")

            # logs (if expanded)
            if self.log_open:
                exec_log = find_latest_log(["executor"])
                strat_log = find_latest_log(["keltner","ema_adx","donch","atr","bbands","rsi_mr"])
                buff = []
                if strat_log:
                    buff.append(f"=== {strat_log)} (tail 60) ===\n{tail_file(strat_log,60)}")
                if exec_log:
                    buff.append(f"\n=== {str(exec_log)} (tail 60) ===\n{tail_file(exec_log,60)}")
                text = "\n".join(buff) if buff else "(no logs)"
                self.txt.configure(state=tk.NORMAL)
                self.txt.delete("1.0", tk.END)
                self.txt.insert("1.0", text)
                self.txt.configure(state=tk.DISABLED)
        except Exception as e:
            # Keep UI alive no matter what
            pass

        # reschedule
        self.after(1500, self.refresh_loop)

if __name__ == "__main__":
    app = Manager()
    # ensure services once at start
    app._ensure_services()
    # if panic flag is present user can unmute in UI; else we’re live
    app.mainloop()
