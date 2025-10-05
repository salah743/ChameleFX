
from pathlib import Path
import re
from patchlib import project_root, backup_write

ROOT = project_root(Path(__file__))
p = ROOT / "chamelefx/alpha/ensemble.py"
if not p.exists():
    print(f"[WARN] {p} not found")
else:
    txt = p.read_text(encoding="utf-8")
    m2 = re.search(r"""def\s+confidence\s*\(.*?\)\s*:\s*(?:.|\n)*?(?=\ndef\s+\w+\(|\Z)""", txt, re.S)
    if not m2:
        print("[WARN] could not determine confidence() block to replace")
    else:
        new_func = '''
def confidence(norm_or_weights, weights=None, clamp: float | None = None) -> float:
    """Flexible confidence score in [0,1].
    Modes:
      - confidence(weights)
      - confidence(norm, weights, clamp=...)
    """
    try:
        if isinstance(norm_or_weights, dict) and weights is not None:
            norm = norm_or_weights or {}
            w = weights or {}
            if not w:
                return 0.0
            vals = [abs(float(x)) for x in (w.values() if isinstance(w, dict) else list(w))]
            avg_abs = sum(vals) / max(1, len(vals))
            nv = [float(v) for v in norm.values()] if isinstance(norm, dict) else []
            if nv:
                mu = sum(nv)/len(nv)
                var = sum((v-mu)**2 for v in nv)/len(nv)
                penalty = min(1.0, var ** 0.5)
            else:
                penalty = 0.0
            base = max(0.0, min(1.0, avg_abs))
            conf = max(0.0, min(1.0, base * (1.0 - 0.5*penalty)))
            if clamp is not None:
                conf = min(conf, float(clamp))
            return float(conf)
        weights = norm_or_weights
        if weights is None:
            return 0.0
        seq = list(weights.values()) if isinstance(weights, dict) else list(weights) if isinstance(weights, (list, tuple)) else [float(weights)]
        if not seq:
            return 0.0
        avg_abs = sum(abs(float(x)) for x in seq) / len(seq)
        return float(max(0.0, min(1.0, avg_abs)))
    except Exception:
        return 0.0
'''.lstrip("\n")
        new = txt[:m2.start()] + new_func + txt[m2.end():]
        if new != txt:
            backup_write(p, new)
            print("[OK] extended ensemble.confidence to support API call shape")
        else:
            print("[SKIP] ensemble.confidence already up to date")
