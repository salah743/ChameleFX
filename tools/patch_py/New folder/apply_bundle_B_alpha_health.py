# -*- coding: utf-8 -*-
"""
Bundle B: Alpha Health Pack
- chamelefx/alpha/decay.py     : decay recorder & summary (rolling)
- chamelefx/alpha/diagnostics.py: drift vs backtest checks, helpers
- chamelefx/performance/attribution.py: per-signal pnl attribution
- app/api/ext_alpha_health.py   : REST endpoints
- server.py                     : include router
- config.json                   : default thresholds + telemetry dir
"""
from __future__ import annotations
import os, json, time, math, statistics, re
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
API  = ROOT / "app" / "api"
DATA = ROOT / "data" / "telemetry"

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def ensure_cfg():
    cfgp = CFX / "config.json"
    try:
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    t = cfg.setdefault("telemetry", {})
    t.setdefault("dir", "data/telemetry")
    ah = cfg.setdefault("alpha_health", {})
    ah.setdefault("decay_window", 250)         # samples for decay rolling stats
    ah.setdefault("drift_kl_cap", 0.25)        # KL threshold for drift warn
    ah.setdefault("min_samples", 50)           # minimum for stable stats
    ah.setdefault("attrib_window", 500)        # per-signal attribution horizon
    cfgp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

# --------------- alpha/decay.py ----------------------------------------------
DECAY = r'''
from __future__ import annotations
import json, time, math, statistics
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "telemetry"
FILE = DATA / "alpha_decay.json"

def _load() -> Dict[str, Any]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"signals": {}, "ts": time.time()}

def _save(x: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(x, indent=2), encoding="utf-8")
    tmp.replace(FILE)

def _roll(arr: List[float], cap: int) -> List[float]:
    return arr[-cap:] if cap and len(arr) > cap else arr

def record(signal_name: str, signal_value: float, pnl: float, window: int = 250) -> Dict[str, Any]:
    d = _load()
    s = d["signals"].setdefault(signal_name, {"sig": [], "pnl": [], "samples": 0})
    s["sig"]  = _roll(s.get("sig",[])  + [float(signal_value)], window)
    s["pnl"]  = _roll(s.get("pnl",[])  + [float(pnl)], window)
    s["samples"] = len(s["sig"])
    d["ts"] = time.time()
    _save(d)
    return {"ok": True, "signal": signal_name, "samples": s["samples"]}

def _safe_corr(a: List[float], b: List[float]) -> float:
    try:
        if len(a) < 3 or len(b) < 3: return 0.0
        return float(statistics.correlation(a, b))
    except Exception:
        return 0.0

def _safe_mean(x: List[float]) -> float:
    return float(sum(x)/len(x)) if x else 0.0

def _safe_std(x: List[float]) -> float:
    try:
        return float(statistics.pstdev(x)) if len(x) > 1 else 0.0
    except Exception:
        return 0.0

def summary(signal_name: str, window: int = 250) -> Dict[str, Any]:
    d = _load()
    s = d.get("signals", {}).get(signal_name, {})
    sig = s.get("sig", [])[-window:]
    pnl = s.get("pnl", [])[-window:]
    decay_corr = _safe_corr(sig, pnl)
    pnl_mu = _safe_mean(pnl)
    pnl_sd = _safe_std(pnl)
    tstat = (pnl_mu / (pnl_sd / (len(pnl)**0.5))) if pnl and pnl_sd > 1e-12 else 0.0
    return {
        "ok": True,
        "signal": signal_name,
        "samples": len(sig),
        "decay_corr": decay_corr,
        "pnl_mean": pnl_mu,
        "pnl_sd": pnl_sd,
        "t_stat": tstat
    }

def summary_all(window: int = 250) -> Dict[str, Any]:
    d = _load()
    out = {}
    for k in d.get("signals", {}).keys():
        out[k] = summary(k, window)
    return {"ok": True, "signals": out, "ts": d.get("ts",0)}
'''

# --------------- alpha/diagnostics.py ----------------------------------------
DIAG = r'''
from __future__ import annotations
import json, time, math
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "telemetry"
FILE = DATA / "alpha_drift.json"

def _load() -> Dict[str, Any]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"models": {}, "ts": time.time()}

def _save(x: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(x, indent=2), encoding="utf-8")
    tmp.replace(FILE)

def _hist(xs: List[float], bins: int = 20, lo: float = None, hi: float = None):
    if not xs:
        return [0.0]*bins, 0.0, 0.0
    lo = float(min(xs)) if lo is None else float(lo)
    hi = float(max(xs)) if hi is None else float(hi)
    if hi <= lo: hi = lo + 1e-9
    w = (hi - lo) / bins
    h = [0]*bins
    for x in xs:
        idx = int((x - lo) / w)
        if idx >= bins: idx = bins-1
        if idx < 0: idx = 0
        h[idx] += 1
    n = float(len(xs))
    return [c/n for c in h], lo, hi

def _kl(p: List[float], q: List[float]) -> float:
    eps = 1e-9
    s = 0.0
    for pi, qi in zip(p, q):
        s += pi * (math.log((pi+eps)/(qi+eps)))
    return float(s)

def record_distributions(model: str, live_scores: List[float], backtest_scores: List[float], bins: int = 20) -> Dict[str, Any]:
    d = _load()
    m = d["models"].setdefault(model, {})
    p, lo1, hi1 = _hist(live_scores, bins)
    q, lo2, hi2 = _hist(backtest_scores, bins, lo1, hi1)
    m["kl"] = _kl(p, q)
    m["samples_live"] = len(live_scores)
    m["samples_backtest"] = len(backtest_scores)
    m["ts"] = time.time()
    d["ts"] = time.time()
    _save(d)
    return {"ok": True, "model": model, "kl": m["kl"]}

def summary(model: str) -> Dict[str, Any]:
    d = _load()
    return {"ok": True, "model": model, **d.get("models", {}).get(model, {})}

def summary_all() -> Dict[str, Any]:
    d = _load()
    return {"ok": True, "models": d.get("models", {}), "ts": d.get("ts",0)}
'''

