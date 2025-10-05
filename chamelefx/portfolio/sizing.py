from __future__ import annotations
from chamelefx.log import get_logger
import os, json, math
from typing import Dict, Any, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUNTIME = os.path.join(ROOT, "runtime")
CFG = os.path.join(ROOT, "config.json")
VOLF = os.path.join(RUNTIME, "vols.json")  # optional: {"EURUSD":0.006, ...} (daily stdev or ATR% as decimal)
REGF = os.path.join(RUNTIME, "regime.json")# optional: {"vol_regime":"low|med|high","trend":"up|down|range"}

def _cfg() -> Dict[str, Any]:
    try: return json.load(open(CFG,"r",encoding="utf-8"))
    except: return {}

def _read_json(path, default):
    try: return json.load(open(path,"r",encoding="utf-8"))
    except: return default

def fixed_risk(weights: Dict[str,float], equity: float, params: Dict[str,Any]) -> Dict[str,float]:
    """Map weights (-1..+1) to lots using a fixed gross lot budget."""
    total_lots = float(params.get("total_lots", 3.0))
    out = {str(s): float(w)*total_lots for s,w in (weights or {}).items()}
    return out

def kelly_fractional(weights: Dict[str,float], equity: float, params: Dict[str,Any]) -> Dict[str,float]:
    """
    Fractional Kelly sizing per symbol:
      lots = sign(w) * kelly_frac * capital_fraction
    We approximate edge as |w| (0..1), variance as proxy from vol or default.
    """
    kf = float(params.get("kelly_fraction", 0.25))  # 1.0=full Kelly, 0.25=quarter
    base = float(params.get("base_lots", 1.0))
    vols = _read_json(VOLF,{})
    out={}
    for s,w in (weights or {}).items():
        v = abs(float(vols.get(s, params.get("default_vol", 0.01)))) or 1e-4
        edge = max(0.0, min(1.0, abs(float(w))))  # crude proxy
        f_kelly = edge / max(v,1e-4)
        lots = math.copysign(base * kf * min(f_kelly, 5.0), float(w))
        out[str(s)] = float(lots)
    return out

def vol_adjusted(weights: Dict[str,float], equity: float, params: Dict[str,Any]) -> Dict[str,float]:
    """
    Target a portfolio volatility by allocating inverse to symbol vol:
      lots_s ∝ weight_s * (target_vol / vol_s)
    """
    tvol = float(params.get("target_portfolio_vol", 0.10))  # annualized proxy
    vols = _read_json(VOLF,{})
    scale = float(params.get("scale", 1.0))
    out={}
    for s,w in (weights or {}).items():
        v = abs(float(vols.get(s, params.get("default_vol", 0.01)))) or 1e-4
        lots = float(w) * (tvol / v) * scale
        out[str(s)] = lots
    return out

def regime_aware(weights: Dict[str,float], equity: float, params: Dict[str,Any]) -> Dict[str,float]:
    """
    Adjust lot budget by regime (vol/trend).
      high vol  -> shrink
      low vol   -> expand
    """
    reg = _read_json(REGF,{})
    mult = 1.0
    vol_reg = str(reg.get("vol_regime","med"))
    mult *= {"low":1.4,"med":1.0,"high":0.6}.get(vol_reg,1.0)
    # optional trend tilt, e.g. if 'range' then reduce trend weights (not implemented deeply here)
    base = float(params.get("base_lots", 2.0))
    out = {str(s): float(w) * base * mult for s,w in (weights or {}).items()}
    return out

METHODS = {
    "fixed": fixed_risk,
    "kelly": kelly_fractional,
    "vol": vol_adjusted,
    "regime": regime_aware,
}

def compute(method: str, weights: Dict[str,float], equity: float, params: Dict[str,Any]) -> Dict[str,float]:
    fn = METHODS.get(str(method).lower(), fixed_risk)
    return fn(weights or {}, float(equity or 0.0), params or {})

def default_params() -> Dict[str,Any]:
    cfg = _cfg()
    sizing = cfg.get("sizing", {})
    if not sizing:
        sizing = {
            "method": "fixed",
            "params": {
                "total_lots": 3.0,
                "kelly_fraction": 0.25,
                "base_lots": 1.0,
                "default_vol": 0.01,
                "target_portfolio_vol": 0.10,
                "scale": 1.0
            }
        }
    return sizing
