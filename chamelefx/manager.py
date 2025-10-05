$mp = ".\chamelefx\manager.py"
Copy-Item $mp "$mp.bak" -Force 2>$null

@'
import importlib, pkgutil, time, json, urllib.request, urllib.error
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional
import tkinter as tk
from tkinter import ttk

try:
    from chamelefx.log import get_logger
except Exception:
    import logging
    def get_logger(name): return logging.getLogger(name)

class EventBus:
    def __init__(self):
        self._subs: Dict[str, List[Callable[[str, dict], None]]] = {}
    def subscribe(self, topic: str, fn: Callable[[str, dict], None]):
        self._subs.setdefault(topic, []).append(fn)
    def publish(self, topic: str, payload: dict):
        for fn in list(self._subs.get(topic, [])):
            try: fn(topic, payload)
            except Exception: pass

class ApiClient:
    def __init__(self, base: str, timeout: float = 5.0):
        self.base = base.rstrip("/"); self.timeout = timeout
    def _req(self, method: str, path: str, data: Optional[dict] = None) -> dict:
        url = self.base + (path if path.startswith("/") else "/" + path)
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try: return json.loads(e.read().decode("utf-8"))
            except Exception: return {"ok": False, "status": e.code, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    def get(self, path: str) -> dict:  return self._req("GET", path)
    def post(self, path: str, data: dict) -> dict: return self._req("POST", path, data)

class UIHelpers:
    def __init__(self, root: tk.Tk): self.root = root
    def make_led(self, parent, size=12, color="grey"):
        c = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bg=parent.cget("background"))
        o = c.create_oval(1,1,size-1,size-1, fill=color, outline=""); c._oval = o
        def set_color(col): c.itemconfigure(o, fill=col)
        c.set_color = set_color; return c
    def make_table(self, parent, columns: List[str]):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)
        for c in columns: tree.heading(c, text=c); tree.column(c, width=100, anchor="center")
        tree.pack(fill="both", expand=True)
        def update_rows(rows):
            tree.delete(*tree.get_children())
            if rows and isinstance(rows[0], dict):
                for r in rows: tree.insert("", "end", values=[r.get(c,"") for c in columns])
            else:
                for r in rows: tree.insert("", "end", values=r)
        tree.update_rows = update_rows; return tree

class Manager:
    def __init__(self):
        self.root = tk.Tk(); self.root.title("ChameleFX — Manager"); self.root.geometry("980x640")
        self.logger = get_logger("manager")
        self.root_dir = Path(__file__).resolve().parents[1]
        cfg = self._load_config()
        base = cfg.get("api",{}).get("base") or "http://127.0.0.1:18124"
        self.api = ApiClient(base)
        self.event_bus = EventBus()
        self.ui = UIHelpers(self.root)
        self.frames = self._build_frames()
        self.components: List[Any] = []
        self._load_components()
        self.refresh_ms = 800
        self.root.after(self.refresh_ms, self._refresh_loop)

    def _load_config(self)->dict:
        p = self.root_dir / "config.json"
        try: return json.loads(p.read_text(encoding="utf-8"))
        except Exception: return {"api":{"base":"http://127.0.0.1:18124"}}

    def _build_frames(self):
        top = ttk.Frame(self.root, padding=8); top.pack(side="top", fill="x")
        grid = ttk.Frame(self.root, padding=8); grid.pack(side="top", fill="both", expand=True)
        ttk.Label(top, text="ChameleFX Manager", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.led_api = self.ui.make_led(top); self.led_api.pack(side="left", padx=8)
        self.lbl_api = ttk.Label(top, text="API: …"); self.lbl_api.pack(side="left")
        left = ttk.Frame(grid); left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(grid); right.pack(side="left", fill="both", expand=True)
        return {"header": top, "grid": {"connectivity": left, "positions": right}, "left": left, "right": right}

    def _discover_modules(self) -> List[str]:
        """Prefer new chamelefx.manager_core.components; fallback to legacy Manager_Components."""
        import sys
        mods: List[str] = []

        # NEW canonical path
        new_dir = self.root_dir / "chamelefx" / "manager_core" / "components"
        new_pkg = "chamelefx.manager_core.components"
        (new_dir.parent / "__init__.py").write_text("", encoding="utf-8")  # manager_core
        (new_dir / "__init__.py").write_text("", encoding="utf-8")        # components
        if str(self.root_dir) not in sys.path:
            sys.path.insert(0, str(self.root_dir))
        if new_dir.exists():
            for _, modname, ispkg in pkgutil.iter_modules([str(new_dir)]):
                if not ispkg and not modname.startswith("_"):
                    mods.append(f"{new_pkg}.{modname}")

        # LEGACY fallback
        legacy_dir = self.root_dir / "Manager_Components"
        if legacy_dir.exists():
            (legacy_dir / "__init__.py").write_text("", encoding="utf-8")
            for _, modname, ispkg in pkgutil.iter_modules([str(legacy_dir)]):
                if not ispkg and not modname.startswith("_"):
                    mods.append(f"Manager_Components.{modname}")

        return mods

    def _load_components(self):
        for module_path in self._discover_modules():
            try:
                mod = importlib.import_module(module_path)
                comp = mod.register(self) if hasattr(mod,"register") else (mod.Component(self) if hasattr(mod,"Component") else None)
                if comp and hasattr(comp,"attach"): comp.attach(self)
                if comp and hasattr(comp,"mount"):  comp.mount(self)
                if comp: self.components.append(comp)
                self.logger.info("Loaded %s", module_path)
            except Exception as e:
                self.logger.exception("component_load_error")
                print(f"[Manager] NOT loaded {module_path}: {e!r}")

    def _refresh_loop(self):
        try:
            h = self.api.get("/health")
            ok = bool(h.get("ok"))
            self.led_api.set_color("lime" if ok else "red")
            self.lbl_api.config(text=f"API: {'UP' if ok else 'DOWN'}")
        except Exception:
            self.led_api.set_color("red"); self.lbl_api.config(text="API: DOWN")

        now = time.monotonic()
        for c in list(self.components):
            try: c.refresh(now)
            except Exception: self.logger.exception("component_refresh_error")

        self.root.after(self.refresh_ms, self._refresh_loop)

def main():
    m = Manager()
    m.root.mainloop()

if __name__ == "__main__":
    main()
'@ | Set-Content $mp -Encoding UTF8

# quick syntax check
.\py-portable\python\python.exe -c "import py_compile; py_compile.compile(r'chamelefx\manager.py', doraise=True)"
Write-Host "[OK] manager.py patched for chamelefx.manager_core.components"
