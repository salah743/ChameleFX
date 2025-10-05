# -*- coding: utf-8 -*-
import os, time, shutil, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "chamelefx" / "app" / "api" / "orders_bridge.py"

CONTENT = textwrap.dedent("""\
from __future__ import annotations
from typing import Any, Dict

def place(symbol: str, side: str, weight: float = 0.0, order_type: str = "market") -> Dict[str, Any]:
    \"\"\"Stub order bridge: in real system this routes to MT5/live execution.\"\"\"
    return {
        "ok": True,
        "symbol": symbol,
        "side": side,
        "weight": weight,
        "order_type": order_type,
        "status": "ACCEPTED",
    }
""")

def main():
    os.makedirs(TARGET.parent, exist_ok=True)
    if TARGET.exists():
        shutil.copy2(TARGET, TARGET.with_suffix(f".bak.{int(time.time())}.py"))
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(CONTENT)
    print("[OK] orders_bridge stub created at", TARGET)

if __name__ == "__main__":
    raise SystemExit(main())
