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
