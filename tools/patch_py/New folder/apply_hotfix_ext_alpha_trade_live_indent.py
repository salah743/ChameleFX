# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time, shutil, textwrap

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TARGET = os.path.join(ROOT, "app", "api", "ext_alpha_trade_live.py")

CONTENT = textwrap.dedent("""\
from __future__ import annotations
from fastapi import APIRouter, Body
from typing import Dict, Any
import importlib

router = APIRouter()

def W():
    # late import to avoid circulars
    return importlib.import_module("chamelefx.alpha.weighting")

def BR():
    # orders bridge path
    return importlib.import_module("chamelefx.app.api.orders_bridge")

@router.post("/alpha/trade_live")
def alpha_trade_live(
    symbol: str = Body(..., embed=True),
    side: str = Body("buy", embed=True),
    method: str = Body("kelly", embed=True),
    signal: float = Body(1.0, embed=True),
    clamp: float = Body(0.35, embed=True),
    params: Dict[str, Any] = Body({}, embed=True),
):
    # compute weight from signal
    try:
        w = float(W().weight_from_signal(signal, method=method, clamp=clamp, params=params))
    except Exception:
        w = 0.0
    # place order
    try:
        return BR().place(symbol=symbol, side=side, weight=w, order_type="market")
    except Exception as e:
        return {"ok": False, "error": "bridge_failed", "detail": repr(e)}

@router.post("/alpha/trade_live_biased")
def alpha_trade_live_biased(
    symbol: str = Body(..., embed=True),
    side: str = Body("buy", embed=True),
    base_weight: float = Body(0.10, embed=True),
    bias: float = Body(1.0, embed=True),
):
    try:
        w = float(base_weight) * float(bias)
    except Exception:
        w = 0.0
    try:
        return BR().place(symbol=symbol, side=side, weight=w, order_type="market")
    except Exception as e:
        return {"ok": False, "error": "bridge_failed", "detail": repr(e)}
""")

def main():
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    if os.path.exists(TARGET):
        shutil.copy2(TARGET, TARGET + f".bak.{int(time.time())}")
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write(CONTENT)
    print("[OK] ext_alpha_trade_live.py rewritten cleanly")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
