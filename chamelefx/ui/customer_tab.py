from __future__ import annotations
from chamelefx.log import get_logger
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict
import requests, json

API_URL = "http://127.0.0.1:18124"

class CustomerTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.kpi_frame = ttk.LabelFrame(self, text="Performance KPIs")
        self.kpi_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_equity = ttk.Label(self.kpi_frame, text="Equity: --")
        self.lbl_equity.pack(side="left", padx=10)
        self.lbl_sharpe = ttk.Label(self.kpi_frame, text="Sharpe: --")
        self.lbl_sharpe.pack(side="left", padx=10)
        self.lbl_dd = ttk.Label(self.kpi_frame, text="Max DD: --")
        self.lbl_dd.pack(side="left", padx=10)
        self.lbl_wr = ttk.Label(self.kpi_frame, text="Win Rate: --")
        self.lbl_wr.pack(side="left", padx=10)
        self.lbl_exp = ttk.Label(self.kpi_frame, text="Expectancy: --")
        self.lbl_exp.pack(side="left", padx=10)

        self.health_frame = ttk.LabelFrame(self, text="Alpha Health")
        self.health_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_decay = ttk.Label(self.health_frame, text="Decay: --")
        self.lbl_decay.pack(side="left", padx=10)
        self.lbl_drift = ttk.Label(self.health_frame, text="Drift: --")
        self.lbl_drift.pack(side="left", padx=10)

        self.attrib_frame = ttk.LabelFrame(self, text="Attribution")
        self.attrib_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_top = ttk.Label(self.attrib_frame, text="Top3: --")
        self.lbl_top.pack(side="left", padx=10)
        self.lbl_bottom = ttk.Label(self.attrib_frame, text="Bottom3: --")
        self.lbl_bottom.pack(side="left", padx=10)

        self.exec_frame = ttk.LabelFrame(self, text="Execution")
        self.exec_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_slip = ttk.Label(self.exec_frame, text="Slippage: --")
        self.lbl_slip.pack(side="left", padx=10)
        self.lbl_venue = ttk.Label(self.exec_frame, text="Venues: --")
        self.lbl_venue.pack(side="left", padx=10)

        self.port_frame = ttk.LabelFrame(self, text="Portfolio")
        self.port_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_driftp = ttk.Label(self.port_frame, text="Drift: --")
        self.lbl_driftp.pack(side="left", padx=10)
        self.btn_reb = ttk.Button(self.port_frame, text="Rebalance Now", command=self._rebalance)
        self.btn_reb.pack(side="left", padx=10)

        self.after(4000, self.refresh)

    def refresh(self):
        try:
            r = requests.get(f"{API_URL}/customer/metrics", timeout=2)
            if r.ok:
                d = r.json()
                self.lbl_equity.config(text=f"Equity: {d.get('equity')}")
                self.lbl_sharpe.config(text=f"Sharpe: {d.get('sharpe'):.2f}")
                self.lbl_dd.config(text=f"Max DD: {d.get('max_dd'):.2f}")
                self.lbl_wr.config(text=f"WinRate: {d.get('win_rate'):.2f}")
                self.lbl_exp.config(text=f"Exp: {d.get('expectancy'):.2f}")
                self.lbl_decay.config(text=f"Decay: {d.get('decay')}")
                self.lbl_drift.config(text=f"Drift: {d.get('drift')}")
                self.lbl_top.config(text=f"Top3: {','.join(d.get('top3',[]))}")
                self.lbl_bottom.config(text=f"Bottom3: {','.join(d.get('bottom3',[]))}")
                self.lbl_slip.config(text=f"Slippage: {d.get('slippage_bps')}")
                self.lbl_venue.config(text=f"Venues: {d.get('venue_status')}")
                self.lbl_driftp.config(text=f"Drift: {d.get('portfolio_drift')}")
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
        self.after(4000, self.refresh)

    def _rebalance(self):
        try:
            requests.post(f"{API_URL}/portfolio/rebalance", timeout=5.0)
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
