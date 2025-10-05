# tools/patch_py/apply_bundle_L_router_costs.py
from __future__ import annotations
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[2]
APP  = ROOT / "app" / "api"
CFX  = ROOT / "chamelefx"
RUN  = CFX / "runtime"
RUN.mkdir(parents=True, exist_ok=True)

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.strip() + "\n", encoding="utf-8")
    print("[L] wrote", p)

# ---------------- router cost model ----------------
COST_MODEL = r"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from pathlib import Path
import json, statistics, math, time

ROOT = Path(__file__).resolve().parents[1]
RUN  = ROOT / "runtime"
RUN.mkdir(parents=True, exist_ok=True)
FILLS = RUN / "fills.json"
COSTS = RUN / "router_costs.json"

def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _save_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _fills() -> List[dict]:
    rows = _read_json(FILLS, [])
    if not isinstance(rows, list): rows = []
    out = []
    for r in rows:
        if not isinstance(r, dict): continue
        # expected: symbol, price, qty, side, venue?, bench?
        sym  = str(r.get("symbol","")).upper()
        if not sym: continue
        try:
            px   = float(r.get("price", 0.0))
            qty  = abs(float(r.get("qty", 0.0)))
        except Exception:
            continue
        if px <= 0 or qty <= 0: continue
        bench = float(r.get("bench", px))
        side  = str(r.get("side","buy")).lower()
        venue = str(r.get("venue","")).upper() or "DEFAULT"
        # slippage in bps (positive = worse than bench)
        bps = 0.0
        if bench > 0:
            sgn = 1.0 if side == "buy" else -1.0
            bps = ((px - bench)/bench) * 10000.0 * sgn
        out.append({"symbol":sym, "venue":venue, "qty":qty, "bps":bps})
    return out

def _bucket(notional: float) -> str:
    n = float(notional)
    if n <= 50_000:       return "S"   # small
    if n <= 200_000:      return "M"   # medium
    return "L"                              # large

def refresh() -> dict:
    rows = _fills()
    if not rows:
        table: Dict[str, Any] = {"updated": time.time(), "symbols": {}}
        _save_json(COSTS, table)
        return {"ok": True, "counts": 0, "symbols": 0}

    # aggregate by symbol, venue, size bucket
    agg: Dict[str, Dict[str, Dict[str, list]]] = {}
    for r in rows:
        sym, venue = r["symbol"], r["venue"]
        b = _bucket(r["qty"])
        agg.setdefault(sym, {}).setdefault(venue, {}).setdefault(b, []).append(float(r["bps"]))

    # compute stats
    table = {"updated": time.time(), "symbols": {}}
    for sym, venues in agg.items():
        table["symbols"][sym] = {}
        for venue, buckets in venues.items():
            v = {}
            for b, arr in buckets.items():
                if not arr: 
                    v[b] = {"mean": 0.0, "stdev": 0.0, "p95": 0.0, "n": 0}
                else:
                    arr_sorted = sorted(arr)
                    n = len(arr_sorted)
                    mean = float(statistics.mean(arr_sorted))
                    stdev = float(statistics.pstdev(arr_sorted)) if n > 1 else 0.0
                    p95 = float(arr_sorted[min(n-1, int(0.95*n))])
                    v[b] = {"mean": mean, "stdev": stdev, "p95": p95, "n": n}
            table["symbols"][sym][venue] = v

    _save_json(COSTS, table)
    return {"ok": True, "counts": len(rows), "symbols": len(table["symbols"])}

def summary() -> dict:
    return _read_json(COSTS, {"updated": 0, "symbols": {}})

def cost_penalty_bps(symbol: str, notional: float, venue: str | None = None, mode: str = "p95") -> float:
    """Return bps penalty estimate for (symbol, size, venue)."""
    tab = summary()
    sym = str(symbol).upper()
    if "symbols" not in tab or sym not in tab["symbols"]:
        return 0.0
    ven = (venue or "DEFAULT").upper()
    size = _bucket(notional)
    vs = tab["symbols"][sym]
    # prefer requested venue, else best of available
    candidates = []
    if ven in vs:
        candidates = [ven]
    else:
        candidates = list(vs.keys())
        if not candidates:
            return 0.0
    def pick(vname: str) -> float:
        bx = vs[vname].get(size) or {}
        if mode == "mean":
            return float(bx.get("mean", 0.0))
        if mode == "stdev":
            return float(bx.get("stdev", 0.0))
        return float(bx.get("p95", 0.0))
    vals = [pick(v) for v in candidates]
    # if venue specified but missing bucket stats, fall back to 0
    return float(vals[0] if ven in vs else min(vals) if vals else 0.0)
