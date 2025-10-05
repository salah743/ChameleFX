# tools/patch_py/apply_bundle_R_runtime_safety.py
from __future__ import annotations
from pathlib import Path
import re, json, time

ROOT = Path(__file__).resolve().parents[2]
APP  = ROOT / "app" / "api"
CFX  = ROOT / "chamelefx"
RUN  = CFX / "runtime"
RUN.mkdir(parents=True, exist_ok=True)

def w(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.strip() + "\n", encoding="utf-8")
    print("[R] wrote", p)

# ---------------- utils: atomic json ----------------
ATOMIC = r"""
from __future__ import annotations
from pathlib import Path
import json, tempfile, os

def read_json(p: Path, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json_atomic(p: Path, obj) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(p.parent), encoding="utf-8") as tmp:
        json.dump(obj, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, p)  # atomic on Windows/NTFS and POSIX
"""

# ---------------- utils: config/runtime validator ---------------
VALIDATOR = r"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import json

from chamelefx.utils.atomic_json import read_json, write_json_atomic

ROOT = Path(__file__).resolve().parents[1]
CFX  = ROOT
RUN  = ROOT / "runtime"

# Minimal schema with safe defaults; extend as needed.
DEFAULT_CONFIG: Dict[str, Any] = {
    "api": {"host": "127.0.0.1", "port": 18124, "timeout_s": 15},
    "execution": {
        "max_spread_pips": 2.5,
        "news_blackout": False,
        "slippage_log": True
    },
    "portfolio": {
        "rebalance": "weekly",
        "correlation": 0.65,
        "risk_budget": 0.20
    },
    "guardrails": {
        "dd_throttle": 0.35,
        "daily_loss_cap": 0.06
    },
    "routing": {"twap": True},
    "scaling": {"queue": True},
    "capital": {"rebalance": "monthly"}
}

def _deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def validate_and_fix_config(cfg_path: Path) -> dict:
    cfg = read_json(cfg_path, {})
    fixed = _deep_merge(DEFAULT_CONFIG, cfg if isinstance(cfg, dict) else {})
    write_json_atomic(cfg_path, fixed)
    return fixed

def ensure_runtime_layout() -> dict:
    created = []
    for rel in ["runtime", "runtime/reports", "runtime/cache", "runtime/logs"]:
        p = ROOT / rel
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(str(p))
    # seed tiny files if missing
    seeds = {
        "runtime/alpha_monitor.json": {"symbols": {}, "ts": 0},
        "runtime/regime_sizing.json": {
            "multipliers":{
                "trend":{"low":1.1,"normal":1.0,"high":0.8},
                "range":{"low":0.9,"normal":1.0,"high":1.0},
                "unknown":{"low":1.0,"normal":1.0,"high":1.0}
            },
            "fallback":1.0,
            "bounds":{"min":0.70,"max":1.30},
            "nudge":{"step":0.005,"snr_boost":0.9,"snr_cut":0.25,"drift_cut":0.15,"drift_mul":0.5}
        }
    }
    for rel, val in seeds.items():
        p = ROOT / rel
        if not p.exists():
            write_json_atomic(p, val)
            created.append(str(p))
    return {"ok": True, "created": created}
"""

# --------------- diagnostics snapshot -------------------
DIAG = r"""
from __future__ import annotations
from pathlib import Path
import json, time, platform

from chamelefx.utils.atomic_json import read_json
from chamelefx.utils.validator import validate_and_fix_config

ROOT = Path(__file__).resolve().parents[1]
RUN  = ROOT / "runtime"

def file_info(p: Path):
    try:
        st = p.stat()
        return {"exists": True, "size": st.st_size, "mtime": st.st_mtime}
    except Exception:
        return {"exists": False}

