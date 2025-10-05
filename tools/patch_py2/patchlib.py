
import re, time, shutil
from pathlib import Path

def project_root(start: Path) -> Path:
    """Find project root that contains config.json and chamelefx/."""
    p = start.resolve()
    for _ in range(8):
        if (p / "config.json").exists() and (p / "chamelefx").exists():
            return p
        p = p.parent
    raise RuntimeError("Could not locate ChameleFX project root from: " + str(start))

def backup_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        ts = time.strftime("%Y%m%d-%H%M%S")
        bak = path.with_suffix(path.suffix + f".bak.{ts}")
        shutil.copy2(path, bak)
    path.write_text(data, encoding="utf-8")

def ensure_import(text: str, import_line: str):
    if import_line.strip() in text:
        return text, False
    lines = text.splitlines()
    insert = 0
    for i, ln in enumerate(lines[:5]):
        if ln.startswith("from __future__"):
            insert = i+1
    lines.insert(insert, import_line.rstrip())
    out = "\n".join(lines)
    if not out.endswith("\n"):
        out += "\n"
    return out, True

def sub_once(text: str, pattern: str, repl: str, flags=0):
    new, n = re.subn(pattern, repl, text, count=1, flags=flags|re.M|re.S)
    return new, bool(n)

def replace_all(text: str, pattern: str, repl: str, flags=0):
    new, n = re.subn(pattern, repl, text, flags=flags|re.M|re.S)
    return new, int(n)
