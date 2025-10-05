from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "telemetry"
FILE = DATA / "alpha_attribution.json"

def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"signals": {}, "ts": time.time()}

def _save(x):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(x, indent=2), encoding="utf-8")
    tmp.replace(FILE)

def record(signal: str, pnl: float) -> Dict[str, Any]:
    d = _load()
    s = d["signals"].setdefault(signal, {"pnl_sum": 0.0, "count": 0})
    s["pnl_sum"] += float(pnl)
    s["count"]   += 1
    d["ts"] = time.time()
    _save(d)
    return {"ok": True, "signal": signal, "pnl_sum": s["pnl_sum"], "count": s["count"]}

def summary(signal: str) -> Dict[str, Any]:
    d = _load()
    s = d["signals"].get(signal, {"pnl_sum": 0.0, "count": 0})
    avg = (s["pnl_sum"]/s["count"]) if s["count"] else 0.0
    return {"ok": True, "signal": signal, "pnl_sum": s["pnl_sum"], "count": s["count"], "avg": avg}

def summary_all() -> Dict[str, Any]:
    d = _load()
    out = {}
    for k, s in d.get("signals", {}).items():
        avg = (s["pnl_sum"]/s["count"]) if s["count"] else 0.0
        out[k] = {"pnl_sum": s["pnl_sum"], "count": s["count"], "avg": avg}
    return {"ok": True, "signals": out, "ts": d.get("ts",0)}
