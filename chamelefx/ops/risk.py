from __future__ import annotations
from typing import Dict, Any
def daily_halt(equity: float, ref: float, max_dd_pct: float)->bool:
    if ref<=0: return False
    used = max(0.0, (ref - equity)/ref*100.0)
    return used >= max_dd_pct

def dd_scale(risk_pct: float, eq: float, peak: float, threshold_pct: float, scale: float)->float:
    if peak<=0: return risk_pct
    dd = max(0.0, (peak - eq)/peak*100.0)
    return risk_pct*scale if dd>=threshold_pct else risk_pct
