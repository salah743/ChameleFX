from __future__ import annotations
from chamelefx.log import get_logger
import tkinter as tk
from tkinter import ttk, messagebox
import threading, json
import requests

API_DEFAULT = "http://127.0.0.1:18124"

class PortfolioTab(tk.Frame):
    """
    Clean & safe Portfolio tab:
     - symbol list entry (comma separated)
     - method dropdown (risk_parity / equal / meanvar stub)
     - Optimize -> fills table with weights
     - Apply -> POST to /portfolio/apply (optional endpoint; errors ignored)
    """

    def __init__(self, master=None, api_base: str = API_DEFAULT):
        super().__init__(master)
        self.api_base = api_base or API_DEFAULT

        # Controls row
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        tk.Label(top, text="Symbols (comma separated):").pack(side="left")
        self.e_symbols = tk.Entry(top, width=40)
        self.e_symbols.insert(0, "EURUSD,GBPUSD,XAUUSD")
        self.e_symbols.pack(side="left", padx=6)

        tk.Label(top, text="Method:").pack(side="left", padx=(8,2))
        self.cb_method = ttk.Combobox(top, values=["risk_parity","equal","meanvar"], width=14, state="readonly")
        self.cb_method.set("risk_parity")
        self.cb_method.pack(side="left")

        tk.Button(top, text="Optimize", command=self.on_optimize).pack(side="left", padx=8)
        tk.Button(top, text="Apply", command=self.on_apply).pack(side="left")

        # Table
        mid = tk.Frame(self)
        mid.pack(fill="both", expand=True, padx=10, pady=(4,10))
        cols = ("symbol","weight")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (220,120)):
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=w, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # Status
        self.status = tk.Label(self, text="", anchor="w")
        self.status.pack(fill="x", padx=10, pady=(0,8))

        # Data
        self.last_weights = {}

    def set_status(self, msg: str):
        try:
            self.status.config(text=msg)
        except Exception:
    get_logger(__name__).exception('Unhandled exception')

    def _parse_symbols(self) -> list[str]:
        txt = self.e_symbols.get().strip()
        if not txt:
            return []
        # split by comma / whitespace
        parts = [p.strip().upper() for p in txt.replace(";", ",").split(",")]
        parts = [p for p in parts if p]
        # dedupe preserve order
        out = []
        for p in parts:
            if p not in out:
                out.append(p)
        return out

    def on_optimize(self):
        sy = self._parse_symbols()
        method = self.cb_method.get().strip() or "risk_parity"
        if not sy:
            messagebox.showwarning("Portfolio", "Please enter one or more symbols.")
            return

        def work():
            self.set_status("Optimizing...")
            try:
                j = requests.post(
                    self.api_base + "/portfolio/optimize",
                    json={"method": method, "symbols": sy},
                    timeout=5.0,
                ).json()
            except Exception as e:
                self.set_status("Optimize error")
                messagebox.showerror("Portfolio", f"Optimize error:\n{e!r}")
                return

            if not isinstance(j, dict) or not j.get("ok"):
                self.set_status("Optimize failed")
                messagebox.showerror("Portfolio", f"Optimize failed:\n{json.dumps(j, indent=2)}")
                return

            w = j.get("weights") or {}
            self._fill_table(w)
            self.last_weights = w
            self.set_status("Optimized")

        threading.Thread(target=work, daemon=True).start()

    def _fill_table(self, weights: dict):
        try:
            for r in self.tree.get_children():
                self.tree.delete(r)
            # show sorted by symbol
            for sym in sorted(weights.keys()):
                try:
                    val = float(weights.get(sym, 0.0))
                except Exception:
                    val = 0.0
                self.tree.insert("", "end", values=(sym, f"{val:.4f}"))
        except Exception:
    get_logger(__name__).exception('Unhandled exception')

    def on_apply(self):
        if not self.last_weights:
            messagebox.showinfo("Portfolio", "No weights to apply. Run Optimize first.")
            return

        def work():
            self.set_status("Applying...")
            payload = {"weights": self.last_weights}
            try:
                # Not all stacks have /portfolio/apply; ignore if missing
                r = requests.post(self.api_base + "/portfolio/apply", json=payload, timeout=5.0)
                ok = (r.status_code == 200)
                j = r.json() if ok else {}
            except Exception:
                ok = False
                j = {}

            if ok and isinstance(j, dict) and j.get("ok"):
                self.set_status("Applied")
            else:
                # Soft-fail; we at least built the weights
                self.set_status("Apply endpoint not available (weights built)")
                # No popup to avoid blocking the user

# end PortfolioTab


    def optimize_now(self):
        try:
            base = self._base() if hasattr(self, "_base") else "http://127.0.0.1:18124"
            syms = [self.tree.item(iid)["values"][0] for iid in self.tree.get_children()]
            if not syms:
                return
            # BATCH61_RET_HOOK — fetch aligned returns from CSV history
            jr = requests.post(base + "/portfolio/returns", json={"symbols": syms, "csv_dir": "data/history", "lookback": 250}, timeout=8).json()
            if not jr.get("ok"):
                print("returns error", jr)
                return
            rets = jr.get("returns", [])
            sy_used = jr.get("symbols", syms)
            # Optimize (default meanvar; you can add dropdown to pick method)
            jopt = requests.post(base + "/portfolio/optimize", json={"symbols": sy_used, "returns": rets, "method": "meanvar"}, timeout=8).json()
            if jopt.get("ok"):
                for s,w in jopt["weights"].items():
                    for iid in self.tree.get_children():
                        vals = list(self.tree.item(iid)["values"])
                        if vals and vals[0]==s:
                            vals[1]=f"{w:.3f}"
                            self.tree.item(iid, values=vals)
        except Exception as e:
            print("optimize_now error", e)
