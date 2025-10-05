
from pathlib import Path
import re
from patchlib import project_root, backup_write

ROOT = project_root(Path(__file__))

# Remove BOM in setup_gui.py
sg = ROOT / "chamelefx/setup_gui.py"
if sg.exists():
    raw = sg.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        sg.write_bytes(raw.lstrip(b'\xef\xbb\xbf'))
        print("[OK] removed BOM from setup_gui.py")
    else:
        print("[SKIP] setup_gui.py has no BOM")

# Repair AlphaTab.weight_from_signal
at = ROOT / "chamelefx/ui/alpha_tab.py"
if not at.exists():
    print(f"[WARN] {at} not found")
else:
    txt = at.read_text(encoding="utf-8")
    m = re.search(r"""def\s+weight_from_signal\s*\(self\)\s*:\s*(?:.|\n)*?(?=\n\s{4}def\s+\w+\(|\Z)""", txt, re.S)
    if not m:
        print("[WARN] weight_from_signal method not found; skipping")
    else:
        new_block = '''
    def weight_from_signal(self):
        try:
            import requests
        except Exception:
            return
        sym = self._selected_symbol() if hasattr(self, '_selected_symbol') else 'EURUSD'
        try:
            w = float(self.e_weight.get() or 0.25)
        except Exception:
            w = 0.25
        try:
            pr = requests.post(self._base() + "/sizing/regime/preview", json={"symbol": sym, "weight": w}, timeout=3.0).json()
            lots = pr.get("lots", None)
            if lots is not None and hasattr(self, 'e_lots_auto'):
                self.e_lots_auto.configure(state='normal')
                self.e_lots_auto.delete(0, 'end')
                self.e_lots_auto.insert(0, f"{float(lots):.2f}")
                self.e_lots_auto.configure(state='readonly')
        except Exception:
            pass
'''.lstrip("\n")
        new_txt = txt[:m.start()] + new_block + txt[m.end():]
        if new_txt != txt:
            backup_write(at, new_txt)
            print("[OK] repaired AlphaTab.weight_from_signal")
        else:
            print("[SKIP] AlphaTab already healthy")