def snapshot() -> dict:
    cfgp = ROOT / "config.json"
    cfg  = validate_and_fix_config(cfgp)
    files = {
        "alpha_monitor": file_info(RUN/"alpha_monitor.json"),
        "regime_sizing": file_info(RUN/"regime_sizing.json"),
        "parity_last":   file_info(RUN/"parity_last.json"),
        "router_costs":  file_info(RUN/"router_costs.json"),
        "orders_outbox": file_info(RUN/"orders_outbox.json"),
    }
    return {
        "ok": True,
        "ts": time.time(),
        "meta": {"host": platform.node(), "py": platform.python_version()},
        "config_digest": cfg,
        "files": files
    }

def health() -> dict:
    try:
        ok = True
        issues = []
        # basic checks
        if not (ROOT/"config.json").exists():
            ok = False; issues.append("missing_config_json")
        for need in [RUN, RUN/"reports", RUN/"logs"]:
            if not need.exists():
                ok = False; issues.append(f"missing_dir:{need.name}")
        return {"ok": ok, "issues": issues, "ts": time.time()}
    except Exception as e:
        return {"ok": False, "error": repr(e), "ts": time.time()}
"""

# ------------- runtime safety & rate limit wiring -------------
RUNTIME_EXT = r"""
from __future__ import annotations
from typing import Callable, Awaitable
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time

from chamelefx.utils.validator import validate_and_fix_config, ensure_runtime_layout

# in-memory token bucket per (path) with simple quotas
_BUCKETS = {}  # path -> {tokens, last_ts}
_RATE   = {     # per 2 seconds
  "/stats/summary_fast": 8,
  "/alpha/features/compute": 6,
  "/alpha/weight_from_signal": 10,
}
_WINDOW = 2.0

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        quota = _RATE.get(path)
        if quota:
            now = time.time()
            b = _BUCKETS.get(path, {"tokens": quota, "last": now})
            # refill
            elapsed = now - b["last"]
            if elapsed > _WINDOW:
                b["tokens"] = quota
                b["last"] = now
            if b["tokens"] <= 0:
                return JSONResponse({"ok": False, "error": "rate_limited"}, status_code=429)
            b["tokens"] -= 1
            _BUCKETS[path] = b
        return await call_next(request)

def wire(app) -> None:
    # 1) ensure config + runtime layout
    try:
        from pathlib import Path
        root = Path(__file__).resolve().parents[2] / "chamelefx"
        validate_and_fix_config(root / "config.json")
        ensure_runtime_layout()
    except Exception:
        pass
    # 2) add rate limit middleware
    try:
        app.add_middleware(RateLimitMiddleware)
    except Exception:
        pass
"""

# ------------- API routes for diagnostics ----------------
DIAG_EXT = r"""
from __future__ import annotations
from fastapi import APIRouter
from chamelefx.ops import diag_snapshot as diag

router = APIRouter()

@router.get("/ops/diag/health")
def ops_diag_health():
    return diag.health()

@router.get("/ops/diag/snapshot")
def ops_diag_snapshot():
    return diag.snapshot()
"""

def patch_server():
    sp = APP / "server.py"
    txt = sp.read_text(encoding="utf-8")

    # preserve the future import at the top
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    future, rest = (m.group(1), m.group(2)) if m else ("", txt)

    # imports
    imprs = [
        "from app.api.ext_runtime_safety import wire as runtime_wire",
        "from app.api.ext_diag_snapshot import router as diag_router",
    ]
    for imp in imprs:
        if imp not in rest:
            rest = imp + "\n" + rest

    # wire + include
    if "runtime_wire(app)" not in rest:
        rest += "\n# Bundle R wiring\nruntime_wire(app)\n"
    if "app.include_router(diag_router)" not in rest:
        rest += "app.include_router(diag_router)\n"

    sp.write_text(future + rest, encoding="utf-8")
    print("[R] server.py patched (runtime wire + diag router)")

def main():
    w(CFX / "utils" / "atomic_json.py", ATOMIC)
    w(CFX / "utils" / "validator.py", VALIDATOR)
    w(CFX / "ops" / "diag_snapshot.py", DIAG)
    w(APP / "ext_runtime_safety.py", RUNTIME_EXT)
    w(APP / "ext_diag_snapshot.py", DIAG_EXT)
    patch_server()
    print("[R] Bundle R installed.")

if __name__ == "__main__":
    main()
