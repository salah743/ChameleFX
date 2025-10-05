# -*- coding: utf-8 -*-
"""
KO Stub-All Routers:
- Parse app/api/server.py for "from app.api.ext_XXX import router ..."
- Create missing app/api/ext_XXX.py stubs with a basic APIRouter.
"""
from __future__ import annotations
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_DIR = ROOT / "app" / "api"
SERVER = API_DIR / "server.py"

def ensure_init(pkg: Path):
    f = pkg / "__init__.py"
    if not f.exists():
        pkg.mkdir(parents=True, exist_ok=True)
        f.write_text("# package\n", encoding="utf-8")

def make_stub(modname: str, target: Path):
    """
    Create a minimal FastAPI router stub for module 'ext_xxx'.
    Expose GET /xxx/ping returning {ok:true, name:"ext_xxx"}.
    """
    name = modname.replace("ext_", "", 1)  # ext_actions -> actions
    content = (
        "from fastapi import APIRouter\n\n"
        "router = APIRouter()\n\n"
        f"@router.get('/{name}/ping')\n"
        "async def ping():\n"
        f"    return {{'ok': True, 'name': '{modname}'}}\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"[STUB] created {target}")

def main():
    ensure_init(API_DIR)
    if not SERVER.exists():
        print("[ERR] app/api/server.py not found")
        return 2

    txt = SERVER.read_text(encoding="utf-8")
    # matches: from app.api.ext_actions import router as actions_router
    pat = re.compile(r"from\s+app\.api\.(ext_[A-Za-z0-9_]+)\s+import\s+router\b")
    mods = pat.findall(txt)
    if not mods:
        print("[INFO] No ext_* imports found in server.py")
        return 0

    created = 0
    for mod in sorted(set(mods)):
        stub_path = API_DIR / f"{mod}.py"
        if not stub_path.exists():
            make_stub(mod, stub_path)
            created += 1
        else:
            # ensure file has a 'router' object; if not, (re)write minimal stub
            src = stub_path.read_text(encoding="utf-8", errors="ignore")
            if "APIRouter" not in src or "router =" not in src:
                make_stub(mod, stub_path)
                created += 1
            else:
                print(f"[OK] {stub_path} exists")

    print(f"[DONE] {created} stub(s) created/updated.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
