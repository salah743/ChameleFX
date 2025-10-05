# tools/patch_py/apply_bundle_Q_mt5_resilience.py
from __future__ import annotations
from pathlib import Path
import re, json

ROOT = Path(__file__).resolve().parents[2]
APP  = ROOT / "app" / "api"
CFX  = ROOT / "chamelefx"
RUN  = CFX / "runtime"
RUN.mkdir(parents=True, exist_ok=True)

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.strip() + "\n", encoding="utf-8")
    print("[Q] wrote", p)

# ----------------- mt5 guard (wrapper) -----------------
GUARD = r"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import json, time, threading

ROOT = Path(__file__).resolve().parents[1]
RUN  = ROOT / "runtime"
RUN.mkdir(parents=True, exist_ok=True)

OUTBOX = RUN / "orders_outbox.json"
LOGF   = RUN / "exec_log.jsonl"

# -------- atomic json helpers --------
def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _atomic_write(p: Path, obj):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(p)

def _append_log(row: dict):
    try:
        LOGF.parent.mkdir(parents=True, exist_ok=True)
        LOGF.open("a", encoding="utf-8").write(json.dumps(row) + "\n")
    except Exception:
        pass

# -------- load client (optional) --------
_mt5 = None
try:
    from chamelefx.integrations import mt5_client as _mt5
except Exception:
    _mt5 = None

_state = {
    "connected": False,
    "last_ping_ok": False,
    "last_error": "",
    "last_ping_ts": 0.0,
    "account": {}
}

_lock = threading.Lock()

def _ensure_outbox():
    if not OUTBOX.exists():
        _atomic_write(OUTBOX, {"pending": [], "sent": []})

