from __future__ import annotations
from chamelefx.log import get_logger
from fastapi import APIRouter, Body
from pathlib import Path
import json, time

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
RUN  = ROOT / "chamelefx" / "runtime"
RUN.mkdir(parents=True, exist_ok=True)
STATE = RUN / "safe_mode.json"

def _get():
    try: return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception: return {"enabled": False, "ts": 0}

def _set(enabled: bool):
    d = {"enabled": bool(enabled), "ts": time.time()}
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
    tmp.replace(STATE)
    return d

@router.get("/ops/safe_mode/status")
def safe_mode_status():
    return _get()

@router.post("/ops/safe_mode/toggle")
def safe_mode_toggle(enable: bool = Body(..., embed=True)):
    d = _set(enable)
    # optional: if enabling, reduce risk & disable costly venues quickly
    try:
        if d["enabled"]:
            # write a risk hint file (consumed by your pretrade/risk layer if wired)
            (RUN / "risk_hint.json").write_text(json.dumps({"risk_multiplier":0.5}, indent=2), encoding="utf-8")
            # disable an alt venue quickly (if present)
            from chamelefx.router import state as RS
            RS.disable("MT5_ALT", 900)
        else:
            (RUN / "risk_hint.json").write_text(json.dumps({"risk_multiplier":1.0}, indent=2), encoding="utf-8")
            from chamelefx.router import state as RS
            RS.enable("MT5_ALT")
    except Exception:
    get_logger(__name__).exception('Unhandled exception')
    return {"ok": True, "state": d}
