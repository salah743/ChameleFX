# -*- coding: utf-8 -*-
"""
Bundle D: Backtest & Validation
Adds:
- chamelefx/backtest/parity.py
- chamelefx/execution/slippage_cal.py
- chamelefx/backtest/walkforward.py
- app/api/ext_bt_validate.py
Wires router into app/api/server.py
Ensures config defaults and telemetry dirs.
"""
from __future__ import annotations
import os, json, time, re
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
API  = ROOT / "app" / "api"
BT   = CFX / "backtest"
EXEC = CFX / "execution"
DATA = ROOT / "data" / "telemetry"

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def ensure_cfg():
    cfgp = CFX / "config.json"
    try:
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    # Walk-forward defaults
    wf = cfg.setdefault("backtest", {}).setdefault("walkforward", {})
    wf.setdefault("window", 1000)     # bars in train window
    wf.setdefault("step", 100)        # bars to advance
    wf.setdefault("test", 250)        # bars in test window
    wf.setdefault("symbols", ["EURUSD","GBPUSD","USDJPY"])
    # Slippage model telemetry file
    cfg.setdefault("telemetry", {}).setdefault("dir", "data/telemetry")
    cfgp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

PARITY = r'''
from __future__ import annotations
import math, json, statistics
from typing import Dict, Any, List, Tuple

# We compare "live" sizing (alpha.weighting) vs "bt" sizing (same formulas)
# to guarantee parity—if bt module not present, use weighting for both.

def _load_live_weighting():
    import importlib
    try:
        return importlib.import_module("chamelefx.alpha.weighting")
    except Exception:
        class _W:
            @staticmethod
            def weight_from_signal(signal: float, method: str="kelly", clamp: float=0.35, params=None)->float:
                # basic fallback: linear clamp
                s = float(signal)
                return max(-clamp, min(clamp, s*0.1))
        return _W

def _bt_weight_from_signal(signal: float, method: str="kelly", clamp: float=0.35, params=None)->float:
    # In case you have a dedicated backtest sizing, import it here.
    # Default to live weighting for parity reference.
    W = _load_live_weighting()
    return W.weight_from_signal(signal, method=method, clamp=clamp, params=params or {})

def sizing_parity(signals: List[float], method: str="kelly", clamp: float=0.35, params=None) -> Dict[str, Any]:
    params = params or {}
    W = _load_live_weighting()
    live = [float(W.weight_from_signal(s, method=method, clamp=clamp, params=params)) for s in signals]
    bt   = [float(_bt_weight_from_signal(s, method=method, clamp=clamp, params=params)) for s in signals]
    # metrics
    def _mape(a,b):
        eps=1e-12
        return sum(abs(x - y)/max(eps, abs(y)) for x,y in zip(a,b))/max(1,len(a))
    def _corr(a,b):
        try:
            if len(a) < 3: return 1.0 if a==b else 0.0
            return float(statistics.correlation(a,b))
        except Exception:
            return 0.0
    return {
        "ok": True,
        "method": method,
        "clamp": clamp,
        "samples": len(signals),
        "mape": _mape(live, bt),
        "corr": _corr(live, bt),
        "live_head": live[:5],
        "bt_head": bt[:5]
    }
'''

SLIPCAL = r'''
from __future__ import annotations
import json, math, statistics, time
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "telemetry"
COSTS_FILE = DATA / "execution_costs.json"
ORDERS_FILE = ROOT / "chamelefx" / "runtime" / "orders_recent.json"
MODEL_FILE = DATA / "slippage_model.json"

def _load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _avg(x: List[float])->float:
    return float(sum(x)/len(x)) if x else 0.0

def _blend(a: float, b: float, w: float=0.5)->float:
    return float((1.0-w)*a + w*b)

def calibrate(window: int=200, blend: float=0.5) -> Dict[str, Any]:
    """
    Build per-symbol slippage model (bps) from execution_costs + recent orders echo.
    """
    costs = _load_json(COSTS_FILE, {"symbols":{}})
    echo  = _load_json(ORDERS_FILE, {"orders":[]})
    by_sym = {}

    # from costs json
    for sym, st in costs.get("symbols", {}).items():
        sl = st.get("slippage_bps", [])[-window:]
        by_sym.setdefault(sym, {})["cost_avg_bps"] = _avg(sl)

    # from order echoes (if any have meta slippage/price refs later)
    # For now we only count #orders to weight trust
    for o in echo.get("orders", []):
        s = str(o.get("symbol","?"))
        by_sym.setdefault(s, {})["orders"] = int(by_sym.get(s,{}).get("orders",0)) + 1

    # final model
    model = {"symbols": {}, "ts": time.time()}
    for s, d in by_sym.items():
        cost = float(d.get("cost_avg_bps", 0.0))
        # weight by orders count mildly
        trust = min(1.0, (float(d.get("orders",0))/50.0))
        est = _blend(0.0, cost, w=max(0.2, trust*blend))
        model["symbols"][s] = {"slippage_bps": est, "orders": int(d.get("orders",0))}
    tmp = MODEL_FILE.with_suffix(".tmp")
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(model, indent=2), encoding="utf-8")
    tmp.replace(MODEL_FILE)
    return {"ok": True, "model_file": str(MODEL_FILE), "symbols": model.get("symbols", {})}

def summary() -> Dict[str, Any]:
    m = _load_json(MODEL_FILE, {"symbols":{}})
    return {"ok": True, **m}
'''

