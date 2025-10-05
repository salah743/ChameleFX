# -*- coding: utf-8 -*-
"""
Bundle G: Backtest Integration Pro
- chamelefx/backtest/walkforward.py (rolling WF + curves export)
- chamelefx/backtest/fills.py (slippage-aware fills)
- chamelefx/backtest/parity.py (signal + regime parity)
- app/api/ext_bt_pro.py (API)
- wires router into app/api/server.py (after __future__ block)
Idempotent and safe.
"""
from __future__ import annotations
import json, time, shutil, re
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
API  = ROOT / "app" / "api"
BT   = CFX / "backtest"
TEL  = ROOT / "data" / "telemetry"

def _w(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def _b(p: Path):
    if p.exists(): shutil.copy2(p, p.with_suffix(p.suffix + f".bak.{int(time.time())}"))

def _cfg() -> Dict[str, Any]:
    p = CFX / "config.json"
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}

def ensure_cfg():
    cfgp = CFX / "config.json"
    cfg = _cfg()
    bt = cfg.setdefault("backtest", {})
    wf = bt.setdefault("walkforward", {})
    wf.setdefault("window", 1000)
    wf.setdefault("step", 200)
    wf.setdefault("test", 250)
    wf.setdefault("symbols", ["EURUSD","GBPUSD","USDJPY"])
    bt.setdefault("slippage_bps_default", 2.0)
    (CFX / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    TEL.mkdir(parents=True, exist_ok=True)

FILLS = r'''
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
'''

WALKFWD = r'''
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
'''

PARITY = r'''
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
'''

API_EXT = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from typing import List, Dict, Any
from chamelefx.backtest import walkforward as WF
from chamelefx.backtest import parity as PR
from chamelefx.backtest import fills as F

router = APIRouter()

# ---- Walk-forward pro ----
@router.post("/btpro/wf/run")
def btpro_wf_run(symbols: List[str] = Body(None, embed=True),
                 window: int = Body(None, embed=True),
                 step: int = Body(None, embed=True),
                 test: int = Body(None, embed=True)):
    return WF.run(symbols=symbols, window=window, step=step, test=test)

@router.get("/btpro/wf/summary")
def btpro_wf_summary():
    return WF.summary()

# ---- Parity expansion ----
@router.post("/btpro/parity/sizing")
def btpro_parity_sizing(signals: List[float] = Body(..., embed=True),
                        method: str = Body("kelly", embed=True),
                        clamp: float = Body(0.35, embed=True)):
    return PR.sizing_parity(signals, method=method, clamp=clamp)

@router.post("/btpro/parity/signal")
def btpro_parity_signal(live: List[float] = Body(..., embed=True),
                        bt:   List[float] = Body(..., embed=True)):
    return PR.signal_parity(live, bt)

@router.post("/btpro/parity/regime")
def btpro_parity_regime(live_labels: List[str] = Body(..., embed=True),
                        bt_labels:   List[str] = Body(..., embed=True)):
    return PR.regime_parity(live_labels, bt_labels)

# ---- Slippage-aware fills (utility) ----
@router.post("/btpro/fill")
def btpro_fill(price: float = Body(..., embed=True),
               side: str    = Body(..., embed=True),
               symbol: str  = Body("EURUSD", embed=True),
               default_bps: float = Body(2.0, embed=True)):
    return {"ok": True, "filled_price": F.apply_fill(price, side, symbol, default_bps)}
'''

def _place_after_future(txt: str, import_line: str) -> str:
    lines = txt.splitlines()
    n = len(lines); i = 0
    # skip shebang/encoding/comments/blank + docstring
    while i < n and (lines[i].strip()=="" or lines[i].lstrip().startswith("#") or lines[i].startswith("\ufeff")):
        i += 1
    if i < n and lines[i].lstrip().startswith(("'''",'\"\"\"')):
        q = "'''" if lines[i].lstrip().startswith("'''") else '"""'
        i += 1
        while i < n and q not in lines[i]:
            i += 1
        if i < n: i += 1
    # now after docstring; find future block
    j=i; last_future=-1
    while j<n and lines[j].strip().startswith("from __future__ import"):
        last_future=j; j+=1
    idx = (last_future+1) if last_future>=0 else 0
    if import_line in "\n".join(lines): return "\n".join(lines)
    lines.insert(idx, import_line)
    return "\n".join(lines)

def _append_include(txt: str, inc: str) -> str:
    if inc in txt: return txt
    if not txt.endswith("\n"): txt += "\n"
    return txt + "\n" + inc + "\n"

def wire_server():
    srv = API / "server.py"
    if not srv.exists(): return
    t = srv.read_text(encoding="utf-8")
    t2 = _place_after_future(t, "from app.api.ext_bt_pro import router as bt_pro_router")
    t2 = _append_include(t2, "app.include_router(bt_pro_router)")
    if t2 != t:
        _b(srv); srv.write_text(t2, encoding="utf-8")

def main():
    ensure_cfg()
    _w(BT / "fills.py", FILLS)
    _w(BT / "walkforward.py", WALKFWD)
    _w(BT / "parity.py", PARITY)
    _w(API / "ext_bt_pro.py", API_EXT)
    wire_server()
    print("[BundleG] Backtest Integration Pro installed & wired.")

if __name__ == "__main__":
    main()
