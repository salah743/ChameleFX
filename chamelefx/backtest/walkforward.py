from __future__ import annotations
import json, time, statistics
from pathlib import Path
from typing import Dict, Any, List, Tuple
import random

ROOT = Path(__file__).resolve().parents[2]
TEL  = ROOT / "data" / "telemetry"
WF_JSON = TEL / "walkforward_pro.json"
EQ_DIR = TEL / "wf_curves"

def _save(obj: Dict[str, Any]):
    TEL.mkdir(parents=True, exist_ok=True)
    tmp = WF_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(WF_JSON)

def _cfg()->Dict[str, Any]:
    import json
    p = ROOT / "chamelefx" / "config.json"
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}

def _hist_ret(symbol: str, n: int)->List[float]:
    # Try databank if present
    try:
        from chamelefx.databank import history_returns
        arr = history_returns(symbol=symbol, lookback=n)
        if arr: return [float(x) for x in arr]
    except Exception:
        pass
    # Toy returns if none
    return [random.gauss(0.0002, 0.002) for _ in range(n)]

def _equity(rets: List[float])->List[float]:
    eq=1.0; out=[]
    for r in rets:
        eq *= (1.0 + float(r))
        out.append(eq)
    return out

def _sharpe(rets: List[float])->float:
    if len(rets) < 2: return 0.0
    mu = statistics.mean(rets)
    sd = statistics.pstdev(rets) or 1e-9
    return float(mu/sd)

def _slice_walk(symbol: str, window:int, step:int, test:int)->Dict[str, Any]:
    """
    Rolling WF with multiple slices:
    - train windows advance by `step`
    - each emits a test slice with naive mean-direction strategy for demo.
    """
    need = window + test + 3*step
    R = _hist_ret(symbol, need)
    runs=[]; curves=[]
    start_train = 0
    while start_train + window + test <= len(R):
        train = R[start_train:start_train+window]
        testR = R[start_train+window:start_train+window+test]
        bias = 1.0 if sum(1 for r in train if r>0) >= len(train)/2 else -1.0
        stratR = [bias*r for r in testR]
        eq = _equity(stratR)
        runs.append({
            "train_i": start_train,
            "train_len": len(train),
            "test_len": len(testR),
            "bias": bias,
            "equity_last": eq[-1] if eq else 1.0,
            "sharpe_approx": _sharpe(stratR)
        })
        curves.append(eq)
        start_train += step
    # Save curves to files
    EQ_DIR.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(curves):
        (EQ_DIR / f"{symbol}_run{i}.json").write_text(json.dumps(c), encoding="utf-8")
    return {"symbol": symbol, "runs": runs, "curves": len(curves)}

def run(symbols: List[str]|None=None, window:int|None=None, step:int|None=None, test:int|None=None)->Dict[str, Any]:
    cfg = _cfg().get("backtest", {}).get("walkforward", {})
    symbols = symbols or cfg.get("symbols", ["EURUSD","GBPUSD","USDJPY"])
    window  = int(window or cfg.get("window", 1000))
    step    = int(step or cfg.get("step", 200))
    test    = int(test or cfg.get("test", 250))
    out={"ok": True, "ts": time.time(), "wf": []}
    for s in symbols:
        out["wf"].append(_slice_walk(s, window, step, test))
    _save(out)
    return out

def summary()->Dict[str, Any]:
    try: return json.loads(WF_JSON.read_text(encoding="utf-8"))
    except Exception: return {"ok": False, "error": "no_walkforward_pro"}
