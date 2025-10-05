
import threading, time
from tkinter import ttk

class Component:
    __component_name__ = "connectivity"
    __requires_api__ = ">=1.0,<2.0"
    def __init__(self, manager):
        self.m = manager; self._alive = True
        self.last = {"health": None, "mt5": None}
        self._t = threading.Thread(target=self._poll, daemon=True)

    def attach(self, manager): pass
    def mount(self, manager):
        parent = manager.frames["grid"]["connectivity"]
        box = ttk.LabelFrame(parent, text="Connectivity"); box.pack(fill="x", pady=6)
        self.lbl_h = ttk.Label(box, text="API: …"); self.lbl_h.pack(anchor="w", padx=6, pady=2)
        self.lbl_m = ttk.Label(box, text="MT5: …"); self.lbl_m.pack(anchor="w", padx=6, pady=2)
        btns = ttk.Frame(box); btns.pack(anchor="w", padx=6, pady=4)
        ttk.Button(btns, text="MT5 Heartbeat", command=self._heartbeat).pack(side="left", padx=2)
        ttk.Button(btns, text="Reconnect", command=self._reconnect).pack(side="left", padx=2)
        self._t.start()
    def refresh(self, now):
        h = self.last.get("health"); m = self.last.get("mt5")
        self.lbl_h.config(text=f"API: {'UP' if h else 'DOWN'}")
        if isinstance(m, dict):
            self.lbl_m.config(text=f"MT5: login={'yes' if m.get('mt5',{}).get('login') else 'no'} server={'yes' if m.get('mt5',{}).get('server') else 'no'}")
        elif m is False: self.lbl_m.config(text="MT5: DOWN")
        else: self.lbl_m.config(text="MT5: …")
    def shutdown(self): self._alive = False
    def _poll(self):
        while self._alive:
            try: self.last['health'] = bool(self.m.api.get('/health').get('ok'))
            except Exception: self.last['health'] = False
            time.sleep(1.2)
    def _heartbeat(self):
        try: self.last['mt5'] = self.m.api.get('/mt5/status')
        except Exception: self.last['mt5'] = False
    def _reconnect(self):
        try: self.m.api.post('/mt5/reconnect', {})
        except Exception: pass
