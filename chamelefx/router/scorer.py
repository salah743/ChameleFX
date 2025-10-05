from __future__ import annotations
from chamelefx.log import get_logger
from chamelefx.router import cost_model as _costm
import json, time
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[2]
TEL  = ROOT / "data" / "telemetry"
CFX  = ROOT / "chamelefx"
CONF = CFX / "config.json"

SLIP_MODEL = TEL / "slippage_model.json"
ROUT_STAT  = TEL / "router_status.json"

def _jload(p: Path, default):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return default

def _cfg()->Dict[str, Any]:
    return _jload(CONF, {})

def _weights(conf: Dict[str, Any])->Dict[str,float]:
    r = (conf.get("router") or {}).get("weights", {})
    return {
        "slippage": float(r.get("slippage", 0.6)),
        "fill_rate": float(r.get("fill_rate", 0.3)),
        "latency":  float(r.get("latency",  0.1)),
    }

def _cooldown_sec(conf: Dict[str, Any])->int:
    return int((conf.get("router") or {}).get("cooldown_sec", 900))

def _reenable_thr_bps(conf: Dict[str, Any])->float:
    return float((conf.get("router") or {}).get("reenable_threshold_bps", 2.0))

def _venues(conf: Dict[str, Any])->List[str]:
    return list((conf.get("router") or {}).get("venues", ["MT5_PRIMARY","MT5_ALT"]))

def _write_status(d: Dict[str, Any])->None:
    TEL.mkdir(parents=True, exist_ok=True)
    tmp = ROUT_STAT.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
    tmp.replace(ROUT_STAT)

def score_venues(symbol: str)->Dict[str, Any]:
    """
    Score = -w_slip * normalized_slip + w_fill * fill_rate - w_lat * norm_latency
    Higher is better.
    """
    conf = _cfg()
    w = _weights(conf)
    model = _jload(SLIP_MODEL, {"symbols":{}})
    symd  = model.get("symbols", {})
    venues = _venues(conf)
    out = []
    for v in venues:
        # simplified venue stats: use symbol cost as proxy, defaults to 3.0 bps
        sl_bps = float(symd.get(symbol, {}).get("slippage_bps", 3.0))
        fill_rate = 0.9  # stub; could be learned from fills later
        latency   = 0.15 # seconds; stub; can be measured
        # normalize: smaller is better for slippage/latency → convert to [0..1]
        slip_norm = min(1.0, sl_bps / 10.0)
        lat_norm  = min(1.0, latency / 1.0)
        s = (-w["slippage"] * slip_norm) + (w["fill_rate"] * fill_rate) + (-w["latency"] * lat_norm)
        out.append({"venue": v, "score": float(s), "slippage_bps": sl_bps, "fill_rate": fill_rate, "latency": latency})
    out = sorted(out, key=lambda x: x["score"], reverse=True)
    # status summary for UI
    status = _jload(ROUT_STAT, {})
    enabled_list = [v for v in venues if v not in (status.get("disabled", []))]
    _write_status({"enabled": len(enabled_list), "total": len(venues), "disabled": status.get("disabled", []), "ts": time.time()})
    return {"ok": True, "scores": out, "ts": time.time()}

def best_venue(symbol: str)->Dict[str, Any]:
    s = score_venues(symbol)
    if not s.get("scores"):
        return {"ok": False, "error": "no_venues"}
    return {"ok": True, "best": s["scores"][0], "ts": s["ts"]}

from pathlib import Path
import json, time, statistics
from typing import Dict, Any

LOGS = Path(__file__).resolve().parents[2] / "data" / "logs"
STATS = Path(__file__).resolve().parents[2] / "data" / "telemetry" / "venue_stats.json"

def _parse_exec_log(source="execution.log", lookback=500):
    f = LOGS / source
    if not f.exists(): return []
    lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()[-lookback:]
    out=[]
    for l in lines:
        try:
            j=json.loads(l)
            out.append(j)
        except Exception:
    get_logger(__name__).exception('Unhandled exception')
    return out

def compute(symbol="EURUSD", lookback=500)->Dict[str, Any]:
    trades = _parse_exec_log("execution.log", lookback)
    sym_trades = [t for t in trades if t.get("symbol")==symbol]
    if not sym_trades: return {"ok": False, "error": "no_trades"}
    lats=[t.get("lat_ms",0) for t in sym_trades if "lat_ms" in t]
    costs=[t.get("slip_bps",0) for t in sym_trades if "slip_bps" in t]
    out={
        "ok": True,
        "samples": len(sym_trades),
        "avg_latency": statistics.mean(lats) if lats else None,
        "avg_slip_bps": statistics.mean(costs) if costs else None,
    }
    STATS.parent.mkdir(parents=True, exist_ok=True)
    STATS.write_text(json.dumps(out, indent=2))
    return out