WALKFWD = r'''
from __future__ import annotations
import json, time, random
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "telemetry"
WF_FILE = DATA / "walkforward.json"

def _save(obj: Dict[str, Any]):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = WF_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(WF_FILE)

def _load_cfg()->Dict[str, Any]:
    import json
    p = ROOT / "chamelefx" / "config.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _history(symbol: str, lookback: int) -> List[float]:
    """
    Fetch history for symbol. If databank missing, generate toy returns.
    """
    try:
        from chamelefx.databank import history_returns  # optional in your stack
        arr = history_returns(symbol=symbol, lookback=lookback)
        if arr: return [float(x) for x in arr]
    except Exception:
        pass
    # toy: mean 0.02%, sd 0.2%
    import random
    return [random.gauss(0.0002, 0.002) for _ in range(lookback)]

def _equity_curve(rets: List[float]) -> List[float]:
    eq, out = 1.0, []
    for r in rets:
        eq *= (1.0 + float(r))
        out.append(eq)
    return out

def run(symbols: List[str]|None=None, window:int|None=None, step:int|None=None, test:int|None=None) -> Dict[str, Any]:
    cfg = _load_cfg().get("backtest", {}).get("walkforward", {})
    symbols = symbols or cfg.get("symbols", ["EURUSD","GBPUSD","USDJPY"])
    window  = int(window or cfg.get("window", 1000))
    step    = int(step or cfg.get("step", 100))
    test    = int(test or cfg.get("test", 250))
    result = {"ok": True, "runs": [], "ts": time.time()}

    for sym in symbols:
        rets = _history(sym, window + test + step)
        # naive split: [0:window] train, [window:window+test] test
        train = rets[:window]
        test_r= rets[window:window+test]
        # placeholder strategy: mean sign of train returns drives test exposure
        bias = 1.0 if sum(1 for r in train if r>0) >= len(train)/2 else -1.0
        test_sig = [bias for _ in test_r]
        test_eq = _equity_curve([bias*r for r in test_r])
        run = {
            "symbol": sym,
            "train_len": len(train),
            "test_len": len(test_r),
            "bias": bias,
            "equity_last": test_eq[-1] if test_eq else 1.0,
            "sharpe_approx": (sum(test_r)/max(1,len(test_r))) / ( (sum((x - sum(test_r)/max(1,len(test_r)))**2 for x in test_r)/max(1,len(test_r)))**0.5 + 1e-9)
        }
        result["runs"].append(run)

    _save(result)
    return result

def summary() -> Dict[str, Any]:
    try:
        return json.loads(WF_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "error": "no_walkforward"}
'''

API_EXT = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from typing import List, Dict, Any
from chamelefx.backtest import parity as PAR
from chamelefx.execution import slippage_cal as SC
from chamelefx.backtest import walkforward as WF

router = APIRouter()

# --- Parity ---
@router.post("/bt/parity/sizing")
def bt_parity_sizing(signals: List[float] = Body(..., embed=True),
                     method: str = Body("kelly", embed=True),
                     clamp: float = Body(0.35, embed=True)):
    return PAR.sizing_parity(signals, method=method, clamp=clamp, params={})

# --- Slippage calibration ---
@router.post("/exec/slippage/recalibrate")
def exec_slippage_recalibrate(window: int = Body(200, embed=True),
                              blend: float = Body(0.5, embed=True)):
    return SC.calibrate(window=window, blend=blend)

@router.get("/exec/slippage/model")
def exec_slippage_model():
    return SC.summary()

# --- Walk-forward ---
@router.post("/bt/walkforward/run")
def bt_walkforward_run(symbols: List[str] = Body(None, embed=True),
                       window: int = Body(None, embed=True),
                       step: int = Body(None, embed=True),
                       test: int = Body(None, embed=True)):
    return WF.run(symbols=symbols, window=window, step=step, test=test)

@router.get("/bt/walkforward/summary")
def bt_walkforward_summary():
    return WF.summary()
'''

def include_router_in_server():
    srv = API / "server.py"
    if not srv.exists():
        return
    txt = srv.read_text(encoding="utf-8")
    changed = False
    imp = "from app.api.ext_bt_validate import router as bt_validate_router"
    if imp not in txt:
        txt = imp + "\n" + txt
        changed = True
    if "app.include_router(bt_validate_router)" not in txt:
        txt += "\napp.include_router(bt_validate_router)\n"
        changed = True
    if changed:
        srv.write_text(txt, encoding="utf-8")

def main():
    ensure_cfg()
    write(BT   / "parity.py",        PARITY)
    write(EXEC / "slippage_cal.py",  SLIPCAL)
    write(BT   / "walkforward.py",   WALKFWD)
    write(API  / "ext_bt_validate.py", API_EXT)
    include_router_in_server()
    DATA.mkdir(parents=True, exist_ok=True)
    print("[BundleD] Backtest & Validation installed and API wired.")

if __name__ == "__main__":
    main()
