from __future__ import annotations
from chamelefx.log import get_logger
from pathlib import Path
from typing import Dict, Any, Tuple
import json, math, time

ROOT = Path(__file__).resolve().parents[1]
RUN  = ROOT / "runtime"
RUN.mkdir(parents=True, exist_ok=True)

MON   = RUN / "alpha_monitor.json"      # from Bundle M
PAR   = RUN / "parity_last.json"        # from Bundle J
RSZ   = RUN / "regime_sizing.json"      # from Bundle N

DEFAULT_CFG = {
  "multipliers": {
    "trend":  {"low":1.1, "normal":1.0, "high":0.8},
    "range":  {"low":0.9, "normal":1.0, "high":1.0},
    "unknown":{"low":1.0, "normal":1.0, "high":1.0}
  },
  "fallback": 1.0,
  "bounds": {"min":0.70, "max":1.30},
  "nudge":  {"step":0.005, "snr_boost":0.90, "snr_cut":0.25, "drift_cut":0.15, "drift_mul":0.5}
}

def _read(p: Path, dflt):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dflt

def _write(p: Path, obj):
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def _active_regime(symbol: str, mon: dict) -> Tuple[str,str]:
    sym = symbol.upper()
    rec = ((mon.get("symbols") or {}).get(sym) or {})
    last = rec.get("last") or {}
    reg  = last.get("regime") or {}
    trend = str(reg.get("trend","unknown")).lower()
    vol   = str(reg.get("vol","normal")).lower()
    if trend not in ("trend","range","unknown"): trend = "unknown"
    if vol not in ("low","normal","high"): vol = "normal"
    return trend, vol

def _snr(symbol: str, mon: dict) -> float:
    sym = symbol.upper()
    rec = ((mon.get("symbols") or {}).get(sym) or {})
    stats = ((rec.get("last") or {}).get("stats") or {})
    try:
        return float(stats.get("snr", 0.0))
    except Exception:
        return 0.0

def _drift(par: dict) -> float:
    try:
        return float(par.get("drift", 0.0))
    except Exception:
        return 0.0

def _clamp(x: float, a: float, b: float) -> float:
    return a if x < a else b if x > b else x

def _ensure_cfg(cfg: dict) -> dict:
    # Merge defaults
    out = json.loads(json.dumps(DEFAULT_CFG))
    if isinstance(cfg, dict):
        for k in ("multipliers","fallback","bounds","nudge"):
            if k in cfg:
                out[k] = cfg[k]
    # Normalize numbers
    for reg in out["multipliers"].keys():
        for v in ("low","normal","high"):
            try:
                out["multipliers"][reg][v] = float(out["multipliers"][reg][v])
            except Exception:
                out["multipliers"][reg][v] = 1.0
    try:
        out["fallback"] = float(out.get("fallback", 1.0))
    except Exception:
        out["fallback"] = 1.0
    for k in ("min","max"):
        try:
            out["bounds"][k] = float(out["bounds"][k])
        except Exception:
            out["bounds"][k] = 0.70 if k=="min" else 1.30
    for k in ("step","snr_boost","snr_cut","drift_cut"):
        try:
            out["nudge"][k] = float(out["nudge"][k])
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
    try:
        out["nudge"]["drift_mul"] = float(out["nudge"].get("drift_mul", 0.5))
    except Exception:
        out["nudge"]["drift_mul"] = 0.5
    return out

def preview(symbols: list[str]) -> dict:
    mon = _read(MON, {"symbols":{}})
    par = _read(PAR, {})
    cfg = _ensure_cfg(_read(RSZ, DEFAULT_CFG))
    bounds = cfg["bounds"]; nudge = cfg["nudge"]
    plan = []

    for sym in symbols:
        trend, vol = _active_regime(sym, mon)
        base_mult = cfg["multipliers"].get(trend, {}).get(vol, cfg["fallback"])
        snr = _snr(sym, mon)
        drift = _drift(par)  # global last drift; if you store per-symbol drift, adapt here

        delta = 0.0
        if snr >= nudge["snr_boost"]:
            delta += nudge["step"]          # +0.5% by default
        elif snr <= nudge["snr_cut"]:
            delta -= nudge["step"]          # -0.5%

        if abs(drift) >= nudge["drift_cut"]:
            # penalize more if drift high; scaled by drift_mul (0.5 => up to another ±0.25%)
            delta -= nudge["step"] * nudge["drift_mul"] * (1.0 if drift > 0 else 1.0)

        new_mult = _clamp(base_mult * (1.0 + delta), bounds["min"], bounds["max"])
        plan.append({
            "symbol": sym,
            "regime": {"trend": trend, "vol": vol},
            "snr": snr,
            "drift": drift,
            "prev": base_mult,
            "delta": delta,
            "next": new_mult
        })

    return {"ok": True, "ts": time.time(), "bounds": bounds, "step": nudge["step"], "plan": plan}

def apply(symbols: list[str]) -> dict:
    p = preview(symbols)
    cfg = _ensure_cfg(_read(RSZ, DEFAULT_CFG))
    for row in p["plan"]:
        trend = row["regime"]["trend"]; vol = row["regime"]["vol"]
        cfg["multipliers"].setdefault(trend, {}).setdefault(vol, cfg["fallback"])
        cfg["multipliers"][trend][vol] = float(row["next"])
    _write(RSZ, cfg)
    return {"ok": True, "applied": len(p["plan"]), "config": cfg}

def reset_to_defaults() -> dict:
    _write(RSZ, DEFAULT_CFG)
    return {"ok": True, "config": DEFAULT_CFG}
