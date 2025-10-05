from __future__ import annotations
import statistics
from typing import Dict, Any, List

def _live_weighting():
    import importlib
    try: return importlib.import_module("chamelefx.alpha.weighting")
    except Exception:
        class _W:
            @staticmethod
            def weight_from_signal(s, method="kelly", clamp=0.35, params=None):
                return max(-clamp, min(clamp, float(s)*0.1))
        return _W

def sizing_parity(signals: List[float], method="kelly", clamp=0.35)->Dict[str, Any]:
    W = _live_weighting()
    live = [float(W.weight_from_signal(s, method=method, clamp=clamp, params={})) for s in signals]
    bt   = [float(W.weight_from_signal(s, method=method, clamp=clamp, params={})) for s in signals]
    def _mape(a,b):
        eps=1e-12
        return sum(abs(x-y)/max(eps, abs(y)) for x,y in zip(a,b))/max(1,len(a))
    def _corr(a,b):
        try:
            if len(a)<3: return 1.0 if a==b else 0.0
            return float(statistics.correlation(a,b))
        except Exception:
            return 0.0
    return {"ok": True, "mape": _mape(live,bt), "corr": _corr(live,bt), "samples": len(signals)}

def signal_parity(live: List[float], bt: List[float])->Dict[str, Any]:
    # Compare two signal streams (e.g., live vs backtest)
    n = min(len(live), len(bt))
    live = [float(x) for x in live[:n]]
    bt   = [float(x) for x in bt[:n]]
    def _mse(a,b): return sum((x-y)**2 for x,y in zip(a,b))/max(1,len(a))
    def _corr(a,b):
        try:
            if len(a)<3: return 1.0 if a==b else 0.0
            return float(statistics.correlation(a,b))
        except Exception:
            return 0.0
    return {"ok": True, "mse": _mse(live,bt), "corr": _corr(live,bt), "samples": n}

def regime_parity(live_labels: List[str], bt_labels: List[str])->Dict[str, Any]:
    # Match rate between regime labels (e.g., "trend","range","high_vol")
    n = min(len(live_labels), len(bt_labels))
    if n==0: return {"ok": False, "error": "no_labels"}
    match = sum(1 for i in range(n) if str(live_labels[i]) == str(bt_labels[i]))
    return {"ok": True, "match_rate": match/float(n), "samples": n}
