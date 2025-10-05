
from __future__ import annotations
class Ensemble:
    def __init__(self, *args, **kwargs): pass
def confidence(norm_or_weights, weights=None, clamp: float | None = None) -> float:
    try:
        if isinstance(norm_or_weights, dict) and weights is not None:
            norm = norm_or_weights or {}; w = weights or {}
            if not w: return 0.0
            vals = [abs(float(x)) for x in (w.values() if isinstance(w, dict) else list(w))]
            avg_abs = sum(vals)/max(1,len(vals))
            nv = [float(v) for v in norm.values()] if isinstance(norm, dict) else []
            penalty = 0.0
            if nv:
                mu = sum(nv)/len(nv); var = sum((v-mu)**2 for v in nv)/len(nv); penalty = min(1.0, var**0.5)
            base = max(0.0, min(1.0, avg_abs)); conf = max(0.0, min(1.0, base*(1-0.5*penalty)))
            if clamp is not None: conf = min(conf, float(clamp))
            return float(conf)
        weights = norm_or_weights
        if weights is None: return 0.0
        seq = list(weights.values()) if isinstance(weights, dict) else list(weights) if isinstance(weights,(list,tuple)) else [float(weights)]
        if not seq: return 0.0
        avg_abs = sum(abs(float(x)) for x in seq)/len(seq); return float(max(0.0, min(1.0, avg_abs)))
    except Exception:
        return 0.0
