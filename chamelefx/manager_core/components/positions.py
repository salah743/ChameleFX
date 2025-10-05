
import threading, time
from tkinter import ttk

class Component:
    __component_name__ = "positions"
    def __init__(self, manager):
        self.m = manager; self._alive = True; self.rows = []
        self._t = threading.Thread(target=self._poll, daemon=True)
    def attach(self, manager): pass
    def mount(self, manager):
        parent = manager.frames["grid"]["positions"]
        box = ttk.LabelFrame(parent, text="Alpha (demo)"); box.pack(fill="both", expand=True, pady=6)
        self.table = manager.ui.make_table(box, ["Key","Value"]); self._t.start()
    def refresh(self, now): self.table.update_rows(self.rows)
    def shutdown(self): self._alive = False
    def _poll(self):
        while self._alive:
            try:
                res = self.m.api.post('/alpha/features/compute', {'symbol':'EURUSD'})
                if isinstance(res, dict): self.rows = [[k,str(v)] for k,v in res.items() if k in ('ok','symbol','meta')]
            except Exception: pass
            time.sleep(1.5)
