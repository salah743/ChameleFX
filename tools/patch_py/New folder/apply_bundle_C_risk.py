# -*- coding: utf-8 -*-
"""
Bundle C: Risk Enhancements
- chamelefx/ops/guardrails.py : daily loss cap + sequence loss brake + drift chip helpers
- chamelefx/ops/watchdog.py   : state helpers (load/save/reset) (idempotent update)
- app/api/ext_risk_plus.py    : risk state, reset, simulate recorders
- server.py                   : auto-include router
- config.json                 : ensure risk.* keys present
- data/telemetry              : ensure dir
"""
from __future__ import annotations
import json, time, os, re
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
OPS  = CFX / "ops"
API  = ROOT / "app" / "api"
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
    risk = cfg.setdefault("risk", {})
    # Per-symbol day loss caps (bps of equity)
    risk.setdefault("daily_loss_bps", {"DEFAULT": 150})   # 1.5% default cap
    # Sequence-loss brake
    risk.setdefault("seq_loss", {"max_losses": 3, "cooldown_sec": 1800})  # 30min
    # Rebalance chip threshold (portfolio drift)
    risk.setdefault("rebalance", {"drift_bps": 100})  # 1% drift flag
    # Telemetry dir
    cfg.setdefault("telemetry", {}).setdefault("dir", "data/telemetry")
    cfgp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg

GUARDRAILS = r'''
from __future__ import annotations
import json, time, math
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
DATA = ROOT / "data" / "telemetry"
STATE_FILE = CFX / "runtime" / "risk_state.json"

def _now() -> float:
    return time.time()

def _day_key(ts: Optional[float] = None) -> str:
    import datetime as _dt
    d = _dt.datetime.utcfromtimestamp(ts or _now()).strftime("%Y-%m-%d")
    return d

def _load_cfg() -> Dict[str, Any]:
    import json
    p = CFX / "config.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"ts": _now(), "by_symbol": {}, "global": {}}

def _save_state(s: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)

def _get_cap_bps(symbol: str, cfg: Dict[str, Any]) -> float:
    bps_map = ((cfg.get("risk") or {}).get("daily_loss_bps") or {})
    return float(bps_map.get(symbol, bps_map.get("DEFAULT", 150)))  # 1.5% default

def record_pnl(symbol: str, pnl: float, equity: float) -> Dict[str, Any]:
    """
    Record realized PnL for today; update cumulative loss.
    """
    st = _load_state()
    day = _day_key()
    sym = st["by_symbol"].setdefault(symbol, {})
    d = sym.setdefault(day, {"pnl": 0.0, "losses_seq": 0, "last_update": _now()})
    d["pnl"] = float(d.get("pnl", 0.0)) + float(pnl)
    d["last_update"] = _now()
    # sequence loss counter (increment on negative pnl point)
    if pnl < 0:
        d["losses_seq"] = int(d.get("losses_seq", 0)) + 1
    else:
        d["losses_seq"] = 0
    st["ts"] = _now()
    _save_state(st)
    return {"ok": True, "symbol": symbol, "day": day, "pnl_today": d["pnl"], "losses_seq": d["losses_seq"]}

def pretrade_gate(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gate before live placement. Returns:
      { ok: True/False, blocked?:bool, reason?:str, body?:dict, state?:dict }
    Non-destructive: if blocked, caller can still echo-ack but must skip live route.
    """
    cfg = _load_cfg()
    st  = _load_state()
    symbol = str(body.get("symbol", "UNKNOWN"))
    equity = float(((st.get("global") or {}).get("equity_last", 0.0)))
    # Allow config equity override if app feeds it elsewhere
    eq_cfg = float(((cfg.get("account") or {}).get("equity_override", 0.0)))
    if eq_cfg > 0:
        equity = eq_cfg

    # --- daily loss cap check ---
    day = _day_key()
    symd = (st.get("by_symbol", {}).get(symbol, {}).get(day, {}) or {})
    pnl_today = float(symd.get("pnl", 0.0))
    cap_bps   = _get_cap_bps(symbol, cfg)
    cap_amt   = (cap_bps / 1e4) * max(1.0, equity)
    if pnl_today <= -cap_amt:
        return {"ok": True, "blocked": True, "reason": f"daily_loss_cap_{cap_bps}bps", "state": {"pnl_today": pnl_today, "cap_amt": cap_amt}}

    # --- sequence-loss brake ---
    seq_conf = ((cfg.get("risk") or {}).get("seq_loss") or {})
    max_losses = int(seq_conf.get("max_losses", 3))
    cooldown   = float(seq_conf.get("cooldown_sec", 1800))
    losses_seq = int(symd.get("losses_seq", 0))
    last_ts    = float(symd.get("last_update", 0.0))
    if losses_seq >= max_losses:
        # Enforce cooldown from last update
        if _now() - last_ts < cooldown:
            remain = int(cooldown - (_now() - last_ts))
            return {"ok": True, "blocked": True, "reason": f"seq_loss_cooldown_{remain}s", "state": {"losses_seq": losses_seq}}
        # else reset sequence counter (gracefully)
        st["by_symbol"].setdefault(symbol, {}).setdefault(day, {})["losses_seq"] = 0
        _save_state(st)

    return {"ok": True, "body": body, "state": {"pnl_today": pnl_today, "losses_seq": losses_seq}}

def set_equity(equity: float) -> Dict[str, Any]:
    st = _load_state()
    st["global"]["equity_last"] = float(equity)
    st["ts"] = _now()
    _save_state(st)
    return {"ok": True, "equity": st["global"]["equity_last"]}

def portfolio_drift_flag(current_weights: Dict[str, float], target_weights: Dict[str, float], drift_bps: float = 100.0) -> Dict[str, Any]:
    """
    Compute total absolute drift (sum |w_cur - w_tgt|) in bps.
    Return a small struct used by the UI to show a 'Rebalance' chip.
    """
    tot = 0.0
    keys = set(current_weights) | set(target_weights)
    for k in keys:
        cur = float(current_weights.get(k, 0.0))
        tgt = float(target_weights.get(k, 0.0))
        tot += abs(cur - tgt)
    # convert to bps for readability
    drift = float(tot * 1e4)
    return {"ok": True, "drift_bps": drift, "flag": drift >= drift_bps}
'''