def _client_order_id(order: dict) -> str:
    # idempotency key: symbol/side/qty/price/timebucket
    bkt = int(time.time() // 30)  # 30s bucket to reduce duplicates from retries
    return order.get("client_order_id") or f"{order.get('symbol','?')}-{order.get('side','?')}-{order.get('qty',0)}-{order.get('price','')}-{bkt}"

def status() -> dict:
    with _lock:
        s = dict(_state)
    return {"ok": True, **s, "mt5_available": bool(_mt5)}

def connect() -> dict:
    with _lock:
        if _mt5 is None:
            _state.update({"connected": False, "last_error": "mt5_client not available"})
            return {"ok": False, "error": "mt5_unavailable"}
        try:
            ok = _mt5.connect()
            _state["connected"] = bool(ok)
            _state["last_error"] = "" if ok else "connect_failed"
            return {"ok": bool(ok)}
        except Exception as e:
            _state.update({"connected": False, "last_error": repr(e)})
            return {"ok": False, "error": "exception", "detail": repr(e)}

def disconnect() -> dict:
    with _lock:
        try:
            if _mt5 and hasattr(_mt5, "disconnect"):
                _mt5.disconnect()
            _state["connected"] = False
            return {"ok": True}
        except Exception as e:
            _state["last_error"] = repr(e)
            return {"ok": False, "error": repr(e)}

def ping() -> dict:
    with _lock:
        if _mt5 is None:
            _state.update({"last_ping_ok": False, "last_error": "mt5_unavailable", "last_ping_ts": time.time()})
            return {"ok": False, "mt5": "unavailable"}
        try:
            acct = _mt5.account_summary()
            _state["account"] = acct or {}
            _state["last_ping_ok"] = True if acct else False
            _state["connected"] = True if acct else _state["connected"]
            _state["last_ping_ts"] = time.time()
            return {"ok": bool(acct), "account": acct}
        except Exception as e:
            _state["last_ping_ok"] = False
            _state["last_error"] = repr(e)
            _state["last_ping_ts"] = time.time()
            # try a reconnect once
            try:
                if _mt5 and hasattr(_mt5, "connect"):
                    _mt5.connect()
            except Exception:
                pass
            return {"ok": False, "error": repr(e)}

def _send_mt5(order: dict) -> dict:
    # Only called under lock
    if _mt5 is None:
        return {"ok": False, "error": "mt5_unavailable"}
    side = order.get("side","buy").lower()
    typ  = order.get("type","market").lower()
    sym  = order.get("symbol","")
    qty  = float(order.get("qty",0))
    price = order.get("price", None)
    sl = order.get("sl", None)
    tp = order.get("tp", None)

    if typ == "market":
        return _mt5.place_market(symbol=sym, side=side, qty=qty, sl=sl, tp=tp)
    elif typ in ("limit","stop","stop_limit","stoplimit"):
        return _mt5.place_pending(symbol=sym, side=side, qty=qty, price=price, typ=typ, sl=sl, tp=tp)
    else:
        return {"ok": False, "error": f"unsupported_type:{typ}"}

def _persist_outbox(ob):
    _atomic_write(OUTBOX, ob)

def _load_outbox() -> dict:
    _ensure_outbox()
    return _read_json(OUTBOX, {"pending": [], "sent": []})

def _already_sent(ob: dict, coid: str) -> bool:
    for r in ob.get("sent", []):
        if r.get("client_order_id") == coid:
            return True
    return False

def place_order(order: dict, attempts: int = 3) -> dict:
    """
    Crash-safe, idempotent place:
    1) Write to outbox.pending (if not already there)
    2) Try send with backoff; on ok -> move to sent with broker ids
    """
    with _lock:
        coid = _client_order_id(order)
        order["client_order_id"] = coid
        ob = _load_outbox()
        if _already_sent(ob, coid):
            return {"ok": True, "status": "duplicate_ignored", "client_order_id": coid}

        # ensure it's in pending (dedupe)
        pend = ob.get("pending", [])
        if not any(p.get("client_order_id")==coid for p in pend):
            pend.append(order)
            ob["pending"] = pend
            _persist_outbox(ob)

        # try send
        backoff = 0.3
        last_err = ""
        for i in range(attempts):
            try:
                res = _send_mt5(order)
                if res and res.get("ok"):
                    # move to sent
                    ob = _load_outbox()  # reload fresh
                    ob["pending"] = [p for p in ob.get("pending", []) if p.get("client_order_id") != coid]
                    sent_row = dict(order)
                    sent_row.update({"result": res, "ts": time.time(), "sent": True})
                    ob.setdefault("sent", []).append(sent_row)
                    _persist_outbox(ob)
                    _append_log({"ts": time.time(), "event":"order_sent", "coid": coid, "symbol": order.get("symbol"), "side": order.get("side"), "qty": order.get("qty"), "res": res})
                    return {"ok": True, "client_order_id": coid, "result": res}
                last_err = repr(res)
            except Exception as e:
                last_err = repr(e)
            time.sleep(backoff)
            backoff *= 2.0

        _append_log({"ts": time.time(), "event":"order_failed", "coid": coid, "error": last_err})
        return {"ok": False, "client_order_id": coid, "error": last_err}

def cancel_order(broker_order_id: Any) -> dict:
    with _lock:
        try:
            if _mt5 is None:
                return {"ok": False, "error": "mt5_unavailable"}
            res = _mt5.cancel_order(broker_order_id)
            _append_log({"ts": time.time(), "event":"order_cancel", "id": broker_order_id, "res": res})
            return res or {"ok": False}
        except Exception as e:
            return {"ok": False, "error": repr(e)}

def outbox() -> dict:
    with _lock:
        ob = _load_outbox()
        return {"ok": True, "pending": ob.get("pending", []), "sent_count": len(ob.get("sent", []))}

def flush_pending(max_items: int = 10) -> dict:
    with _lock:
        ob = _load_outbox()
        pend = ob.get("pending", [])[:max_items]
        results = []
        for order in pend:
            results.append(place_order(order))
        return {"ok": True, "results": results}
"""

# ----------------- API endpoints -----------------
EXT = r"""
from __future__ import annotations
from fastapi import APIRouter, Body, Query
from chamelefx.integrations import mt5_guard as g

router = APIRouter()

@router.get("/mt5/status")
def mt5_status():
    return g.status()

@router.post("/mt5/reconnect")
def mt5_reconnect():
    return g.connect()

@router.get("/mt5/heartbeat")
def mt5_heartbeat():
    # ping also auto-reconnects inside on error
    return g.ping()

@router.post("/mt5/order/place")
def mt5_order_place(payload: dict = Body(...)):
    """
    payload: {symbol, side, qty, type='market'|'limit'|'stop'|'stop_limit', price?, sl?, tp?, client_order_id?}
    """
    return g.place_order(payload)

@router.post("/mt5/order/cancel")
def mt5_order_cancel(broker_order_id: str = Body(..., embed=True)):
    return g.cancel_order(broker_order_id)

@router.get("/mt5/outbox")
def mt5_outbox():
    return g.outbox()

@router.post("/mt5/outbox/flush")
def mt5_outbox_flush(max_items: int = Body(10, embed=True)):
    return g.flush_pending(max_items=max_items)
"""

def patch_server():
    sp = APP / "server.py"
    txt = sp.read_text(encoding="utf-8")
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    future, rest = (m.group(1), m.group(2)) if m else ("", txt)
    imp = "from app.api.ext_mt5_resilience import router as mt5_resilience_router"
    inc = "app.include_router(mt5_resilience_router)"
    if imp not in rest:
        rest = imp + "\n" + rest
    if inc not in rest:
        rest += "\n" + inc + "\n"
    (APP / "server.py").write_text(future + rest, encoding="utf-8")
    print("[Q] server.py patched (mt5_resilience_router)")

def main():
    write(CFX / "integrations" / "mt5_guard.py", GUARD)
    write(APP / "ext_mt5_resilience.py", EXT)
    patch_server()
    print("[Q] Bundle Q installed.")

if __name__ == "__main__":
    main()
