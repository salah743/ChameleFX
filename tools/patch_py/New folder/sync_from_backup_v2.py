# -*- coding: utf-8 -*-
"""
KO Sync v2 — robust backup layout detection.

- Supports flat backup dump:  D:\ChameneFX Backup\<files here>
- Also supports nested:       D:\ChameleFX Backup\ChameleFX\<files here>
- Or any path containing ...\ChameleFX\

Usage:
  cd D:\ChameleFX
  .\py-portable\python\python.exe .\tools\patch_py\sync_from_backup_v2.py
  # optional overwrite:
  .\py-portable\python\python.exe .\tools\patch_py\sync_from_backup_v2.py --force
"""
from __future__ import annotations
import argparse, json, re, shutil, filecmp
from pathlib import Path
from typing import List, Optional

LIVE = Path(r"D:\ChameleFX")

# Accept both spellings; pick the one that exists
BACKUP_CANDIDATES = [
    Path(r"D:\ChameneFX Backup"),
    Path(r"D:\ChameleFX Backup"),
]
BACKUP: Optional[Path] = next((p for p in BACKUP_CANDIDATES if p.exists()), None)

REPORT = LIVE / "sync_report.txt"

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
    "chamelefx/integrations/blotter_adapter.py": """from __future__ import annotations
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
    "chamelefx/runtime/account.json": json.dumps(
        {"equity":100000.0,"balance":100000.0,"open_pnl":0.0,"open_positions":0,"source":"sync"}, indent=2),
    "chamelefx/runtime/positions.json": "{}\n",
    "chamelefx/runtime/fills.json": "[]\n",
    "chamelefx/runtime/orders_recent.json": "[]\n",
}

ROUTER_IMPORTS = [
    ("app.api.ext_orders_blotter", "blotter_router", "from app.api.ext_orders_blotter import router as blotter_router"),
    ("app.api.ext_router_stats",   "router_stats_router", "from app.api.ext_router_stats import router as router_stats_router"),
    ("app.api.ext_alpha_features", "alpha_feat_router", "from app.api.ext_alpha_features import router as alpha_feat_router"),
    ("app.api.ext_alpha_weight",   "alpha_weight_router","from app.api.ext_alpha_weight import router as alpha_weight_router"),
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

def ensure_dirs_and_inits(log: List[str]):
    for d in REQUIRED_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        ip = d / "__init__.py"
        if not ip.exists():
            ip.write_text("", encoding="utf-8")
            log.append(f"CREATE: {ip}")

def find_backup_source(rel: Path) -> Optional[Path]:
    """Try multiple layouts to find the backup source for relpath."""
    if BACKUP is None:
        return None
    # 1) Flat: BACKUP/rel
    p1 = BACKUP / rel
    if p1.exists():
        return p1
    # 2) Look for */ChameleFX/rel under backup root
    #    (handles backups where the project folder is nested somewhere)
    # Search only 2 levels deep for perf
    cand = list(BACKUP.glob(f"**/ChameleFX/{rel.as_posix()}"))
    if cand:
        # pick the shortest path (least nesting)
        cand.sort(key=lambda x: len(x.as_posix()))
        return cand[0]
    # 3) As a last resort, match by filename under backup (riskier)
    filename = rel.name
    matches = list(BACKUP.glob(f"**/{filename}"))
    if matches:
        # Prefer any that ends with the exact rel string
        exact = [m for m in matches if m.as_posix().endswith(rel.as_posix())]
        if exact:
            exact.sort(key=lambda x: len(x.as_posix()))
            return exact[0]
        # else, return the shortest path match
        matches.sort(key=lambda x: len(x.as_posix()))
        return matches[0]
    return None

def copy_if_missing(rel: Path, force: bool, log: List[str]):
    dst = LIVE / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if force:
            src = find_backup_source(rel)
            if src and src.is_file():
                # only overwrite if different
                same = False
                try:
                    same = filecmp.cmp(src, dst, shallow=False)
                except Exception:
                    same = False
                if not same:
                    shutil.copy2(src, dst)
                    log.append(f"OVERWRITE: {dst} <- {src}")
                else:
                    log.append(f"SKIP(equal): {dst}")
            else:
                log.append(f"SKIP(force,no-src): {dst}")
        else:
            log.append(f"SKIP(exists): {dst}")
        return

    # doesn't exist; try backup
    src = find_backup_source(rel)
    if src:
        if src.is_dir():
            shutil.copytree(src, dst)
            log.append(f"COPY DIR: {dst} <- {src}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            log.append(f"COPY: {dst} <- {src}")
        return

    # no source; optionally create stub
    key = rel.as_posix()
    if key in SAFE_STUBS:
        dst.write_text(SAFE_STUBS[key], encoding="utf-8")
        log.append(f"STUB: {dst} (no backup source)")
    else:
        log.append(f"MISS: {dst} (no backup source & no stub)")

def patch_server_imports(log: List[str]):
    sp = LIVE / "app" / "api" / "server.py"
    if not sp.exists():
        log.append("WARN: app/api/server.py missing; cannot patch includes.")
        return
    txt = sp.read_text(encoding="utf-8")
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    if m:
        future, rest = m.group(1), m.group(2)
    else:
        future, rest = "", txt
        log.append("WARN: no future import at top; preserving existing order.")

    for _mod, alias, line in ROUTER_IMPORTS:
        if alias not in rest and line not in rest:
            rest = line + "\n" + rest
            log.append(f"IMPORT+: {line}")

    for inc in INCLUDE_LINES:
        if inc not in rest:
            rest += "\n" + inc + "\n"
            log.append(f"INCLUDE+: {inc}")

    sp.write_text(future + rest, encoding="utf-8")
    log.append(f"PATCHED: {sp} (future import preserved if present)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing files when backup differs")
    args = parser.parse_args()

    log: List[str] = []
    log.append(f"LIVE  : {LIVE}")
    log.append(f"BACKUP: {BACKUP if BACKUP else '(not found)'}")

    if not LIVE.exists():
        raise SystemExit(f"Live root not found: {LIVE}")

    ensure_dirs_and_inits(log)

    for rel in REQUIRED_FILES:
        copy_if_missing(rel, args.force, log)

    patch_server_imports(log)

    REPORT.write_text("\n".join(log), encoding="utf-8")
    print("[KO SYNC v2] Complete. See report:", REPORT)

if __name__ == "__main__":
    main()
