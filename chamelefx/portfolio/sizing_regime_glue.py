from __future__ import annotations
from chamelefx.log import get_logger
# This module is imported by portfolio.sizing when present to apply regime adjustment.
from chamelefx.portfolio.sizing_regime import apply_regime as _apply

def adjust_weight(symbol: str, weight: float) -> float:
    try:
        return _apply(symbol, weight)
    except Exception:
        return float(weight)
