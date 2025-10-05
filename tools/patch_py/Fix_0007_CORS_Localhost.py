
from pathlib import Path
import re
from patchlib import project_root, backup_write

ROOT = project_root(Path(__file__))
p = ROOT / "app/api/server.py"
if not p.exists():
    print(f"[WARN] {p} not found")
else:
    txt = p.read_text(encoding="utf-8")
    new = re.sub(r'allow_origins=\["\*"\]', 'allow_origins=["http://127.0.0.1","http://localhost"]', txt)
    if new != txt:
        backup_write(p, new)
        print("[OK] restricted CORS to localhost")
    else:
        print("[SKIP] CORS already restricted or pattern mismatch")
