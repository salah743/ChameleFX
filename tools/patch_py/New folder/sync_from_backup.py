# -*- coding: utf-8 -*-
"""
KO Sync: Copy only missing required files from backup → live,
without bringing junk back.

Usage:
  cd D:\ChameleFX
  .\py-portable\python\python.exe .\tools\patch_py\sync_from_backup.py
  # optional:
  .\py-portable\python\python.exe .\tools\patch_py\sync_from_backup.py --force

Default roots:
  LIVE   = D:\ChameleFX
  BACKUP = D:\ChameneFX Backup   (note the space; script tries both spellings)
"""
from __future__ import annotations
import argparse
import filecmp
import json
import os
import re
import shutil
from pathlib import Path
from typing import List, Tuple

# --- Roots -------------------------------------------------------------
LIVE = Path(r"D:\ChameleFX")
# User wrote "ChameneFX Backup" (with e). Try both spellings safely:
BACKUP_CANDIDATES = [
    Path(r"D:\ChameneFX Backup"),
    Path(r"D:\ChameleFX Backup"),
]

# choose the first existing backup path
for _p in BACKUP_CANDIDATES:
    if _p.exists():
        BACKUP = _p
        break
else:
    BACKUP = BACKUP_CANDIDATES[0]  # default

REPORT = LIVE / "sync_report.txt"

# --- Required minimal tree (only the stuff that must exist) ------------
REQUIRED_DIRS = [
    LIVE / "app" / "api",
    LIVE / "chamelefx",
    LIVE / "chamelefx" / "alpha",
    LIVE / "chamelefx" / "analytics",
    LIVE / "chamelefx" / "execution",
    LIVE / "chamelefx" / "portfolio",
    LIVE / "chamelefx" / "router",
    LIVE / "chamelefx" / "ui",
    LIVE / "chamelefx" / "performance",
    LIVE / "chamelefx" / "validation",
    LIVE / "chamelefx" / "databank",
    LIVE / "chamelefx" / "integrations",
    LIVE / "chamelefx" / "runtime",
]

# Files we expect, with “relative path from each root”
REQUIRED_FILES: List[Path] = [
    Path("app/api/server.py"),

    Path("app/api/ext_orders_blotter.py"),
    Path("app/api/ext_router_stats.py"),
    Path("app/api/ext_alpha_features.py"),
    Path("app/api/ext_alpha_weight.py"),
    Path("app/api/ext_alpha_trade_live.py"),
    Path("app/api/ext_perf_metrics.py"),

    Path("chamelefx/manager.py"),
    Path("chamelefx/setup_gui.py"),
    Path("chamelefx/config.json"),

    Path("chamelefx/alpha/features.py"),
    Path("chamelefx/alpha/ensemble.py"),

    Path("chamelefx/analytics/decay.py"),
    Path("chamelefx/analytics/diagnostics.py"),

    Path("chamelefx/execution/quality.py"),
    Path("chamelefx/execution/twap.py"),

    Path("chamelefx/portfolio/sizing.py"),
    Path("chamelefx/portfolio/optimizer.py"),

    Path("chamelefx/router/scorer.py"),

    Path("chamelefx/ui/dashboard.py"),
    Path("chamelefx/ui/alpha_tab.py"),
    Path("chamelefx/ui/portfolio_tab.py"),
    Path("chamelefx/ui/dumpboard.py"),

    Path("chamelefx/performance/stats.py"),

    Path("chamelefx/validation/backtester.py"),

    Path("chamelefx/databank/loader.py"),

    Path("chamelefx/integrations/mt5_client.py"),
    Path("chamelefx/integrations/blotter_adapter.py"),

    Path("chamelefx/runtime/account.json"),
    Path("chamelefx/runtime/positions.json"),
    Path("chamelefx/runtime/fills.json"),
    Path("chamelefx/runtime/orders_recent.json"),
]

SAFE_STUBS = {
    "chamelefx/integrations/blotter_adapter.py": """\
from __future__ import annotations
from typing import Any, Dict, List
try:
    from .mt5_client import connect, shutdown, orders_get, deals_get, cancel_order as mt5_cancel
    MT5_WIRED = True
except Exception:
    MT5_WIRED = False

def _need():
    if not MT5_WIRED:
        raise RuntimeError("MT5 not wired; provide chamelefx/integrations/mt5_client.py")

def open_orders() -> List[Dict[str, Any]]:
    _need(); connect()
    try:
        rows = orders_get() or []
        return [{"id": str(r.get("ticket")), "symbol": r.get("symbol"), "side": r.get("side"),
                 "qty": r.get("qty"), "price": r.get("price_open"), "ts": r.get("ts")} for r in rows]
    finally:
        shutdown()

def recent_fills(n: int = 50) -> List[Dict[str, Any]]:
    _need(); connect()
    try:
        deals = deals_get() or []
        deals = sorted(deals, key=lambda d: d.get("ts", 0), reverse=True)[:n]
        return [{"id": str(d.get("ticket")), "symbol": d.get("symbol"), "side": d.get("side"),
                 "qty": d.get("qty"), "price": d.get("price"), "ts": d.get("ts")} for d in deals]
    finally:
        shutdown()

def cancel_order(order_id: str) -> Dict[str, Any]:
    _need(); connect()
    try:
        ok = mt5_cancel(int(order_id))
        return {"ok": bool(ok), "order_id": order_id}
    finally:
        shutdown()
""",
    "chamelefx/runtime/account.json": json.dumps({
        "equity": 100000.0, "balance": 100000.0, "open_pnl": 0.0, "open_positions": 0, "source": "sync"
    }, indent=2),
    "chamelefx/runtime/positions.json": "{}\n",
    "chamelefx/runtime/fills.json": "[]\n",
    "chamelefx/runtime/orders_recent.json": "[]\n",
}

