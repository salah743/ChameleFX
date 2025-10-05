# tools/patch_py/apply_bundle_N_regime_sizing.py
from __future__ import annotations
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[2]
APP  = ROOT / "app" / "api"
CFX  = ROOT / "chamelefx"
RUN  = CFX / "runtime"
RUN.mkdir(parents=True, exist_ok=True)

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.strip()+"\n", encoding="utf-8")
    print("[N] wrote", p)

# -------- regime sizing core (sits in portfolio/sizing_regime.py) --------
CORE = r"""
from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
RUN  = ROOT / "runtime"
RUN.mkdir(parents=True, exist_ok=True)
CFG  = RUN / "regime_sizing.json"
MON  = RUN / "alpha_monitor.json"   # written by Bundle M

DEFAULT = {
  "multipliers": {
    "trend":  {"low":1.1, "normal":1.0, "high":0.8},
    "range":  {"low":0.9, "normal":1.0, "high":1.0},
    "unknown":{"low":1.0, "normal":1.0, "high":1.0}
  },
  "fallback": 1.0
}

def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def get_config() -> dict:
    cfg = _read_json(CFG, DEFAULT)
    # normalize keys/caps
    for k in ("trend","range","unknown"):
        cfg.setdefault("multipliers", {}).setdefault(k, {"low":1.0,"normal":1.0,"high":1.0})
        for v in ("low","normal","high"):
            try:
                cfg["multipliers"][k][v] = float(cfg["multipliers"][k][v])
            except Exception:
                cfg["multipliers"][k][v] = 1.0
    try:
        cfg["fallback"] = float(cfg.get("fallback", 1.0))
    except Exception:
        cfg["fallback"] = 1.0
    return cfg

def set_config(new_cfg: dict) -> dict:
    cfg = get_config()
    # shallow merge
    if isinstance(new_cfg, dict):
        if "multipliers" in new_cfg and isinstance(new_cfg["multipliers"], dict):
            for reg, volmap in new_cfg["multipliers"].items():
                if reg not in cfg["multipliers"]: 
                    cfg["multipliers"][reg] = {"low":1.0,"normal":1.0,"high":1.0}
                if isinstance(volmap, dict):
                    for v, val in volmap.items():
                        try:
                            cfg["multipliers"][reg][v] = float(val)
                        except Exception:
                            pass
        if "fallback" in new_cfg:
            try:
                cfg["fallback"] = float(new_cfg["fallback"])
            except Exception:
                pass
    CFG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"ok": True, "config": cfg}

def _latest_regime(symbol: str) -> tuple[str,str]:
    d = _read_json(MON, {"symbols":{}})
    sym = str(symbol).upper()
    rec = d.get("symbols", {}).get(sym, {})
    last = rec.get("last", {})
    regime = last.get("regime", {}) if isinstance(last, dict) else {}
    trend = str(regime.get("trend","unknown")).lower()
    vol   = str(regime.get("vol","normal")).lower()
    if trend not in ("trend","range","unknown"): trend = "unknown"
    if vol not in ("low","normal","high"): vol = "normal"
    return trend, vol

def regime_multiplier(symbol: str) -> float:
    cfg = get_config()
    trend, vol = _latest_regime(symbol)
    try:
        return float(cfg["multipliers"][trend][vol])
    except Exception:
        return float(cfg.get("fallback", 1.0))

def apply_regime(symbol: str, base_weight: float) -> float:
    mult = regime_multiplier(symbol)
    return float(base_weight) * float(mult)
"""

# -------- glue into existing sizing (non-invasive hook) --------
GLUE = r"""
from __future__ import annotations
# This module is imported by portfolio.sizing when present to apply regime adjustment.
from chamelefx.portfolio.sizing_regime import apply_regime as _apply

def adjust_weight(symbol: str, weight: float) -> float:
    try:
        return _apply(symbol, weight)
    except Exception:
        return float(weight)
"""

# -------- API layer for runtime control --------
API = r"""
from __future__ import annotations
from fastapi import APIRouter, Body, Query
from chamelefx.portfolio import sizing_regime as rs
from chamelefx.portfolio import sizing as base

router = APIRouter()

@router.get("/sizing/regime/config")
def get_cfg():
    return {"ok": True, "config": rs.get_config()}

@router.post("/sizing/regime/config")
def set_cfg(cfg: dict = Body(...)):
    return rs.set_config(cfg)

@router.get("/sizing/regime/preview")
def preview(symbol: str = Query("EURUSD"),
           method: str = Query("kelly"),
           clamp: float = Query(0.35),
           signal: float = Query(1.0)):
    try:
        w_base = float(base.weight_from_signal(symbol=symbol, signal=signal, method=method, clamp=clamp))
    except Exception:
        w_base = 0.0
    try:
        from chamelefx.portfolio import sizing_regime_glue as g
        w_adj = float(g.adjust_weight(symbol, w_base))
    except Exception:
        w_adj = w_base
    return {"ok": True, "symbol": symbol, "base": w_base, "adjusted": w_adj}
"""

def patch_server():
    sp = APP / "server.py"
    txt = sp.read_text(encoding="utf-8")

    # keep future-import at the top
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    future, rest = (m.group(1), m.group(2)) if m else ("", txt)

    imp = "from app.api.ext_sizing_regime import router as sizing_regime_router"
    inc = "app.include_router(sizing_regime_router)"
    if imp not in rest:
        rest = imp + "\n" + rest
    if inc not in rest:
        rest += "\n" + inc + "\n"

    (APP/"server.py").write_text(future + rest, encoding="utf-8")
    print("[N] server.py patched (sizing_regime_router)")

def seed_runtime():
    f = RUN / "regime_sizing.json"
    if not f.exists():
        f.write_text(json.dumps({
            "multipliers":{
                "trend":{"low":1.1,"normal":1.0,"high":0.8},
                "range":{"low":0.9,"normal":1.0,"high":1.0},
                "unknown":{"low":1.0,"normal":1.0,"high":1.0}
            },
            "fallback": 1.0
        }, indent=2), encoding="utf-8")
        print("[N] seeded", f)

def main():
    # core + glue + api
    write(CFX / "portfolio" / "sizing_regime.py", CORE)
    write(CFX / "portfolio" / "sizing_regime_glue.py", GLUE)
    write(APP / "ext_sizing_regime.py", API)
    seed_runtime()
    patch_server()
    print("[N] Bundle N installed.")

if __name__ == "__main__":
    main()
