from __future__ import annotations
from chamelefx.log import get_logger
from typing import Dict, Any, List
from pathlib import Path
import json, statistics, time

ROOT = Path(__file__).resolve().parents[1]
RUN  = ROOT / "runtime"
RUN.mkdir(parents=True, exist_ok=True)
STORE = RUN / "alpha_monitor.json"

DEFAULT = {"symbols": {}, "ts": 0}

def _read() -> dict:
    try:
        d = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return d
        return DEFAULT.copy()
    except Exception:
        return DEFAULT.copy()

def _write(d: dict) -> None:
    d["ts"] = time.time()
    STORE.write_text(json.dumps(d, indent=2), encoding="utf-8")

def _rolling_stats(arr: List[float]) -> dict:
    if not arr:
        return {"n":0,"mean":0.0,"stdev":0.0,"snr":0.0}
    n = len(arr)
    mean = float(statistics.mean(arr))
    stdev = float(statistics.pstdev(arr)) if n>1 else 0.0
    snr = float(abs(mean) / (stdev + 1e-12))
    return {"n":n,"mean":mean,"stdev":stdev,"snr":snr}

def _regime_flags(prices: List[float]) -> dict:
    # minimal regime detector: rolling return & rolling stdev
    if not prices or len(prices) < 5:
        return {"trend":"unknown","vol":"unknown"}
    rets = [0.0] + [(prices[i]-prices[i-1])/(prices[i-1] or 1.0) for i in range(1,len(prices))]
    rmean = float(statistics.mean(rets))
    rvol  = float(statistics.pstdev(rets)) if len(rets)>1 else 0.0
    trend = "trend" if abs(rmean) > (rvol*0.25) else "range"
    vol = "low"
    if rvol > 0.015: vol = "high"
    elif rvol > 0.006: vol = "normal"
    return {"trend":trend, "vol":vol}

def ingest(symbol: str, signal_value: float, price: float | None = None, window: int = 200, bt_mean_hint: float | None = None) -> dict:
    # Ingest a live datapoint (signal + optional price). Keeps a rolling window and computes health.
    d = _read()
    sym = str(symbol).upper()
    srec = d["symbols"].setdefault(sym, {"signals": [], "prices": [], "last": {}})

    sigs = srec["signals"]
    sigs.append(float(signal_value))
    if len(sigs) > max(10, int(window)):
        srec["signals"] = sigs[-int(window):]

    if price is not None:
        pxs = srec["prices"]
        pxs.append(float(price))
        if len(pxs) > max(10, int(window)):
            srec["prices"] = pxs[-int(window):]

    stats = _rolling_stats(srec["signals"])
    regime = _regime_flags(srec.get("prices", []))

    degrade = (stats["n"] >= 30 and stats["snr"] < 0.25)

    drift = None
    if bt_mean_hint is not None:
        try:
            drift = float(stats["mean"] - float(bt_mean_hint))
        except Exception:
            drift = None

    last = {
        "ts": time.time(),
        "stats": stats,
        "regime": regime,
        "degrade": bool(degrade),
        "drift_vs_bt_mean": drift
    }
    srec["last"] = last
    _write(d)
    return {"ok": True, "symbol": sym, **last}

def health(symbol: str) -> dict:
    d = _read()
    sym = str(symbol).upper()
    rec = d["symbols"].get(sym) or {}
    return {"ok": True, "symbol": sym, "last": rec.get("last", {}), "n": len(rec.get("signals", []))}

def regimes() -> dict:
    d = _read()
    out = {}
    for sym, rec in d.get("symbols", {}).items():
        r = (rec.get("last") or {}).get("regime") or {"trend":"unknown","vol":"unknown"}
        out[sym] = r
    return {"ok": True, "ts": d.get("ts", 0), "regimes": out}
