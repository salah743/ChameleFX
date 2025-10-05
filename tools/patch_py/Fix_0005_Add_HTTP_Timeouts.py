
from pathlib import Path
import re
from patchlib import project_root, backup_write

ROOT = project_root(Path(__file__))
paths = list((ROOT / "chamelefx/ui").glob("*.py")) + [ROOT / "app/api/server.py"]

def add_timeout_to_calls(text: str) -> str:
    def repl(m):
        call = m.group(0)
        if "timeout=" in call:
            return call
        return call[:-1] + (", timeout=5.0)")
    return re.sub(r"""requests\.(get|post)\([^)]*\)""", repl, text)

for path in paths:
    if not path.exists():
        continue
    txt = path.read_text(encoding="utf-8")
    new = add_timeout_to_calls(txt)
    if new != txt:
        backup_write(path, new)
        print(f"[OK] enforced timeouts in {path}")
    else:
        print(f"[SKIP] {path} already had timeouts or no calls")
