# -*- coding: utf-8 -*-
"""
Bundle F: Router Smart Execution
- Adds router scorer/state modules
- Smart router API
- Wires server safely (after __future__ block)
- Ensures config + telemetry paths
"""
from __future__ import annotations
import json, time, shutil, re
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
API  = ROOT / "app" / "api"
ROUT = CFX / "router"
TEL  = ROOT / "data" / "telemetry"

def _w(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def _b(p: Path):
    if p.exists(): shutil.copy2(p, p.with_suffix(p.suffix + f".bak.{int(time.time())}"))

def ensure_cfg():
    cfgp = CFX / "config.json"
    try:
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    router = cfg.setdefault("router", {})
    weights = router.setdefault("weights", {})
    weights.setdefault("slippage", 0.6)
    weights.setdefault("fill_rate", 0.3)
    weights.setdefault("latency",  0.1)
    router.setdefault("cooldown_sec", 900)  # 15 minutes
    router.setdefault("reenable_threshold_bps", 2.0)
    # optional: static venues if you want (can be overwritten by runtime)
    router.setdefault("venues", ["MT5_PRIMARY", "MT5_ALT"])
    cfgp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    TEL.mkdir(parents=True, exist_ok=True)

SCORER = r'''
from __future__ import annotations
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
        return json.loads(p.read_text(encoding="utf-8"))
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
'''

STATE = r'''
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[2]
TEL  = ROOT / "data" / "telemetry"
STATE_FILE = TEL / "router_status.json"

def _load()->Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"disabled": [], "cooldowns": {}, "enabled": 0, "total": 0, "ts": time.time()}

def _save(d: Dict[str, Any]):
    TEL.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)

def disable(venue: str, secs: int)->Dict[str, Any]:
    st = _load()
    if venue not in st.get("disabled", []):
        st.setdefault("disabled", []).append(venue)
    st.setdefault("cooldowns", {})[venue] = time.time() + float(secs)
    st["ts"] = time.time()
    _save(st)
    return {"ok": True, "state": st}

def enable(venue: str)->Dict[str, Any]:
    st = _load()
    if venue in st.get("disabled", []):
        st["disabled"].remove(venue)
    st.get("cooldowns", {}).pop(venue, None)
    st["ts"] = time.time()
    _save(st)
    return {"ok": True, "state": st}

def sweep()->Dict[str, Any]:
    st = _load()
    cd = st.get("cooldowns", {})
    now = time.time()
    changed = False
    for v, t in list(cd.items()):
        if now >= float(t):
            # cooldown elapsed → re-enable
            st["disabled"] = [x for x in st.get("disabled", []) if x != v]
            cd.pop(v, None)
            changed = True
    if changed:
        st["ts"] = time.time()
        _save(st)
    return {"ok": True, "state": st}
'''

API_EXT = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from typing import Dict, Any
from chamelefx.router import scorer as SC
from chamelefx.router import state as RS
from pathlib import Path
import json, time

router = APIRouter()

@router.get("/router/smart/score")
def router_smart_score(symbol: str = "EURUSD"):
    return SC.score_venues(symbol)

@router.get("/router/smart/decide")
def router_smart_decide(symbol: str = "EURUSD"):
    return SC.best_venue(symbol)

@router.post("/router/smart/disable")
def router_smart_disable(venue: str = Body(..., embed=True),
                         cooldown_sec: int = Body(900, embed=True)):
    return RS.disable(venue, cooldown_sec)

@router.post("/router/smart/enable")
def router_smart_enable(venue: str = Body(..., embed=True)):
    return RS.enable(venue)

@router.post("/router/smart/autotune")
def router_smart_autotune(symbol: str = Body("EURUSD", embed=True),
                          breach_bps: float = Body(5.0, embed=True)):
    """
    If symbol model slippage > breach_bps → disable worst venue for cooldown.
    If below re-enable threshold → sweep + re-enable.
    """
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[2]
    TEL  = ROOT / "data" / "telemetry"
    model = {}
    try:
        model = json.loads((TEL / "slippage_model.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    sym = (model.get("symbols", {}) or {}).get(symbol, {})
    cur = float(sym.get("slippage_bps", 0.0))
    # get best/worst from scores
    sc = SC.score_venues(symbol)
    scores = sc.get("scores", [])
    if not scores:
        return {"ok": False, "error": "no_venues"}
    worst = sorted(scores, key=lambda x: x["slippage_bps"], reverse=True)[0]
    # thresholds
    from chamelefx.router.scorer import _cfg, _cooldown_sec, _reenable_thr_bps
    conf = _cfg()
    cooldown = _cooldown_sec(conf)
    rethr = _reenable_thr_bps(conf)
    actions = []
    if cur > breach_bps:
        RS.disable(worst["venue"], cooldown)
        actions.append({"action":"disable", "venue":worst["venue"], "reason":"breach", "slippage_bps": cur})
    else:
        # try sweep/enables (in case model improved)
        RS.sweep()
        if cur <= rethr:
            # opportunistic enable all
            st = RS._load()
            for v in list(st.get("disabled", [])):
                RS.enable(v)
                actions.append({"action":"enable", "venue":v, "reason":"model_ok", "slippage_bps": cur})
    return {"ok": True, "slippage_bps": cur, "actions": actions}
'''

def _place_after_future(txt: str, import_line: str) -> str:
    lines = txt.splitlines()
    n = len(lines)
    i = 0
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
    j = i
    last_future = -1
    while j < n and lines[j].strip().startswith("from __future__ import"):
        last_future = j; j += 1
    idx = (last_future + 1) if last_future >= 0 else 0
    if import_line in "\n".join(lines):
        return "\n".join(lines)
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
    t2 = _place_after_future(t, "from app.api.ext_router_smart import router as router_smart_router")
    t2 = _append_include(t2, "app.include_router(router_smart_router)")
    if t2 != t:
        _b(srv)
        srv.write_text(t2, encoding="utf-8")

def main():
    ensure_cfg()
    _w(ROUT / "scorer.py", SCORER)
    _w(ROUT / "state.py",  STATE)
    _w(API  / "ext_router_smart.py", API_EXT)
    wire_server()
    print("[BundleF] Router Smart Execution installed & wired.")

if __name__ == "__main__":
    main()
