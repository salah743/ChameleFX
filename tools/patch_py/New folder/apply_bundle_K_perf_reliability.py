# tools/patch_py/apply_bundle_K_perf_reliability.py
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app" / "api"
CFX = ROOT / "chamelefx"

def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")
    print("[K] wrote", path)

# ----- utils: TTL cache -----
TTL = r"""
from __future__ import annotations
import time
from typing import Any, Callable, Tuple, Dict

class TTLCache:
    def __init__(self, ttl_seconds: float = 2.0, max_items: int = 512):
        self.ttl = float(ttl_seconds)
        self.max = int(max_items)
        self._d: Dict[Any, Tuple[float, Any]] = {}

    def get(self, key: Any, fn: Callable[[], Any]):
        now = time.time()
        v = self._d.get(key)
        if v is not None:
            ts, val = v
            if (now - ts) <= self.ttl:
                return val
        val = fn()
        if len(self._d) >= self.max:
            self._d.clear()
        self._d[key] = (now, val)
        return val
"""

# ----- middleware: global concurrency + per-path rate limit + sequentializer -----
MW = r"""
from __future__ import annotations
import asyncio, time
from typing import Callable, Awaitable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class Gatekeeper(BaseHTTPMiddleware):
    def __init__(self, app, global_limit: int = 8, per_path_qps: float = 8.0, sequential_paths: tuple[str,...]=()):
        super().__init__(app)
        self.sem = asyncio.Semaphore(max(1, int(global_limit)))
        self.qps = max(0.5, float(per_path_qps))
        self.sequential = set(sequential_paths or ())
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._errors = 0

    @property
    def error_count(self) -> int:
        return self._errors

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        path = request.url.path
        # simple per-path QPS
        now = time.time()
        last = self._last.get(path, 0.0)
        min_gap = 1.0 / self.qps
        if (now - last) < min_gap:
            await asyncio.sleep(min_gap - (now - last))
        self._last[path] = time.time()

        # sequentialize selected heavy endpoints
        lock: asyncio.Lock | None = None
        for p in self.sequential:
            if path.startswith(p):
                lock = self._locks.setdefault(p, asyncio.Lock())
                break

        try:
            async with self.sem:
                if lock:
                    async with lock:
                        return await call_next(request)
                else:
                    return await call_next(request)
        except Exception:
            self._errors += 1
            raise
"""

# ----- debug/health router -----
HEALTH = r"""
from __future__ import annotations
from fastapi import APIRouter
from pathlib import Path
import importlib

router = APIRouter()

def _is_mounted(mod: str, alias: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False

@router.get("/debug/health_deep")
def health_deep():
    base = Path(__file__).resolve().parents[2] / "chamelefx" / "runtime"
    files = {
        "account.json": (base / "account.json").exists(),
        "positions.json": (base / "positions.json").exists(),
        "fills.json": (base / "fills.json").exists(),
        "orders_recent.json": (base / "orders_recent.json").exists(),
    }
    # MT5 availability flag from integrations
    try:
        from chamelefx.integrations import MT5_AVAILABLE  # type: ignore
        mt5 = bool(MT5_AVAILABLE)
    except Exception:
        mt5 = False

    routers = {
        "blotter": _is_mounted("app.api.ext_orders_blotter", "blotter_router"),
        "router_stats": _is_mounted("app.api.ext_router_stats", "router_stats_router"),
        "alpha_features": _is_mounted("app.api.ext_alpha_features", "alpha_feat_router"),
        "alpha_weight": _is_mounted("app.api.ext_alpha_weight", "alpha_weight_router"),
        "alpha_trade_live": _is_mounted("app.api.ext_alpha_trade_live", "alpha_trade_live_router"),
        "perf": _is_mounted("app.api.ext_perf_metrics", "perf_router"),
        "validation_autopilot": _is_mounted("app.api.ext_validation_autopilot", "validation_autopilot_router"),
    }
    return {"ok": True, "runtime_files": files, "mt5_available": mt5, "routers_importable": routers}
"""

def patch_server():
    sp = APP / "server.py"
    txt = sp.read_text(encoding="utf-8")

    # keep future-import at top
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    if m:
        future, rest = m.group(1), m.group(2)
    else:
        future, rest = "", txt

    # import middleware module
    imp_mw = "from app.api.mw_gate import Gatekeeper"
    if imp_mw not in rest:
        rest = imp_mw + "\n" + rest

    # import health router
    imp_health = "from app.api.ext_debug_health import router as debug_health_router"
    if imp_health not in rest:
        rest = imp_health + "\n" + rest

    # include health router once
    inc_health = "app.include_router(debug_health_router)"
    if inc_health not in rest:
        rest += "\n" + inc_health + "\n"

    # inject middleware on FastAPI app creation line(s)
    # try to add gate after app = FastAPI(...)
    if "Gatekeeper(" not in rest:
        rest = re.sub(
            r'(app\s*=\s*FastAPI\([^\)]*\))',
            r'\1\napp.add_middleware(Gatekeeper, global_limit=8, per_path_qps=6.0, sequential_paths=("/alpha/", "/portfolio/"))',
            rest,
            count=1
        )

    sp.write_text(future + rest, encoding="utf-8")
    print("[K] server.py patched (middleware + health router)")

def main():
    # utils
    write(CFX / "utils" / "ttlcache.py", TTL)
    write(CFX / "utils" / "__init__.py", "")
    # mw
    write(APP / "mw_gate.py", MW)
    # health
    write(APP / "ext_debug_health.py", HEALTH)
    # server patch
    patch_server()
    print("[K] Bundle K installed.")

if __name__ == "__main__":
    main()
