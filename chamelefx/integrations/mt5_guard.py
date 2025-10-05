
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import json, time
from chamelefx.log import get_logger
from chamelefx.utils.filelock import file_lock
from chamelefx.utils.secrets import get_mt5_credentials

log = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "chamelefx" / "runtime"
OUTBOX = RUNTIME / "orders_outbox.json"

def _read_json(p: Path, default):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default

def _write_json_atomic(p: Path, obj: Any):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def status() -> Dict[str, Any]:
    try:
        login, pw, server = get_mt5_credentials()
        return {"ok": True, "mt5": {"login": bool(login), "server": bool(server), "password_set": bool(pw)}}
    except Exception:
        log.exception("status failed"); return {"ok": False}

def heartbeat() -> Dict[str, Any]:
    try: return {"ok": True, "ts": int(time.time())}
    except Exception:
        log.exception("heartbeat failed"); return {"ok": False}

def reconnect() -> Dict[str, Any]:
    try: return {"ok": True, "reconnected": True}
    except Exception:
        log.exception("reconnect failed"); return {"ok": False}

def outbox_append(order: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with file_lock(OUTBOX):
            ob = _read_json(OUTBOX, {"pending": [], "sent": []})
            ob["pending"].append(order)
            _write_json_atomic(OUTBOX, ob)
        return {"ok": True, "queued": True}
    except Exception:
        log.exception("outbox_append failed"); return {"ok": False}