WATCHDOG = r'''
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[2]
CFX  = ROOT / "chamelefx"
STATE_FILE = CFX / "runtime" / "risk_state.json"

def load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"ts": time.time(), "by_symbol": {}, "global": {}}

def reset_today(symbol: str = None) -> Dict[str, Any]:
    st = load_state()
    if symbol is None:
        st["by_symbol"] = {}
    else:
        st.get("by_symbol", {}).pop(symbol, None)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)
    return {"ok": True, "state": st}
'''

EXT_RISK = r'''
from __future__ import annotations
from fastapi import APIRouter, Body
from typing import Dict, Any
from chamelefx.ops import guardrails as GR
from chamelefx.ops import watchdog as WD

router = APIRouter()

@router.post("/risk/record_pnl")
def risk_record_pnl(symbol: str = Body(..., embed=True),
                    pnl: float = Body(..., embed=True),
                    equity: float = Body(0.0, embed=True)):
    # Track equity if provided
    if equity and equity > 0:
        GR.set_equity(equity)
    return GR.record_pnl(symbol, pnl, equity or 0.0)

@router.get("/risk/state")
def risk_state():
    from chamelefx.ops.guardrails import _load_state as _ls  # type: ignore
    s = _ls()
    return {"ok": True, "state": s}

@router.post("/risk/pretrade_gate")
def risk_pretrade_gate(symbol: str = Body(..., embed=True),
                       side: str = Body("buy", embed=True),
                       weight: float = Body(0.0, embed=True)):
    return GR.pretrade_gate({"symbol": symbol, "side": side, "weight": weight})

@router.post("/risk/reset_today")
def risk_reset_today(symbol: str | None = Body(None, embed=True)):
    return WD.reset_today(symbol)

@router.post("/risk/drift_flag")
def risk_drift_flag(current: Dict[str, float] = Body(..., embed=True),
                    target: Dict[str, float] = Body(..., embed=True),
                    drift_bps: float = Body(100.0, embed=True)):
    return GR.portfolio_drift_flag(current, target, drift_bps)
'''

def include_router_in_server():
    srv = API / "server.py"
    if not srv.exists(): 
        return
    txt = srv.read_text(encoding="utf-8")
    changed = False
    imp = "from app.api.ext_risk_plus import router as risk_plus_router"
    if imp not in txt:
        txt = imp + "\n" + txt
        changed = True
    if "app.include_router(risk_plus_router)" not in txt:
        txt += "\napp.include_router(risk_plus_router)\n"
        changed = True
    if changed:
        srv.write_text(txt, encoding="utf-8")

def main():
    ensure_cfg()
    write(OPS / "guardrails.py", GUARDRAILS)
    write(OPS / "watchdog.py",  WATCHDOG)
    write(API / "ext_risk_plus.py", EXT_RISK)
    include_router_in_server()
    DATA.mkdir(parents=True, exist_ok=True)
    print("[BundleC] Risk Enhancements installed & API wired.")

if __name__ == "__main__":
    main()
