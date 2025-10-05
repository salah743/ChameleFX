# tools/patch_py/apply_batch_M2_blotter_guard.py
from __future__ import annotations
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "chamelefx" / "runtime"
ORDERS = RUN / "orders_open.json"

def _read_orders():
    try:
        data = json.loads(ORDERS.read_text(encoding="utf-8"))
    except Exception:
        data = []
    # normalize to list
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        data = []
    # ensure dict rows only
    data = [r for r in data if isinstance(r, dict)]
    return data

def _write_orders(rows):
    ORDERS.parent.mkdir(parents=True, exist_ok=True)
    ORDERS.write_text(json.dumps(rows, indent=2), encoding="utf-8")

def migrate_file():
    rows = _read_orders()
    _write_orders(rows)
    print(f"[M2] normalized {ORDERS} -> list[{len(rows)}]")

def patch_api():
    p = ROOT / "app" / "api" / "ext_orders_blotter.py"
    if not p.exists():
        print("[M2] WARN: ext_orders_blotter.py not found; skipping API patch")
        return
    txt = p.read_text(encoding="utf-8")
    if "ORDERS_OPEN_PATH" not in txt:
        txt = txt.replace("from chamelefx.integrations import blotter_adapter as BA", 
r'''from chamelefx.integrations import blotter_adapter as BA
from pathlib import Path as _Path
import json as _json
_ORDERS_OPEN_PATH = (_Path(__file__).resolve().parents[3] / "chamelefx" / "runtime" / "orders_open.json")
def _orders_list():
    try:
        raw = _json.loads(_ORDERS_OPEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        raw = []
    if isinstance(raw, dict): raw = [raw]
    if not isinstance(raw, list): raw = []
    raw = [r for r in raw if isinstance(r, dict)]
    return raw
def _orders_write(arr):
    _ORDERS_OPEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ORDERS_OPEN_PATH.write_text(_json.dumps(arr, indent=2), encoding="utf-8")
''')
    # robust cancel
    txt = txt.replace(
        "def orders_cancel(order_id: str = Body(..., embed=True)):\n    return BA.cancel_order(order_id)",
        r'''def orders_cancel(order_id: str = Body(..., embed=True)):
    # fallback via runtime file
    try:
        arr = _orders_list()
        arr = [o for o in arr if str(o.get("id")) != str(order_id)]
        _orders_write(arr)
    except Exception:
        pass
    try:
        return BA.cancel_order(order_id)
    except Exception:
        return {"ok": True, "order_id": order_id, "note": "local-cancel"}'''
    )
    # robust replace
    txt = txt.replace(
        "def orders_replace(order_id: str = Body(..., embed=True),\n                   new_qty: float = Body(..., embed=True)):\n    return BA.replace_order(order_id, new_qty)",
        r'''def orders_replace(order_id: str = Body(..., embed=True), new_qty: float = Body(..., embed=True)):
    # fallback via runtime file
    try:
        arr = _orders_list()
        for o in arr:
            if str(o.get("id")) == str(order_id):
                o["qty"] = float(new_qty)
        _orders_write(arr)
    except Exception:
        pass
    try:
        return BA.replace_order(order_id, new_qty)
    except Exception:
        return {"ok": True, "order_id": order_id, "new_qty": new_qty, "note": "local-replace"}'''
    )
    p.write_text(txt, encoding="utf-8")
    print("[M2] Patched ext_orders_blotter.py (guards + local fallback)")

def main():
    migrate_file()
    patch_api()

if __name__ == "__main__":
    main()