# server.py import/include guards
ROUTER_IMPORTS = [
    ("app.api.ext_orders_blotter", "blotter_router", "from app.api.ext_orders_blotter import router as blotter_router"),
    ("app.api.ext_router_stats",   "router_stats_router", "from app.api.ext_router_stats import router as router_stats_router"),
    ("app.api.ext_alpha_features", "alpha_feat_router", "from app.api.ext_alpha_features import router as alpha_feat_router"),
    ("app.api.ext_alpha_weight",   "alpha_weight_router", "from app.api.ext_alpha_weight import router as alpha_weight_router"),
    ("app.api.ext_alpha_trade_live","alpha_trade_live_router","from app.api.ext_alpha_trade_live import router as alpha_trade_live_router"),
    ("app.api.ext_perf_metrics",   "perf_router","from app.api.ext_perf_metrics import router as perf_router"),
]
INCLUDE_LINES = [
    "app.include_router(blotter_router)",
    "app.include_router(router_stats_router)",
    "app.include_router(alpha_feat_router)",
    "app.include_router(alpha_weight_router)",
    "app.include_router(alpha_trade_live_router)",
    "app.include_router(perf_router)",
]

def copy_if_missing(live_root: Path, backup_root: Path, rel: Path, force: bool, log: List[str]):
    dst = live_root / rel
    src = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if force:
            if src.exists() and (not dst.is_file() or not filecmp.cmp(src, dst, shallow=False)):
                shutil.copy2(src, dst)
                log.append(f"OVERWRITE: {dst} from {src}")
        else:
            log.append(f"SKIP (exists): {dst}")
        return

    # copy from backup if it exists
    if src.exists():
        if src.is_dir():
            shutil.copytree(src, dst)
            log.append(f"COPY DIR: {dst} <- {src}")
        else:
            shutil.copy2(src, dst)
            log.append(f"COPY: {dst} <- {src}")
        return

    # fallback stub creation (only for known stubs)
    key = str(rel).replace("\\", "/")
    if key in SAFE_STUBS:
        dst.write_text(SAFE_STUBS[key], encoding="utf-8")
        log.append(f"STUB: {dst} (no source in backup)")
    else:
        log.append(f"MISS: {dst} (not in backup, no stub)")

def ensure_inits(live_root: Path, log: List[str]):
    for d in REQUIRED_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        init = d / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
            log.append(f"CREATE: {init}")

def patch_server_future_and_includes(live_root: Path, log: List[str]):
    sp = live_root / "app" / "api" / "server.py"
    if not sp.exists():
        log.append("WARN: app/api/server.py missing; cannot patch router includes.")
        return
    txt = sp.read_text(encoding="utf-8")
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    if not m:
        log.append("WARN: server.py has no future import at top; leaving as-is.")
        future, rest = "", txt
    else:
        future, rest = m.group(1), m.group(2)

    # ensure imports (before FastAPI app creation is fine)
    for _mod, alias, line in ROUTER_IMPORTS:
        if alias not in rest and line not in rest:
            rest = line + "\n" + rest
            log.append(f"IMPORT+ : {line}")

    # ensure includes
    for inc in INCLUDE_LINES:
        if inc not in rest:
            rest += "\n" + inc + "\n"
            log.append(f"INCLUDE+: {inc}")

    sp.write_text(future + rest, encoding="utf-8")
    log.append(f"PATCHED: {sp} (future import preserved)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing files if source differs")
    args = parser.parse_args()
    LOG: List[str] = []
    LOG.append(f"Live   : {LIVE}")
    LOG.append(f"Backup : {BACKUP}")

    if not LIVE.exists():
        raise SystemExit(f"Live root not found: {LIVE}")
    if not BACKUP.exists():
        LOG.append(f"WARNING: Backup root not found: {BACKUP} (stubs may be created)")

    # 1) ensure dirs + __init__.py
    ensure_inits(LIVE, LOG)

    # 2) copy required files if missing (or overwrite if --force)
    for rel in REQUIRED_FILES:
        copy_if_missing(LIVE, BACKUP, rel, args.force, LOG)

    # 3) normalize server imports/includes
    patch_server_future_and_includes(LIVE, LOG)

    # 4) write report
    REPORT.write_text("\n".join(LOG), encoding="utf-8")
    print("[KO SYNC] Complete. See report:", REPORT)

if __name__ == "__main__":
    main()
