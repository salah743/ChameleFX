# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, time, shutil, math
from typing import Any, Dict, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CFX  = os.path.join(ROOT, "chamelefx")
APP  = os.path.join(CFX, "app", "api")
RUN  = os.path.join(CFX, "runtime")
CFG_PATH = os.path.join(CFX, "config.json")
ORDERS_FILE = os.path.join(RUN, "orders_recent.json")

def _backup(path: str):
    if os.path.exists(path):
        shutil.copy2(path, path + f".bak.{int(time.time())}")

def _ensure_dirs():
    os.makedirs(os.path.dirname(ORDERS_FILE), exist_ok=True)

def _load_cfg() -> Dict[str, Any]:
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _append_recent(entry: Dict[str, Any]) -> None:
    """Append order echo into runtime file (best-effort)."""
    try:
        _ensure_dirs()
        data = {"orders": []}
        if os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = {"orders": []}
        data.setdefault("orders", []).append(entry)
        tmp = ORDERS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, ORDERS_FILE)
    except Exception:
        pass

# -------- MT5 integration (lazy, optional) -----------------------------------

_MT5 = None
_MT5_READY = None

def _mt5_module():
    global _MT5
    if _MT5 is not None:
        return _MT5
    try:
        # Your project previously had this module; if it doesn’t exist we’ll fallback.
        import importlib
        _MT5 = importlib.import_module("chamelefx.integrations.mt5_client")
    except Exception:
        _MT5 = None
    return _MT5

def _mt5_ensure_started(cfg: Dict[str, Any]) -> bool:
    """
    Try to start/connect MT5 exactly once per process; cache readiness.
    Expected mt5 config fields (already in your config.json):
      enabled, account_id, server, path, timeout_sec, retry{attempts,backoff_sec}
    """
    global _MT5_READY
    if _MT5_READY is not None:
        return _MT5_READY

    mod = _mt5_module()
    if mod is None:
        _MT5_READY = False
        return False

    mt5_cfg = (cfg.get("mt5") or {})
    if not mt5_cfg.get("enabled", False):
        _MT5_READY = False
        return False

    attempts = int((mt5_cfg.get("retry") or {}).get("attempts", 3))
    backoff  = float((mt5_cfg.get("retry") or {}).get("backoff_sec", 1.0))
    for i in range(max(1, attempts)):
        try:
            # Your mt5_client should provide something like ensure_started(**kwargs)
            # If your naming differs, adapt here.
            ok = bool(mod.ensure_started(
                account_id=mt5_cfg.get("account_id",""),
                server=mt5_cfg.get("server",""),
                path=mt5_cfg.get("path",""),
                timeout_sec=int(mt5_cfg.get("timeout_sec", 5))
            ))
            if ok:
                _MT5_READY = True
                return True
        except Exception:
            pass
        time.sleep(backoff)
    _MT5_READY = False
    return False

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))

def _weight_to_lots(symbol: str, weight: float, cfg: Dict[str, Any]) -> float:
    """
    Convert dimensionless weight (-1..+1) to MT5 lots.
    Heuristic:
      - base lot for |weight|=0.10 is 0.10 lots
      - scale linearly, clamp to [0.01, 5.00]
    If you have a more exact risk-based sizing, plug it in here (e.g. ATR, pip value).
    """
    w = abs(float(weight))
    # configurable multiplier if you want: cfg["execution"]["lot_scale"] etc.
    lot_scale = float((((cfg.get("execution") or {}).get("router") or {}).get("lot_scale", 1.0)))
    lots = _clamp((w / 0.10) * 0.10 * lot_scale, 0.01, 5.0)  # 0.1 weight -> 0.10 lots
    return float(lots)

def _mt5_place_market(symbol: str, side: str, lots: float) -> Dict[str, Any]:
    """
    Place MT5 market order. Returns a uniform dict.
    Expects chamelefx.integrations.mt5_client to expose: market_order(symbol, lots, side)
      - side: "buy" or "sell"
      - returns dict with {ok, ticket?, error?}
    """
    mod = _mt5_module()
    if mod is None:
        return {"ok": False, "error": "mt5_module_missing"}

    try:
        resp = mod.market_order(symbol=symbol, lots=float(lots), side=side)
        if resp and resp.get("ok"):
            return {"ok": True, "ticket": resp.get("ticket"), "raw": resp}
        return {"ok": False, "error": "mt5_rejected", "raw": resp}
    except Exception as e:
        return {"ok": False, "error": "mt5_exception", "detail": repr(e)}

# -------- Public API ----------------------------------------------------------

def place(symbol: str,
          side: str = "buy",
          weight: float = 0.0,
          order_type: str = "market",
          price: Optional[float] = None,
          meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Unified order entry:
      - runs guardrails (best-effort)
      - if MT5 enabled + available: route to MT5
      - else: local echo (dry ACK) for dev
      - always appends to runtime/orders_recent.json
    """
    meta = meta or {}
    body = {
        "symbol": symbol,
        "side": side,
        "weight": float(weight),
        "order_type": order_type,
        "price": price,
        "ts": time.time(),
        "meta": meta
    }

    # Guardrails pre-trade gate (best-effort)
    try:
        from chamelefx.ops.guardrails import pretrade_gate as _gate
        g = _gate(dict(body))
        if not g.get("ok") or g.get("blocked"):
            result = {"ok": False, "blocked": True, "reason": g.get("reason","guardrails"), "state": g}
            _append_recent({"status": "blocked", **body, "result": result})
            return result
        # allow guardrails to adjust weight/order params
        body = g.get("body", body)
    except Exception:
        pass

    cfg = _load_cfg()
    used_live = False
    mt5_ticket = None
    mt5_raw = None

    # Live path if possible
    if _mt5_ensure_started(cfg) and order_type.lower() == "market":
        lots = _weight_to_lots(symbol, float(body.get("weight", 0.0)), cfg)
        side_norm = "buy" if str(body.get("side","buy")).lower().startswith("b") else "sell"
        live = _mt5_place_market(symbol=symbol, side=side_norm, lots=lots)
        if live.get("ok"):
            used_live = True
            mt5_ticket = live.get("ticket")
            mt5_raw = live.get("raw")
            result = {
                "ok": True,
                "live": True,
                "symbol": symbol,
                "side": side_norm,
                "weight": float(body.get("weight", 0.0)),
                "lots": lots,
                "ticket": mt5_ticket
            }
            _append_recent({"status": "live_sent", **body, "lots": lots, "ticket": mt5_ticket, "result": result})
            return result
        else:
            # If MT5 fails, fall through to echo-ack (dev-safe) but mark as live_failed
            meta["live_error"] = live

    # Dev echo path (or fallback)
    result = {
        "ok": True,
        "live": False,
        "symbol": symbol,
        "side": side,
        "weight": float(body.get("weight", 0.0)),
        "order_type": order_type,
        "ticket": None,
        "note": "echo (MT5 disabled/unavailable)"
    }
    _append_recent({"status": "echo", **body, "result": result})
    return result

# ------------------------------------------------------------------------------

def _install():
    target = os.path.join(CFX, "app", "api", "orders_bridge.py")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    _backup(target)
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(open(__file__, "r", encoding="utf-8").read().split("# -*- coding: utf-8 -*-",1)[1])  # self-embed write
    print("[OK] orders_bridge.py installed ->", target)

if __name__ == "__main__":
    _install()