# --------------- performance/attribution.py ----------------------------------
ATTRIB = r'''
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "telemetry"
FILE = DATA / "alpha_attribution.json"

def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"signals": {}, "ts": time.time()}

def _save(x):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(x, indent=2), encoding="utf-8")
    tmp.replace(FILE)

def record(signal: str, pnl: float) -> Dict[str, Any]:
    d = _load()
    s = d["signals"].setdefault(signal, {"pnl_sum": 0.0, "count": 0})
    s["pnl_sum"] += float(pnl)
    s["count"]   += 1
    d["ts"] = time.time()
    _save(d)
    return {"ok": True, "signal": signal, "pnl_sum": s["pnl_sum"], "count": s["count"]}

def summary(signal: str) -> Dict[str, Any]:
    d = _load()
    s = d["signals"].get(signal, {"pnl_sum": 0.0, "count": 0})
    avg = (s["pnl_sum"]/s["count"]) if s["count"] else 0.0
    return {"ok": True, "signal": signal, "pnl_sum": s["pnl_sum"], "count": s["count"], "avg": avg}

def summary_all() -> Dict[str, Any]:
    d = _load()
    out = {}
    for k, s in d.get("signals", {}).items():
        avg = (s["pnl_sum"]/s["count"]) if s["count"] else 0.0
        out[k] = {"pnl_sum": s["pnl_sum"], "count": s["count"], "avg": avg}
    return {"ok": True, "signals": out, "ts": d.get("ts",0)}
'''

# --------------- API: ext_alpha_health ---------------------------------------
EXT = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from typing import List
from chamelefx.alpha import decay as AD
from chamelefx.alpha import diagnostics as DG
from chamelefx.performance import attribution as AT

router = APIRouter()

# --- Decay ---
@router.post("/alpha/health/decay_record")
def alpha_decay_record(
    signal: str = Body(..., embed=True),
    signal_value: float = Body(..., embed=True),
    pnl: float = Body(..., embed=True),
    window: int = Body(250, embed=True),
):
    return AD.record(signal, signal_value, pnl, window)

@router.get("/alpha/health/decay_summary/{signal}")
def alpha_decay_summary(signal: str, window: int = 250):
    return AD.summary(signal, window)

@router.get("/alpha/health/decay_summary_all")
def alpha_decay_summary_all(window: int = 250):
    return AD.summary_all(window)

# --- Drift vs backtest ---
@router.post("/alpha/health/drift_record")
def alpha_drift_record(
    model: str = Body(..., embed=True),
    live_scores: List[float] = Body(..., embed=True),
    backtest_scores: List[float] = Body(..., embed=True),
    bins: int = Body(20, embed=True),
):
    return DG.record_distributions(model, live_scores, backtest_scores, bins)

@router.get("/alpha/health/drift_summary/{model}")
def alpha_drift_summary(model: str):
    return DG.summary(model)

@router.get("/alpha/health/drift_summary_all")
def alpha_drift_summary_all():
    return DG.summary_all()

# --- Per-signal attribution ---
@router.post("/alpha/diag/attrib_record")
def alpha_attrib_record(
    signal: str = Body(..., embed=True),
    pnl: float = Body(..., embed=True),
):
    return AT.record(signal, pnl)

@router.get("/alpha/diag/attrib_summary/{signal}")
def alpha_attrib_summary(signal: str):
    return AT.summary(signal)

@router.get("/alpha/diag/attrib_summary_all")
def alpha_attrib_summary_all():
    return AT.summary_all()
'''

def include_router_in_server():
    srv = API / "server.py"
    if not srv.exists(): return
    txt = srv.read_text(encoding="utf-8")
    changed = False
    imp = "from app.api.ext_alpha_health import router as alpha_health_router"
    if imp not in txt:
        txt = imp + "\n" + txt
        changed = True
    if "app.include_router(alpha_health_router)" not in txt:
        txt += "\napp.include_router(alpha_health_router)\n"
        changed = True
    if changed:
        srv.write_text(txt, encoding="utf-8")

def main():
    ensure_cfg()
    write(CFX / "alpha" / "decay.py", DECAY)
    write(CFX / "alpha" / "diagnostics.py", DIAG)
    write(CFX / "performance" / "attribution.py", ATTRIB)
    write(API / "ext_alpha_health.py", EXT)
    include_router_in_server()
    DATA.mkdir(parents=True, exist_ok=True)
    print("[BundleB] Alpha Health Pack installed and API wired.")

if __name__ == "__main__":
    main()
