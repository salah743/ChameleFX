
from __future__ import annotations
from typing import Dict, List
from chamelefx.log import get_logger
log = get_logger(__name__)

def _normalize_symbols(symbols: List[str] | None) -> List[str]:
    if not symbols: return ["EURUSD","GBPUSD","USDJPY"]
    return [str(x) for x in symbols if x]

def risk_parity(symbols: List[str] | None = None) -> Dict[str, float]:
    try:
        syms = _normalize_symbols(symbols); w = 1.0/len(syms)
        return {s: round(w,6) for s in syms}
    except Exception:
        log.exception("risk_parity failed"); return {}

def mean_var(symbols: List[str] | None = None) -> Dict[str, float]:
    try:
        syms = _normalize_symbols(symbols)
        if not syms: return {}
        base = 0.6; rest = (1.0-base)/max(1,len(syms)-1)
        out = {syms[0]: round(base,6)}
        for s in syms[1:]: out[s] = round(rest,6)
        return out
    except Exception:
        log.exception("mean_var failed"); return {}

def vol_target(symbols: List[str] | None = None, target: float = 0.10) -> Dict[str, float]:
    try:
        syms = _normalize_symbols(symbols)
        w = min(1.0, max(0.0, float(target)))/max(1,len(syms))
        return {s: round(w,6) for s in syms}
    except Exception:
        log.exception("vol_target failed"); return {}

def solve(method: str, symbols: List[str] | None = None, **kwargs) -> Dict[str, float]:
    try:
        m = (method or "").lower()
        if m in ("risk_parity","rp"): return risk_parity(symbols)
        if m in ("mean_var","mv","mean-variance"): return mean_var(symbols)
        if m in ("vol_target","vt","vol-target","vol"): return vol_target(symbols, float(kwargs.get("target",0.10)))
        return risk_parity(symbols)
    except Exception:
        log.exception("solve failed"); return {}
