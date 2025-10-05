
from pathlib import Path
from patchlib import project_root, backup_write, ensure_import

ROOT = project_root(Path(__file__))

# create admin_gate helper
gate = ROOT / "chamelefx/utils/admin_gate.py"
if not gate.exists():
    gate.write_text("""from __future__ import annotations
from fastapi import Request, HTTPException
from pathlib import Path
import json

def _admin_key() -> str | None:
    p = Path(__file__).resolve().parents[1] / "runtime" / "admin.key"
    try:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    cfgp = Path(__file__).resolve().parents[2] / "config.json"
    try:
        j = json.loads(cfgp.read_text(encoding="utf-8"))
        ops = j.get("ops", {})
        if ops.get("expose") and ops.get("admin_key"):
            return str(ops["admin_key"]).strip()
    except Exception:
        pass
    return None

def require_admin(request: Request) -> None:
    client = request.client.host if request and request.client else None
    if client in ("127.0.0.1", "::1", "localhost"):
        return
    key = request.headers.get("X-Admin-Key") or request.headers.get("x-admin-key")
    expected = _admin_key()
    if expected and key == expected:
        return
    raise HTTPException(status_code=404, detail="Not Found")
""", encoding="utf-8")
    print("[OK] created admin_gate helper")

# patch routers
targets = [
    ROOT / "app/api/ext_diag_snapshot.py",
    ROOT / "app/api/ext_ops_weekly_report.py",
    ROOT / "app/api/ext_ops_effective_config.py",
]
for p in targets:
    if not p.exists():
        print(f"[WARN] {p} missing")
        continue
    txt = p.read_text(encoding="utf-8")
    txt, _ = ensure_import(txt, "from fastapi import Depends")
    txt, _ = ensure_import(txt, "from chamelefx.utils.admin_gate import require_admin")
    txt = txt.replace("APIRouter()", "APIRouter(dependencies=[Depends(require_admin)])")
    backup_write(p, txt)
    print(f"[OK] gated ops router: {p}")
