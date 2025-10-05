# -*- coding: utf-8 -*-
"""
Fix server.py: ensure 'from __future__ import annotations' is at the very top,
after optional shebang and encoding lines, and only once.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "app" / "api" / "server.py"

def main() -> int:
    if not SERVER.exists():
        print("[ERR] server.py not found:", SERVER)
        return 2

    src = SERVER.read_text(encoding="utf-8")
    lines = src.splitlines()

    # Extract optional shebang/encoding headers
    shebang = []
    body_start = 0
    for i, line in enumerate(lines):
        if i == 0 and line.startswith("#!"):
            shebang.append(line)
            continue
        if re.match(r"^#.*coding[:=]\s*[-\w.]+", line.strip()):
            shebang.append(line)
            continue
        body_start = i
        break

    body = lines[body_start:]

    # Remove ALL occurrences of future import in body
    FUTURE_LINE = "from __future__ import annotations"
    body = [ln for ln in body if ln.strip() != FUTURE_LINE]

    # Rebuild: shebang/encoding + future + a blank + rest
    fixed = []
    fixed.extend(shebang)
    if shebang:
        fixed.append("")  # keep a blank after headers
    fixed.append(FUTURE_LINE)
    fixed.append("")
    fixed.extend(body)

    SERVER.write_text("\n".join(fixed) + "\n", encoding="utf-8")
    print("[OK] server.py future import moved to top.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
