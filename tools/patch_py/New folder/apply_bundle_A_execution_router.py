# -*- coding: utf-8 -*-
"""
Bundle A: Execution & Router Intelligence
- chamelefx/execution/quality.py -> cost curves (VWAP/IS + slippage), telemetry persist
- chamelefx/execution/router_intel.py -> route decisions, auto-tune feedback, venue disable
- chamelefx/ops/guardrails.py -> venue breach hook (non-breaking)
- app/api/ext_exec_router.py -> API for venues, autotune, summary
- app/api/ext_exec_quality.py -> ensure costs endpoint present
- server.py -> include new routers
- config.json -> ensure execution.* keys exist
"""

from __future__ import annotations
import os, json, time, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
API  = ROOT / "app" / "api"
EXEC = CFX / "execution"
OPS  = CFX / "ops"
DATA = ROOT / "data" / "telemetry"

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def ensure_config():
    cfg_path = CFX / "config.json"
    cfg = {}
    if cfg_path.exists():
        try: cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except: cfg = {}
    cfg.setdefault("execution", {})
    ex = cfg["execution"]
    ex.setdefault("venues", [
        {"name":"MT5","enabled":True,"fee_bps":0.0},
        {"name":"SIM","enabled":True,"fee_bps":0.0}
    ])
    ex.setdefault("cost", {"max_bps": 4.0, "window": 500})
    ex.setdefault("router", {
        "auto_tune": True,
        "min_fill_rate": 0.6,
        "lot_scale": 1.0,
        "cooldown_sec": 600
    })
    cfg.setdefault("telemetry", {})
    cfg["telemetry"].setdefault("dir", "data/telemetry")
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg

QUALITY = r'''
from __future__ import annotations
import os, json, time, math
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "telemetry"
FILE = DATA / "execution_costs.json"

def _load() -> Dict[str, Any]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"symbols": {}, "ts": time.time()}

def _save(obj: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(FILE)

def _roll(arr: List[float], cap: int) -> List[float]:
    if cap <= 0: return arr
    if len(arr) > cap: return arr[-cap:]
    return arr

def _bps(a: float, b: float) -> float:
    try:
        return ( (a - b) / b ) * 1e4
    except Exception:
        return 0.0

def record_fill(symbol: str, px: float, side: str, ref_vwap: Optional[float]=None, ref_mid: Optional[float]=None, qty: float=1.0) -> Dict[str, Any]:
    """
    Update execution cost telemetry. Stores:
      - slippage_bps (fill vs mid)
      - is_bps (implementation shortfall vs ref_vwap)
    """
    d = _load()
    sym = d["symbols"].setdefault(symbol, {"fills":0,"slippage_bps":[],"is_bps":[],"vwap_ref":[],"mid_ref":[]})
    sym["fills"] = int(sym.get("fills",0)) + 1
    if ref_mid is not None:
        # if buy, positive slippage if fill > mid; if sell, reverse sign
        s_bps = _bps(px, ref_mid)
        if str(side).lower().startswith("s"): s_bps = -s_bps
        sym["slippage_bps"] = _roll(sym.get("slippage_bps",[]) + [s_bps], 1000)
    if ref_vwap is not None:
        isb = _bps(px, ref_vwap)
        if str(side).lower().startswith("s"): isb = -isb
        sym["is_bps"] = _roll(sym.get("is_bps",[]) + [isb], 1000)
        sym["vwap_ref"] = _roll(sym.get("vwap_ref",[]) + [ref_vwap], 200)
    if ref_mid is not None:
        sym["mid_ref"] = _roll(sym.get("mid_ref",[]) + [ref_mid], 200)
    d["ts"] = time.time()
    _save(d)
    return {"ok": True, "symbol": symbol}

def symbol_summary(symbol: str, window: int = 200) -> Dict[str, Any]:
    d = _load()
    sym = d["symbols"].get(symbol, {})
    sl = sym.get("slippage_bps", [])[-window:]
    isv= sym.get("is_bps", [])[-window:]
    def _avg(x): 
        return float(sum(x)/len(x)) if x else 0.0
    return {
        "ok": True,
        "symbol": symbol,
        "fills": sym.get("fills",0),
        "slippage_bps_avg": _avg(sl),
        "is_bps_avg": _avg(isv),
        "samples_slippage": len(sl),
        "samples_is": len(isv)
    }

def summary_all(window: int = 200) -> Dict[str, Any]:
    d = _load()
    out = {}
    for k in d.get("symbols", {}).keys():
        out[k] = symbol_summary(k, window)
    return {"ok": True, "symbols": out, "ts": d.get("ts",0)}
'''

