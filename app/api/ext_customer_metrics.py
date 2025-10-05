from __future__ import annotations
from chamelefx.log import get_logger
from fastapi import APIRouter
from pathlib import Path
from typing import Dict, Any, List, Optional
import json, math, time

ROOT = Path(__file__).resolve().parents[2]
TEL  = ROOT / "data" / "telemetry"
RUN  = ROOT / "chamelefx" / "runtime"

router = APIRouter()

def _jload(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _equity_last() -> float:
    acct = _jload(RUN / "account.json", {})
    if "equity" in acct:
        try: return float(acct.get("equity", 0.0))
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
    # perf summary fallback
    perf = _jload(TEL / "perf_summary.json", {})
    if isinstance(perf, dict):
        try: return float(perf.get("metrics", {}).get("equity_last", 0.0))
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
    # equity_series fallback
    series = _jload(RUN / "equity_series.json", [])
    if isinstance(series, list) and series:
        try: return float(series[-1])
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
    return 0.0

def _perf_kpis() -> Dict[str, float]:
    # Primary: perf_summary.json if exists (produced by your perf API)
    perf = _jload(TEL / "perf_summary.json", {})
    if isinstance(perf, dict) and "metrics" in perf:
        m = perf.get("metrics", {})
        return {
            "sharpe":     float(m.get("sharpe", 0.0)),
            "max_dd":     float(m.get("max_dd", 0.0)),
            "win_rate":   float(m.get("win_rate", 0.0)),
            "expectancy": float(m.get("expectancy", 0.0)),
            "equity_last": float(m.get("equity_last", 0.0)),
        }
    # Fallback: try to compute rough stats from equity_series.json (if present)
    eq = _jload(RUN / "equity_series.json", [])
    if isinstance(eq, list) and len(eq) >= 5:
        try:
            rets = []
            for i in range(1, len(eq)):
                p0 = float(eq[i-1]) if float(eq[i-1]) != 0 else 1.0
                rets.append((float(eq[i]) / p0) - 1.0)
            if not rets:
                return {"sharpe":0.0,"max_dd":0.0,"win_rate":0.0,"expectancy":0.0,"equity_last": float(eq[-1])}
            import statistics
            mu = statistics.mean(rets)
            sd = statistics.pstdev(rets) or 1e-9
            sharpe = mu / sd
            # max drawdown
            peak = eq[0]
            max_dd = 0.0
            for x in eq:
                if x > peak: peak = x
                dd = (float(x) - float(peak)) / float(peak or 1.0)
                if dd < max_dd: max_dd = dd
            # win rate / expectancy
            wins = sum(1 for r in rets if r > 0)
            wr = wins / len(rets)
            exp = statistics.mean(rets)
            return {"sharpe":float(sharpe),"max_dd":float(max_dd),"win_rate":float(wr),"expectancy":float(exp),"equity_last": float(eq[-1])}
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
    # Last resort zeros
    return {"sharpe":0.0,"max_dd":0.0,"win_rate":0.0,"expectancy":0.0,"equity_last":0.0}

def _alpha_health() -> Dict[str, Any]:
    decay = _jload(TEL / "alpha_decay.json", {})
    drift = _jload(TEL / "alpha_drift.json", {})
    attrib= _jload(TEL / "alpha_attribution.json", {})
    # decay: decide bucket by t-stat (example thresholds)
    tstat = None
    try:
        tstat = float(decay.get("tstat", decay.get("t_stat", None)))
    except Exception:
        tstat = None
    if tstat is None:
        decay_state = "UNKNOWN"
    elif tstat >= 2.0:
        decay_state = "OK"
    elif tstat >= 1.0:
        decay_state = "WARN"
    else:
        decay_state = "ALERT"
    # drift: KL divergence or similar
    kl = None
    try:
        kl = float(drift.get("kl", drift.get("kl_divergence", None)))
    except Exception:
        kl = None
    if kl is None:
        drift_state = "UNKNOWN"
    elif kl < 0.02:
        drift_state = "OK"
    elif kl < 0.05:
        drift_state = "WARN"
    else:
        drift_state = "ALERT"
    # attribution: pick top/bottom 3 by pnl
    top3, bottom3 = [], []
    try:
        items = attrib.get("signals", [])
        # items like [{"name":"sigA","pnl": 123.4}, ...]
        items = sorted(items, key=lambda x: float(x.get("pnl",0.0)))
        bottom3 = [x.get("name","?") for x in items[:3]]
        top3    = [x.get("name","?") for x in items[-3:]][::-1]
    except Exception:
    get_logger(__name__).exception('Unhandled exception')
    return {"decay": decay_state, "drift": drift_state, "top3": top3, "bottom3": bottom3}

def _exec_slip() -> float:
    m = _jload(TEL / "slippage_model.json", {})
    try:
        syms = m.get("symbols", {})
        if not syms: return 0.0
        vals = [float(d.get("slippage_bps", 0.0)) for d in syms.values()]
        return float(sum(vals)/max(1,len(vals)))
    except Exception:
        return 0.0

def _venue_status() -> str:
    # Try reading router status file if your stack writes one; fallback to counts
    status = _jload(TEL / "router_status.json", {})
    try:
        enabled = int(status.get("enabled", 0))
        total   = int(status.get("total", enabled))
        return f"{enabled}/{total} enabled"
    except Exception:
    get_logger(__name__).exception('Unhandled exception')
    # Fallback unknown
    return "unknown"

def _portfolio_drift() -> str:
    # If your portfolio module wrote a drift summary, read it
    pf = _jload(TEL / "portfolio_drift.json", {})
    if isinstance(pf, dict) and "drift_bps" in pf:
        bps = float(pf.get("drift_bps", 0.0))
        if bps < 100: return "LOW"
        if bps < 300: return "MEDIUM"
        return "HIGH"
    return "UNKNOWN"

@router.get("/customer/metrics")
def customer_metrics():
    perf = _perf_kpis()
    ah   = _alpha_health()
    slip = _exec_slip()
    ven  = _venue_status()
    pfd  = _portfolio_drift()
    return {
        "equity": perf.get("equity_last", 0.0),
        "sharpe": perf.get("sharpe", 0.0),
        "max_dd": perf.get("max_dd", 0.0),
        "win_rate": perf.get("win_rate", 0.0),
        "expectancy": perf.get("expectancy", 0.0),
        "decay": ah.get("decay", "UNKNOWN"),
        "drift": ah.get("drift", "UNKNOWN"),
        "top3": ah.get("top3", []),
        "bottom3": ah.get("bottom3", []),
        "slippage_bps": slip,
        "venue_status": ven,
        "portfolio_drift": pfd,
        "ts": time.time(),
    }
