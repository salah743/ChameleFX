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
