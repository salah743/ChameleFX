# tools/patch_py/apply_batch_M1_restore_missing.py
from __future__ import annotations
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]

FILES: dict[str, str] = {
    # API
    "app/api/ext_alpha_weight.py": r'''
from __future__ import annotations
from fastapi import APIRouter, Body
router = APIRouter()
@router.post("/alpha/weight_from_signal")
def weight_from_signal(symbol: str = Body("EURUSD"), weights: dict | None = Body(None), clamp: float = Body(0.35), params: dict | None = Body(None)):
    # trivial sign-based weight as placeholder
    w = 0.0
    if weights and isinstance(weights, dict):
        w = float(weights.get("signal", 0.0))
    w = max(-clamp, min(clamp, w))
    return {"ok": True, "symbol": symbol, "weight": w, "clamp": clamp, "src": "stub"}
''',
    "app/api/ext_perf_metrics.py": r'''
from __future__ import annotations
from fastapi import APIRouter, Body
import math, statistics
router = APIRouter()
_equity: list[float] = []
@router.post("/perf/ingest_equity")
def ingest_equity(equity: list[float] = Body(...)):
    global _equity
    _equity = list(map(float, equity or []))
    return {"ok": True, "ts": __import__("time").time()}
@router.get("/perf/summary")
def perf_summary():
    if not _equity:
        return {"ok": True, "ts": __import__("time").time(), "metrics": {"sharpe":0.0,"max_dd":0.0,"win_rate":0.0,"expectancy":0.0,"equity_last":0.0}}
    eq = _equity
    rets = [0.0] + [ (eq[i]-eq[i-1])/eq[i-1] if eq[i-1] else 0.0 for i in range(1,len(eq)) ]
    sharpe = (statistics.mean(rets) / (statistics.pstdev(rets)+1e-12)) * math.sqrt(252) if len(rets)>1 else 0.0
    peak, dd = -1e18, 0.0
    cur = 0.0
    for v in eq:
        peak = max(peak, v)
        if peak>0: dd = max(dd, (peak - v)/peak)
    wins = sum(1 for r in rets if r>0)
    win_rate = wins/max(1,len(rets))
    expectancy = statistics.mean(rets) if rets else 0.0
    return {"ok": True, "ts": __import__("time").time(), "metrics": {"sharpe":sharpe,"max_dd":dd,"win_rate":win_rate,"expectancy":expectancy,"equity_last":eq[-1]}}
''',

    # Analytics
    "chamelefx/analytics/decay.py": r'''
from __future__ import annotations
def half_life(decay_per_trade: float) -> float:
    # simplistic: HL = ln(0.5)/ln(1-decay)
    import math
    d = max(1e-9, min(0.999999, decay_per_trade))
    return math.log(0.5)/math.log(1.0-d)
''',
    "chamelefx/analytics/diagnostics.py": r'''
from __future__ import annotations
def signal_health(signal_series: list[float]) -> dict:
    import statistics
    if not signal_series: 
        return {"ok":True,"n":0,"mean":0,"stability":0}
    mean = statistics.mean(signal_series)
    vol  = statistics.pstdev(signal_series) + 1e-12
    return {"ok":True,"n":len(signal_series),"mean":mean,"stability":abs(mean)/vol}
''',

    # Execution
    "chamelefx/execution/twap.py": r'''
from __future__ import annotations
def slices(total_qty: float, n: int) -> list[float]:
    n = max(1, int(n))
    slice_sz = float(total_qty)/n
    return [slice_sz]*n
''',

    # Performance
    "chamelefx/performance/stats.py": r'''
from __future__ import annotations
import math, statistics
def summary(equity: list[float]) -> dict:
    if not equity:
        return {"sharpe":0.0,"max_dd":0.0,"win_rate":0.0,"expectancy":0.0,"equity_last":0.0}
    eq = list(map(float, equity))
    rets = [0.0] + [ (eq[i]-eq[i-1])/eq[i-1] if eq[i-1] else 0.0 for i in range(1,len(eq)) ]
    sharpe = (statistics.mean(rets) / (statistics.pstdev(rets)+1e-12)) * math.sqrt(252) if len(rets)>1 else 0.0
    peak, dd = -1e18, 0.0
    for v in eq:
        peak = max(peak, v)
        if peak>0: dd = max(dd, (peak - v)/peak)
    wins = sum(1 for r in rets if r>0)
    win_rate = wins/max(1,len(rets))
    expectancy = statistics.mean(rets) if rets else 0.0
    return {"sharpe":sharpe,"max_dd":dd,"win_rate":win_rate,"expectancy":expectancy,"equity_last":eq[-1]}
''',

    # Validation
    "chamelefx/validation/backtester.py": r'''
from __future__ import annotations
def run(series: list[float], rule: str = "long_on_up") -> dict:
    # toy walk-forward: long if price up vs prev
    if not series or len(series)<2:
        return {"ok":True,"pnl":0.0,"trades":0}
    pnl, trades = 0.0, 0
    for i in range(1, len(series)):
        side = 1 if series[i] > series[i-1] else -1
        pnl += side * (series[i] - series[i-1])
        trades += 1
    return {"ok":True,"pnl":pnl,"trades":trades}
''',

    # Databank
    "chamelefx/databank/loader.py": r'''
from __future__ import annotations
from pathlib import Path
import csv
def load_csv_prices(path: str) -> list[float]:
    p = Path(path)
    if not p.exists(): return []
    out = []
    with p.open("r", newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        for row in r:
            try:
                out.append(float(row[-1]))
            except Exception:
                continue
    return out
''',
}

SERVER_INCLUDES = [
    ("from app.api.ext_alpha_weight import router as alpha_weight_router", "app.include_router(alpha_weight_router)"),
    ("from app.api.ext_perf_metrics import router as perf_router", "app.include_router(perf_router)"),
]

def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip()+"\n", encoding="utf-8")
    return True

def patch_server():
    sp = ROOT / "app" / "api" / "server.py"
    if not sp.exists():
        print("[WARN] server.py missing; cannot patch includes")
        return
    txt = sp.read_text(encoding="utf-8")
    # keep future-import at very top
    import re
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    if m:
        future, rest = m.group(1), m.group(2)
    else:
        future, rest = "", txt
    for imp, inc in SERVER_INCLUDES:
        if imp not in rest:
            rest = imp + "\n" + rest
        if inc not in rest:
            rest += "\n" + inc + "\n"
    sp.write_text(future + rest, encoding="utf-8")

def main():
    created = 0
    for rel, body in FILES.items():
        if write_if_missing(ROOT / rel, body):
            print("[M1] Created:", rel); created += 1
    patch_server()
    print(f"[M1] Done. Files created: {created}")

if __name__ == "__main__":
    main()
