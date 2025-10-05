from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[2]
TEL  = ROOT / "data" / "telemetry"
MODEL = TEL / "slippage_model.json"

def _j(p: Path, default):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default

def slip_bps(symbol: str, default_bps: float=2.0) -> float:
    m = _j(MODEL, {"symbols":{}})
    try:
        return float((m.get("symbols", {}) or {}).get(symbol, {}).get("slippage_bps", default_bps))
    except Exception:
        return float(default_bps)

def apply_fill(price: float, side: str, symbol: str, default_bps: float=2.0) -> float:
    """
    Applies modeled slippage to an intended price.
    For buy → pay up, for sell → receive down.
    """
    bps = slip_bps(symbol, default_bps)
    adj = price * (bps/10000.0)
    if str(side).lower() == "buy":
        return price + adj
    else:
        return price - adj
