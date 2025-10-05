from __future__ import annotations
from chamelefx.log import get_logger
from typing import List, Dict, Any
import time
import MetaTrader5 as mt5

def _connect():
    if not mt5.initialize():
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")

def open_orders() -> List[Dict[str, Any]]:
    """Return currently open orders (pending orders)."""
    _connect()
    orders = mt5.orders_get()
    out=[]
    if orders:
        for o in orders:
            out.append({
                "id": str(o.ticket),
                "symbol": o.symbol,
                "side": "buy" if o.type % 2 == 0 else "sell",
                "qty": o.volume_current,
                "price": o.price_open,
                "ts": o.time_setup,
            })
    mt5.shutdown()
    return out

def recent_fills(n: int=20) -> List[Dict[str, Any]]:
    """Return last n closed deals/fills."""
    _connect()
    deals = mt5.history_deals_get(time.time()-7*86400, time.time())
    out=[]
    if deals:
        for d in sorted(deals, key=lambda x: x.time, reverse=True)[:n]:
            out.append({
                "id": str(d.ticket),
                "symbol": d.symbol,
                "side": "buy" if d.type % 2 == 0 else "sell",
                "qty": d.volume,
                "price": d.price,
                "ts": d.time,
            })
    mt5.shutdown()
    return out

def cancel_order(order_id: str) -> Dict[str, Any]:
    """Cancel an open order by ticket."""
    _connect()
    res = mt5.order_send({
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": int(order_id)
    })
    mt5.shutdown()
    return {"ok": res.retcode == mt5.TRADE_RETCODE_DONE, "order_id": order_id}

def replace_order(order_id: str, new_qty: float) -> Dict[str, Any]:
    """Simplified: cancel+recreate (stub)."""
    # Full replace requires capturing original details and resending
    return {"ok": False, "note": "Replace not implemented yet"}
