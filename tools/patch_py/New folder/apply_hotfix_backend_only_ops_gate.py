from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
APP  = ROOT / "app" / "api"
CFX  = ROOT / "chamelefx"

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.strip()+"\n", encoding="utf-8")
    print("[GATE] wrote", p)

ADMIN_GATE = r"""
from __future__ import annotations
from typing import Optional
from pathlib import Path
from fastapi import Request, HTTPException
from chamelefx.utils.validator import validate_and_fix_config

def _load_admin_key(cfg_ops: dict) -> Optional[str]:
    key = (cfg_ops or {}).get("admin_key")
    if key:
        return str(key)
    # optional file-based key: chamelefx/runtime/admin.key
    p = Path(__file__).resolve().parents[1] / "runtime" / "admin.key"
    try:
        return p.read_text(encoding="utf-8").strip() if p.exists() else None
    except Exception:
        return None

async def admin_guard(request: Request):
    """404 unless ops.expose==true; if exposed, require X-Admin-Key if configured; else allow localhost only."""
    cfgp = Path(__file__).resolve().parents[1] / "config.json"
    cfg  = validate_and_fix_config(cfgp)
    ops  = (cfg or {}).get("ops", {})
    if not bool(ops.get("expose", False)):
        raise HTTPException(status_code=404, detail="not found")
    # exposed -> enforce key if present
    admin_key = _load_admin_key(ops)
    if admin_key:
        hdr = request.headers.get("x-admin-key") or request.headers.get("X-Admin-Key")
        if hdr != admin_key:
            raise HTTPException(status_code=403, detail="forbidden")
        return
    # no key -> allow only local
    client = (request.client.host if request.client else "")
    if client not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="local_only")
"""

def patch_router(path: Path):
    txt = path.read_text(encoding="utf-8")
    if "admin_guard" in txt:
        print(f"[GATE] already guarded: {path}")
        return
    # add imports
    if "from fastapi import APIRouter" in txt:
        txt = txt.replace("from fastapi import APIRouter",
                          "from fastapi import APIRouter, Depends\nfrom chamelefx.utils.admin_gate import admin_guard")
    # add dependency on router
    txt = re.sub(r"router\s*=\s*APIRouter\(\s*\)",
                 "router = APIRouter(dependencies=[Depends(admin_guard)])",
                 txt)
    path.write_text(txt, encoding="utf-8")
    print(f"[GATE] guarded: {path}")

def main():
    write(CFX / "utils" / "admin_gate.py", ADMIN_GATE)

    # guard our ops routers
    candidates = [
        APP / "ext_diag_snapshot.py",        # Bundle R
        APP / "ext_ops_effective_config.py", # Bundle S
        APP / "ext_ops_weekly_report.py",    # Bundle P
    ]
    for p in candidates:
        if p.exists():
            patch_router(p)
        else:
            print(f"[GATE] skip (not found): {p}")

    print("[GATE] backend-only ops gate installed.")

if __name__ == "__main__":
    main()
