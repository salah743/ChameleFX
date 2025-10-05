from __future__ import annotations
from pathlib import Path
import json, time, platform

from chamelefx.utils.atomic_json import read_json
from chamelefx.utils.validator import validate_and_fix_config

ROOT = Path(__file__).resolve().parents[1]
RUN  = ROOT / "runtime"

def file_info(p: Path):
    try:
        st = p.stat()
        return {"exists": True, "size": st.st_size, "mtime": st.st_mtime}
    except Exception:
        return {"exists": False}

def snapshot() -> dict:
    cfgp = ROOT / "config.json"
    cfg  = validate_and_fix_config(cfgp)
    files = {
        "alpha_monitor": file_info(RUN/"alpha_monitor.json"),
        "regime_sizing": file_info(RUN/"regime_sizing.json"),
        "parity_last":   file_info(RUN/"parity_last.json"),
        "router_costs":  file_info(RUN/"router_costs.json"),
        "orders_outbox": file_info(RUN/"orders_outbox.json"),
    }
    return {
        "ok": True,
        "ts": time.time(),
        "meta": {"host": platform.node(), "py": platform.python_version()},
        "config_digest": cfg,
        "files": files
    }

def health() -> dict:
    try:
        ok = True
        issues = []
        # basic checks
        if not (ROOT/"config.json").exists():
            ok = False; issues.append("missing_config_json")
        for need in [RUN, RUN/"reports", RUN/"logs"]:
            if not need.exists():
                ok = False; issues.append(f"missing_dir:{need.name}")
        return {"ok": ok, "issues": issues, "ts": time.time()}
    except Exception as e:
        return {"ok": False, "error": repr(e), "ts": time.time()}
