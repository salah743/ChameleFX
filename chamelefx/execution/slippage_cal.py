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
