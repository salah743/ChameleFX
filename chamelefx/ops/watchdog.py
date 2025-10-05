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