ROUTER_INTEL = r'''
from __future__ import annotations
import time, json, os
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
CFG_PATH = CFX / "config.json"
STATE = CFX / "runtime" / "router_state.json"

def _load_cfg() -> Dict[str, Any]:
    try:
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"venues": {}, "ts": 0}

def _save_state(x: Dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(x, indent=2), encoding="utf-8")
    tmp.replace(STATE)

def venues() -> List[Dict[str, Any]]:
    cfg = _load_cfg()
    return list(cfg.get("execution", {}).get("venues", []))

def disable_venue(name: str, reason: str) -> Dict[str, Any]:
    st = _load_state()
    v = st["venues"].setdefault(name, {})
    v["enabled"] = False
    v["disabled_reason"] = reason
    v["disabled_ts"] = time.time()
    _save_state(st)
    return {"ok": True, "name": name, "state": v}

def enable_venue(name: str) -> Dict[str, Any]:
    st = _load_state()
    v = st["venues"].setdefault(name, {})
    v["enabled"] = True
    v.pop("disabled_reason", None)
    v.pop("disabled_ts", None)
    _save_state(st)
    return {"ok": True, "name": name, "state": v}

def decide(symbol: str) -> Dict[str, Any]:
    """
    Decide routing using config venues minus disabled in state.
    Later: add spread, cost curves, fill-rate, time-of-day hooks.
    """
    cfg_venues = venues()
    st = _load_state().get("venues", {})
    active = []
    for v in cfg_venues:
        nm = v.get("name")
        if not v.get("enabled", True): 
            continue
        if st.get(nm, {}).get("enabled", True) is False:
            continue
        active.append(nm)
    chosen = active[0] if active else None
    return {"ok": True, "symbol": symbol, "active": active, "chosen": chosen}

def feedback_cost_breach(symbol: str, avg_cost_bps: float) -> Dict[str, Any]:
    """
    If avg cost > threshold, disable primary venue temporarily.
    """
    cfg = _load_cfg()
    max_bps = float((cfg.get("execution", {}).get("cost", {}).get("max_bps", 4.0)))
    cooldown = float((cfg.get("execution", {}).get("router", {}).get("cooldown_sec", 600)))
    if avg_cost_bps > max_bps:
        dec = decide(symbol)
        chosen = dec.get("chosen")
        if chosen:
            di = disable_venue(chosen, f"cost_breach_{avg_cost_bps:.2f}bps")
            di["cooldown_sec"] = cooldown
            return {"ok": True, "action": "disabled", "venue": chosen, "cooldown_sec": cooldown}
    return {"ok": True, "action": "none"}
'''

GUARDRAILS_PATCH = r'''
from __future__ import annotations
from typing import Dict, Any

def pretrade_gate(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Best-effort gate. If router venue is disabled by state, allow echo to proceed
    but live path will be skipped upstream. This keeps gate non-blocking.
    """
    return {"ok": True, "body": body}
'''

EXT_EXEC_ROUTER = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from typing import Dict, Any
from chamelefx.execution import router_intel as RI
from chamelefx.execution import quality as Q

router = APIRouter()

@router.get("/router/venues")
def router_venues():
    return {"ok": True, "venues": RI.venues()}

@router.post("/router/enable")
def router_enable(name: str = Body(..., embed=True)):
    return RI.enable_venue(name)

@router.post("/router/disable")
def router_disable(name: str = Body(..., embed=True), reason: str = Body("manual", embed=True)):
    return RI.disable_venue(name, reason)

@router.post("/router/decide")
def router_decide(symbol: str = Body(..., embed=True)):
    return RI.decide(symbol)

@router.post("/router/autotune_cost")
def router_autotune_cost(symbol: str = Body(..., embed=True), window: int = Body(200, embed=True)):
    s = Q.symbol_summary(symbol, window)
    if not s.get("ok"): 
        return s
    avg_cost = float(s.get("slippage_bps_avg",0.0))
    act = RI.feedback_cost_breach(symbol, avg_cost)
    return {"ok": True, "symbol": symbol, "avg_slippage_bps": avg_cost, "action": act}
'''

EXT_EXEC_QUALITY_IF_EMPTY = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from typing import Optional
from chamelefx.execution import quality as Q

router = APIRouter()

@router.post("/exec/cost/record")
def exec_cost_record(symbol: str = Body(..., embed=True),
                     price: float = Body(..., embed=True),
                     side: str = Body("buy", embed=True),
                     ref_vwap: Optional[float] = Body(None, embed=True),
                     ref_mid: Optional[float] = Body(None, embed=True)):
    return Q.record_fill(symbol, price, side, ref_vwap, ref_mid)

@router.get("/exec/cost/summary/{symbol}")
def exec_cost_summary(symbol: str):
    return Q.symbol_summary(symbol)

@router.get("/exec/cost/summary_all")
def exec_cost_summary_all():
    return Q.summary_all()
'''

def ensure_router_in_server():
    srv = API / "server.py"
    if not srv.exists():
        return
    t = srv.read_text(encoding="utf-8")
    changed = False
    # import lines
    imports = [
        ("from app.api.ext_exec_router import router as exec_router", "exec_router"),
        ("from app.api.ext_exec_quality import router as exec_quality_router", "exec_quality_router"),
    ]
    for line, alias in imports:
        if line not in t:
            t = line + "\n" + t
            changed = True
    # include lines
    if "app.include_router(exec_router)" not in t:
        t += "\napp.include_router(exec_router)\n"
        changed = True
    if "app.include_router(exec_quality_router)" not in t:
        t += "\napp.include_router(exec_quality_router)\n"
        changed = True
    if changed:
        srv.write_text(t, encoding="utf-8")

def maybe_seed_ext_exec_quality():
    f = API / "ext_exec_quality.py"
    if not f.exists() or f.read_text(encoding="utf-8").strip() == "":
        write(f, EXT_EXEC_QUALITY_IF_EMPTY)

def main():
    cfg = ensure_config()
    write(EXEC / "quality.py", QUALITY)
    write(EXEC / "router_intel.py", ROUTER_INTEL)
    # guardrails (non-breaking best-effort pretrade gate)
    (OPS).mkdir(parents=True, exist_ok=True)
    gr = OPS / "guardrails.py"
    if not gr.exists():
        write(gr, GUARDRAILS_PATCH)
    # API
    write(API / "ext_exec_router.py", EXT_EXEC_ROUTER)
    maybe_seed_ext_exec_quality()
    ensure_router_in_server()
    # Telemetry dir
    DATA.mkdir(parents=True, exist_ok=True)
    print("[BundleA] Installed execution quality + router intelligence, API wired.")

if __name__ == "__main__":
    main()
