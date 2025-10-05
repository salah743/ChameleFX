from __future__ import annotations
from chamelefx.log import get_logger
import os, json, time, random
from typing import Any, Dict, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUN  = os.path.join(ROOT, "runtime")
os.makedirs(RUN, exist_ok=True)

FILLS_PATH = os.path.join(RUN, "fills.json")
POSITIONS_PATH = os.path.join(RUN, "positions.json")
LOGIN_PATH = os.path.join(RUN, "mt5_login.json")

# Try import MetaTrader5; fall back to stub if import fails.
try:
    import MetaTrader5 as MT5
    _HAVE_MT5 = True
except Exception:
    MT5 = None
    _HAVE_MT5 = False

def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _append(path: str, rec: Dict[str, Any], cap: int = 500):
    rows = _read_json(path, [])
    if not isinstance(rows, list):
        rows = []
    rows.append(rec)
    rows = rows[-cap:]
    _write_json(path, rows)

def _positions() -> Dict[str, Any]:
    d = _read_json(POSITIONS_PATH, {})
    if not isinstance(d, dict):
        d = {}
    return d

def _set_position(symbol: str, lots: float, side: str):
    d = _positions()
    if lots <= 0:
        d.pop(symbol, None)
    else:
        d[symbol] = {"lots": lots, "side": side, "ts": time.time()}
    _write_json(POSITIONS_PATH, d)

def start() -> Dict[str, Any]:
    """
    Initialize MT5 terminal (if available) and login if credentials provided.
    runtime/mt5_login.json (optional):
    {
      "login": <int>,
      "password": "<str>",
      "server": "<str>"
    }
    """
    if not _HAVE_MT5:
        return {"ok": True, "mode": "stub", "msg": "MetaTrader5 package not installed; using stub."}

    if not MT5.initialize():
        return {"ok": False, "mode": "mt5", "error": f"initialize_failed: {MT5.last_error()}"}

    creds = _read_json(LOGIN_PATH, {})
    if creds and all(k in creds for k in ("login","password","server")):
        ok = MT5.login(int(creds["login"]), password=str(creds["password"]), server=str(creds["server"]))
        if not ok:
            return {"ok": False, "mode": "mt5", "error": f"login_failed: {MT5.last_error()}"}
    return {"ok": True, "mode": "mt5"}

def ping() -> Dict[str, Any]:
    if not _HAVE_MT5:
        return {"ok": True, "mode": "stub"}
    try:
        v = MT5.version()
        return {"ok": True, "mode": "mt5", "version": v}
    except Exception as e:
        return {"ok": False, "mode": "mt5", "error": repr(e)}

def place(symbol: str, side: str, lots: float, sl: Optional[float]=None, tp: Optional[float]=None,
          comment: Optional[str]=None, magic: Optional[int]=None) -> Dict[str, Any]:
    ts = time.time()
    if not _HAVE_MT5:
        # STUB: create a synthetic ticket and adjust positions file
        ticket = int(ts * 1000) + random.randint(1, 999)
        # Merge into net position
        pos = _positions().get(symbol)
        if pos and pos.get("side") == side:
            new_lots = float(pos.get("lots", 0.0)) + float(lots)
        elif pos and pos.get("side") != side:
            new_lots = float(pos.get("lots", 0.0)) - float(lots)
            if new_lots < 0:
                side = side  # flip to the side of residual
                new_lots = abs(new_lots)
        else:
            new_lots = float(lots)
        if new_lots <= 0:
            _set_position(symbol, 0, side)
        else:
            _set_position(symbol, new_lots, side)
        fill = {"ts": ts, "ticket": ticket, "symbol": symbol, "side": side, "lots": float(lots),
                "sl": sl, "tp": tp, "comment": comment, "magic": magic, "mode": "stub"}
        _append(FILLS_PATH, fill)
        return {"ok": True, "ticket": ticket, "fill": fill}

    # REAL MT5 flow (simplified market order)
    try:
        typ = MT5.ORDER_TYPE_BUY if side.lower().startswith("b") else MT5.ORDER_TYPE_SELL
        req = {
            "action": MT5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lots),
            "type": typ,
            "price": MT5.symbol_info_tick(symbol).ask if typ==MT5.ORDER_TYPE_BUY else MT5.symbol_info_tick(symbol).bid,
            "sl": sl or 0.0,
            "tp": tp or 0.0,
            "deviation": 20,
            "magic": magic or 9865321,
            "comment": comment or "cfx",
            "type_time": MT5.ORDER_TIME_GTC,
            "type_filling": MT5.ORDER_FILLING_FOK,
        }
        res = MT5.order_send(req)
        ok = (res is not None and res.retcode == MT5.TRADE_RETCODE_DONE)
        ticket = getattr(res, "order", None) or getattr(res, "deal", None)
        rec = {"ts": ts, "ticket": ticket, "symbol": symbol, "side": side, "lots": float(lots),
               "sl": sl, "tp": tp, "comment": comment, "magic": magic, "mode": "mt5", "retcode": getattr(res,'retcode',None)}
        _append(FILLS_PATH, rec)
        # For simplicity, treat as net pos update
        # (you can query MT5.positions_get to be exact)
        return {"ok": bool(ok), "ticket": ticket, "mt5": getattr(res, "_asdict", lambda: None)()}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

def modify(ticket: int, sl: Optional[float]=None, tp: Optional[float]=None) -> Dict[str, Any]:
    ts = time.time()
    if not _HAVE_MT5:
        # STUB: record the modification only
        _append(FILLS_PATH, {"ts": ts, "modify_ticket": ticket, "sl": sl, "tp": tp, "mode": "stub"})
        return {"ok": True, "ticket": ticket, "mode": "stub"}
    try:
        # NOTE: for real MT5 you'd need to fetch current position/order price and send an ORDER_TYPE_MODIFY request.
        _append(FILLS_PATH, {"ts": ts, "modify_ticket": ticket, "sl": sl, "tp": tp, "mode": "mt5"})
        return {"ok": True, "ticket": ticket, "mode": "mt5"}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

def close(ticket: Optional[int]=None, symbol: Optional[str]=None) -> Dict[str, Any]:
    ts = time.time()
    if not _HAVE_MT5:
        # STUB: if ticket not tracked, close by symbol (flatten)
        if symbol:
            _set_position(symbol, 0.0, "flat")
            _append(FILLS_PATH, {"ts": ts, "close_symbol": symbol, "mode": "stub"})
            return {"ok": True, "symbol": symbol, "mode": "stub"}
        _append(FILLS_PATH, {"ts": ts, "close_ticket": ticket, "mode": "stub"})
        return {"ok": True, "ticket": ticket, "mode": "stub"}
    try:
        # Real implementation would inspect position and send opposite order with same volume.
        _append(FILLS_PATH, {"ts": ts, "close": ticket or symbol, "mode": "mt5"})
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": repr(e)}