"""

# --------------- API endpoints -------------------
EXT_COSTS = r"""
from __future__ import annotations
from fastapi import APIRouter, Query
from chamelefx.router import cost_model as cm

router = APIRouter()

@router.post("/router/costs/refresh")
def router_costs_refresh():
    return cm.refresh()

@router.get("/router/costs/summary")
def router_costs_summary():
    return cm.summary()

@router.get("/router/costs/penalty")
def router_costs_penalty(symbol: str = Query("EURUSD"), notional: float = Query(100000.0), venue: str | None = Query(None), mode: str = Query("p95")):
    return {"ok": True, "penalty_bps": cm.cost_penalty_bps(symbol=symbol, notional=notional, venue=venue, mode=mode)}
"""

# --------------- Patch router scorer to use cost model -------------------
def patch_scorer():
    sp = CFX / "router" / "scorer.py"
    if not sp.exists():
        print("[L] WARN: router/scorer.py missing; skipping integration")
        return
    txt = sp.read_text(encoding="utf-8")

    # keep future import block at very top
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    if m:
        future, rest = m.group(1), m.group(2)
    else:
        future, rest = "", txt

    imp = "from chamelefx.router import cost_model as _costm"
    if imp not in rest:
        rest = imp + "\n" + rest

    # heuristic: inject penalty into a function score(...) if present
    # find a def score( line and add penalty usage if not present
    if "_costm.cost_penalty_bps(" not in rest:
        rest = re.sub(
            r"(def\s+score\([^\)]*\)\s*:\s*\n)",
            r"\1    # cost penalty hook\n"
            r"    try:\n"
            r"        _pen = _costm.cost_penalty_bps(symbol=kwargs.get('symbol','EURUSD'), notional=float(kwargs.get('notional',100000.0)), venue=kwargs.get('venue'))\n"
            r"    except Exception:\n"
            r"        _pen = 0.0\n",
            rest,
            count=1
        )
        # then try to find a line where a base score is assembled; we subtract penalty bps*1e-4 to bring into score space
        rest = re.sub(
            r"(\s*return\s+)([^\n]+)",
            r"\1(\2 - (_pen * 1e-4))",
            rest,
            count=1
        )

    sp.write_text(future + rest, encoding="utf-8")
    print("[L] patched router/scorer.py (cost penalty)")

# --------------- Patch server includes ---------------
def patch_server():
    sp = APP / "server.py"
    if not sp.exists():
        print("[L] WARN: app/api/server.py missing; cannot patch router includes")
        return
    txt = sp.read_text(encoding="utf-8")
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    if m:
        future, rest = m.group(1), m.group(2)
    else:
        future, rest = "", txt
    imp = "from app.api.ext_router_costs import router as router_costs_router"
    inc = "app.include_router(router_costs_router)"
    if imp not in rest:
        rest = imp + "\n" + rest
    if inc not in rest:
        rest += "\n" + inc + "\n"
    (APP / "server.py").write_text(future + rest, encoding="utf-8")
    print("[L] server.py patched (router_costs_router)")

def ensure_runtime_seed():
    f = RUN / "router_costs.json"
    if not f.exists():
        f.write_text(json.dumps({"updated": 0, "symbols": {}}, indent=2), encoding="utf-8")
        print("[L] seeded", f)

def main():
    # write files
    write(CFX / "router" / "cost_model.py", COST_MODEL)
    write(APP / "ext_router_costs.py", EXT_COSTS)
    ensure_runtime_seed()
    # patch integrations
    patch_scorer()
    patch_server()
    print("[L] Bundle L installed.")

if __name__ == "__main__":
    main()
