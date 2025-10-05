# chamelefx/setup_gui.py
import tkinter as tk
from tkinter import ttk, messagebox
import json, os, time, threading, subprocess, requests, sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CFX_DIR = os.path.join(ROOT, "chamelefx")
CONFIG_PATH = os.path.join(CFX_DIR, "config.json")
LOGS_DIR = os.path.join(ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

DEFAULTS = {
    "api": {"host": "127.0.0.1", "port": 18123},
    "broker": {"terminal": r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe", "account": "", "password": null, "server": ""},
    "fcs": {"key": ""},
    "trading": {"auto": True, "profile": "moderate"},
    "guardrails": {"risk_per_trade_pct": 1.0, "daily_max_loss_pct": 3.0, "min_rr": 1.5, "max_open_positions": 2, "max_correlated": 1},
}

def _log(msg: str):
    try:
        with open(os.path.join(LOGS_DIR, "setup_gui.log"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

class SetupGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ChameleFX Setup")
        self.state = json.loads(json.dumps(DEFAULTS))  # deep copy
        self._build()
        self._load_existing()

    def _build(self):
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=10, pady=10)

        # API
        api = ttk.LabelFrame(frm, text="API"); api.pack(fill="x", pady=6)
        self.api_host = tk.StringVar(value=self.state["api"]["host"])
        self.api_port = tk.StringVar(value=str(self.state["api"]["port"]))
        ttk.Label(api, text="Host").grid(row=0, column=0, sticky="w"); ttk.Entry(api, textvariable=self.api_host, width=20).grid(row=0, column=1)
        ttk.Label(api, text="Port").grid(row=0, column=2, sticky="w"); ttk.Entry(api, textvariable=self.api_port, width=8).grid(row=0, column=3)

        # Broker
        br = ttk.LabelFrame(frm, text="Broker (MT5)"); br.pack(fill="x", pady=6)
        self.br_term = tk.StringVar(value=self.state["broker"]["terminal"])
        self.br_acct = tk.StringVar(value=self.state["broker"]["account"])
        self.br_pass = tk.StringVar(value=self.state["broker"]["password"])
        self.br_srv  = tk.StringVar(value=self.state["broker"]["server"])
        ttk.Label(br, text="Terminal Path").grid(row=0, column=0, sticky="w"); ttk.Entry(br, textvariable=self.br_term, width=60).grid(row=0, column=1, columnspan=3, sticky="we")
        ttk.Label(br, text="Account").grid(row=1, column=0, sticky="w"); ttk.Entry(br, textvariable=self.br_acct, width=20).grid(row=1, column=1)
        ttk.Label(br, text="Password").grid(row=1, column=2, sticky="w"); ttk.Entry(br, textvariable=self.br_pass, show="*", width=20).grid(row=1, column=3)
        ttk.Label(br, text="Server").grid(row=2, column=0, sticky="w"); ttk.Entry(br, textvariable=self.br_srv, width=20).grid(row=2, column=1)

        # FCS
        fcs = ttk.LabelFrame(frm, text="FCS"); fcs.pack(fill="x", pady=6)
        self.fcs_key = tk.StringVar(value=self.state["fcs"]["key"])
        ttk.Label(fcs, text="API Key").grid(row=0, column=0, sticky="w"); ttk.Entry(fcs, textvariable=self.fcs_key, width=40).grid(row=0, column=1)

        # Trading
        tr = ttk.LabelFrame(frm, text="Trading"); tr.pack(fill="x", pady=6)
        self.tr_auto = tk.BooleanVar(value=self.state["trading"]["auto"])
        self.tr_prof = tk.StringVar(value=self.state["trading"]["profile"])
        ttk.Checkbutton(tr, text="Auto", variable=self.tr_auto).grid(row=0, column=0, sticky="w")
        ttk.Label(tr, text="Profile").grid(row=0, column=1, sticky="w")
        ttk.Combobox(tr, textvariable=self.tr_prof, values=["conservative","moderate","aggressive"], width=14).grid(row=0, column=2)

        # Guardrails
        gr = ttk.LabelFrame(frm, text="Guardrails"); gr.pack(fill="x", pady=6)
        self.gr_rpt  = tk.StringVar(value=str(self.state["guardrails"]["risk_per_trade_pct"]))
        self.gr_dml  = tk.StringVar(value=str(self.state["guardrails"]["daily_max_loss_pct"]))
        self.gr_mrr  = tk.StringVar(value=str(self.state["guardrails"]["min_rr"]))
        self.gr_mop  = tk.StringVar(value=str(self.state["guardrails"]["max_open_positions"]))
        self.gr_mco  = tk.StringVar(value=str(self.state["guardrails"]["max_correlated"]))
        row=0
        for lbl, var in [("Risk %/trade", self.gr_rpt), ("Daily max loss %", self.gr_dml), ("Min RR", self.gr_mrr), ("Max open pos", self.gr_mop), ("Max correlated", self.gr_mco)]:
            ttk.Label(gr, text=lbl).grid(row=row//3, column=(row%3)*2, sticky="w", pady=2)
            ttk.Entry(gr, textvariable=var, width=10).grid(row=row//3, column=(row%3)*2+1, sticky="w", pady=2)
            row += 1

        # Footer
        footer = ttk.Frame(frm); footer.pack(fill="x", pady=10)
        self._status = tk.Label(footer, text="Ready.")
        self._status.pack(side="left")
        ttk.Button(footer, text="Save & Close", command=self._save_and_launch).pack(side="right")

    def _load_existing(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.api_host.set(cfg.get("api", {}).get("host", self.api_host.get()))
            self.api_port.set(str(cfg.get("api", {}).get("port", self.api_port.get())))
            self.br_term.set(cfg.get("broker", {}).get("terminal", self.br_term.get()))
            self.br_acct.set(cfg.get("broker", {}).get("account", self.br_acct.get()))
            self.br_pass.set(cfg.get("broker", {}).get("password", self.br_pass.get()))
            self.br_srv.set(cfg.get("broker", {}).get("server", self.br_srv.get()))
            self.fcs_key.set(cfg.get("fcs", {}).get("key", self.fcs_key.get()))
            tr = cfg.get("trading", {})
            self.tr_auto.set(bool(tr.get("auto", self.tr_auto.get())))
            self.tr_prof.set(tr.get("profile", self.tr_prof.get()))
            gr = cfg.get("guardrails", {})
            self.gr_rpt.set(str(gr.get("risk_per_trade_pct", self.gr_rpt.get())))
            self.gr_dml.set(str(gr.get("daily_max_loss_pct", self.gr_dml.get())))
            self.gr_mrr.set(str(gr.get("min_rr", self.gr_mrr.get())))
            self.gr_mop.set(str(gr.get("max_open_positions", self.gr_mop.get())))
            self.gr_mco.set(str(gr.get("max_correlated", self.gr_mco.get())))
        except Exception:
            pass

    def _save_and_launch(self):
        cfg = {
            "api": {"host": self.api_host.get().strip(), "port": int(self.api_port.get().strip() or "8088")},
            "broker": {"terminal": self.br_term.get().strip(), "account": self.br_acct.get().strip(),
                       "password": null, "server": self.br_srv.get().strip()},
            "fcs": {"key": self.fcs_key.get().strip()},
            "trading": {"auto": bool(self.tr_auto.get()), "profile": self.tr_prof.get().strip().lower()},
            "guardrails": {"risk_per_trade_pct": float(self.gr_rpt.get()), "daily_max_loss_pct": float(self.gr_dml.get()),
                           "min_rr": float(self.gr_mrr.get()), "max_open_positions": int(self.gr_mop.get()),
                           "max_correlated": int(self.gr_mco.get())},
        }
        os.makedirs(CFX_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        self._status.config(text="Starting services…")
        threading.Thread(target=self._start_and_launch_manager, daemon=True).start()

    # ----------------- launching background services -----------------
    def _start_api(self, host: str, port: int):
        """Start FastAPI via our programmatic launcher (stable import paths)."""
        py = sys.executable
        cwd = ROOT
        api_out = open(os.path.join(LOGS_DIR, "api_stdout.log"), "a", encoding="utf-8")
        api_err = open(os.path.join(LOGS_DIR, "api_stderr.log"), "a", encoding="utf-8")
        launcher = os.path.join(ROOT, "app", "api", "launch_api.py")
        cmd = [py, "-u", launcher, host, str(port)]
        subprocess.Popen(cmd, cwd=cwd, stdout=api_out, stderr=api_err)

    def _start_mt5_terminal(self, terminal_path: str):
        """Launch MT5 terminal (best-effort). It may already be running — that's fine."""
        try:
            if terminal_path and os.path.exists(terminal_path):
                subprocess.Popen([terminal_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                _log(f"MT5 terminal started: {terminal_path}")
            else:
                _log("MT5 terminal path missing or not found; skipping launch.")
        except Exception as e:
            _log(f"MT5 terminal launch error: {e}")

    def _wait_health(self, base: str, want_mt5_ok=True, max_sec=12) -> bool:
        """Poll /health/detail until API is up (and MT5 ok if requested)."""
        until = time.time() + max_sec
        last = None
        while time.time() < until:
            try:
                r = requests.get(base + "/health/detail", timeout=1.25)
                if r.ok:
                    j = r.json()
                    last = j
                    if not want_mt5_ok:
                        return True
                    if (j.get("mt5") or {}).get("ok"):
                        return True
            except Exception:
                pass
            time.sleep(1.0)
        # one last snapshot for logs
        _log(f"Health wait timeout. Last payload: {last}")
        return False

    def _start_and_launch_manager(self):
        # Read fresh config
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            messagebox.showerror("Config error", str(e))
            return

        host = cfg.get("api", {}).get("host", "127.0.0.1")
        port = int(cfg.get("api", {}).get("port", 8088))
        base = f"http://{host}:{port}"
        terminal = (cfg.get("broker") or {}).get("terminal", "")

        # 1) Start MT5 terminal (best-effort)
        self._start_mt5_terminal(terminal)

        # 2) Start API server
        self._start_api(host, port)

        # 3) Countdown UI while waiting for API+MT5
        for t in range(8, 0, -1):
            self._status.config(text=f"Bringing services up… {t}")
            time.sleep(1)

        ready = self._wait_health(base, want_mt5_ok=True, max_sec=12)
        if not ready:
            # Still proceed — Manager can show LEDs and user can diagnose with logs
            self._status.config(text="Services not fully up yet, opening Manager…")
        else:
            self._status.config(text="Services up. Opening Manager…")

        # 4) Launch Manager (with logs)
        try:
            py = sys.executable
            mgr_path = os.path.join(CFX_DIR, "manager.py")
            mgr_out = open(os.path.join(LOGS_DIR, "manager_stdout.log"), "a", encoding="utf-8")
            mgr_err = open(os.path.join(LOGS_DIR, "manager_stderr.log"), "a", encoding="utf-8")
            subprocess.Popen([py, "-u", mgr_path], stdout=mgr_out, stderr=mgr_err)
        except Exception as e:
            messagebox.showerror("Launch error", str(e))
        finally:
            self.after(300, self.destroy)

def main():
    app = SetupGUI()
    app.mainloop()

if __name__ == "__main__":
    main()# >>> CFX-BATCH9:COUNTDOWN (do not remove)
def _cfx_countdown_then_launch(seconds=5, launch_cmd=None):
    try:
        import tkinter as tk, subprocess, sys, os
        root = tk.Toplevel() if isinstance(globals().get('root'), tk.Tk) else tk.Tk()
        root.title("ChameleFX — Preparing Manager")
        lbl = tk.Label(root, text=f"Starting Manager in {seconds}s...", font=("Segoe UI", 12))
        lbl.pack(padx=20, pady=20)
        def tick(n=seconds):
            lbl.config(text=f"Starting Manager in {n}s...")
            if n <= 0:
                root.destroy()
                if launch_cmd:
                    try:
                        subprocess.Popen(launch_cmd, shell=True)
                    except Exception:
                        pass
                return
            root.after(1000, lambda: tick(n-1))
        tick(seconds)
        root.mainloop()
    except Exception as _e:
        pass
# <<< CFX-BATCH9:COUNTDOWN
# >>> CFX-BATCH9:LAUNCHER (do not remove)
def _cfx_spawn_manager_direct():
    import subprocess, sys, time
    logp = os.path.join(os.path.dirname(__file__), "setup_gui.log")
    proj = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    portable = os.path.join(proj, "py-portable", "python", "python.exe")
    py = portable if os.path.exists(portable) else (sys.executable or "python")
    mgr = os.path.join(os.path.dirname(__file__), "manager.py")

    def _log(msg: str):
        try:
            with open(logp, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    try:
        # Start minimized (Windows) with correct working directory (proj)
        si = None
        creationflags = 0
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # 7 = SW_SHOWMINNOACTIVE (minimized, no focus)
            si.wShowWindow = 7
            creationflags = 0  # could also use subprocess.CREATE_NEW_CONSOLE

        cmd = [py, mgr]
        _log(f"[CFX] direct spawn: {cmd} cwd={proj}")
        subprocess.Popen(cmd, cwd=proj, startupinfo=si, creationflags=creationflags, shell=False)
        return True
    except Exception as e:
        _log(f"[CFX] direct spawn failed: {e!r}")
        return False

def _cfx_countdown_then_launch(seconds=5, launch_cmd=None):
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title("ChameleFX — Preparing Manager")
        lbl = tk.Label(root, text=f"Starting Manager in {seconds}s...", font=("Segoe UI", 12))
        lbl.pack(padx=20, pady=20)
        def tick(n=seconds):
            lbl.config(text=f"Starting Manager in {n}s...")
            if n <= 0:
                root.destroy()
                _cfx_spawn_manager_direct()
                return
            root.after(1000, lambda: tick(n-1))
        tick(seconds)
        root.mainloop()
    except Exception:
        _cfx_spawn_manager_direct()

def _cfx_launch_now(countdown=5):
    _cfx_countdown_then_launch(seconds=countdown, launch_cmd=None)

if __name__ == "__main__":
    _cfx_launch_now(countdown=3)
# <<< CFX-BATCH9:LAUNCHER
