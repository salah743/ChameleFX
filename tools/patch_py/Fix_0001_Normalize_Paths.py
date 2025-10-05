
from pathlib import Path
import re
from patchlib import project_root, backup_write, replace_once, ensure_import

ROOT = project_root(Path(__file__))

targets = [
    ROOT / "chamelefx/alpha/features.py",
    ROOT / "chamelefx/alpha/ensemble.py",
]

for path in targets:
    if not path.exists():
        print(f"[WARN] skip {path} (not found)")
        continue
    txt = path.read_text(encoding="utf-8")
    changed = False

    txt, imp = ensure_import(txt, "from pathlib import Path")
    changed = changed or imp

    if path.name == "features.py":
        txt, c1 = replace_once(txt, r"""^ROOT\s*=.*$""", "PROJECT_ROOT = Path(__file__).resolve().parents[2]")
        txt, c2 = replace_once(txt, r"""^DATA\s*=.*$""", 'DATA = str(PROJECT_ROOT / "data" / "history")')
        txt, c3 = replace_once(txt, r"""^RUNTIME\s*=.*$""", 'RUNTIME = str(PROJECT_ROOT / "chamelefx" / "runtime")')
        changed = changed or c1 or c2 or c3

    if path.name == "ensemble.py":
        txt, c1 = replace_once(txt, r"""^ROOT\s*=.*$""", "PROJECT_ROOT = Path(__file__).resolve().parents[2]")
        txt, c2 = replace_once(txt, r"""^RUN\s*=.*$""", 'RUN  = str(PROJECT_ROOT / "chamelefx" / "runtime")')
        changed = changed or c1 or c2

    if changed:
        backup_write(path, txt)
        print(f"[OK] normalized paths in {path}")
    else:
        print(f"[SKIP] {path} already normalized")
