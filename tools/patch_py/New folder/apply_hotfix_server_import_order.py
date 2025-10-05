# -*- coding: utf-8 -*-
"""
Reorder imports in app/api/server.py so that:
- all `from __future__ import ...` remain at the top (first contiguous block)
- new router imports are inserted AFTER that block (not before)
- include_router(...) lines are appended near file end if missing

Idempotent & safe on re-runs.
"""
from __future__ import annotations
import re, time, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRV  = ROOT / "app" / "api" / "server.py"

# Put any imports you want ensured here:
ENSURE_IMPORTS = [
    # examples (leave as-is if already present)
    "from app.api.ext_exec_router import router as exec_router",
    "from app.api.ext_exec_quality import router as exec_quality_router",
    "from app.api.ext_alpha_health import router as alpha_health_router",
    "from app.api.ext_bt_validate import router as bt_validate_router",
    "from app.api.ext_risk_plus import router as risk_plus_router",
]

ENSURE_INCLUDES = [
    "app.include_router(exec_router)",
    "app.include_router(exec_quality_router)",
    "app.include_router(alpha_health_router)",
    "app.include_router(bt_validate_router)",
    "app.include_router(risk_plus_router)",
]

def backup(p: Path):
    if p.exists():
        shutil.copy2(p, p.with_suffix(p.suffix + f".bak.{int(time.time())}"))

def find_future_block(lines: list[str]) -> int:
    """
    Return index of the last line of the leading future-import block.
    If no future imports at top, return -1.
    """
    i = 0
    found = False
    for idx, line in enumerate(lines):
        if idx == 0 and line.strip().startswith("from __future__ import"):
            found = True
            i = idx
            continue
        if found:
            if line.strip().startswith("from __future__ import"):
                i = idx
                continue
            else:
                return i
        else:
            # first line is not future import → no block
            break
    return i if found else -1

def ensure_imports_preserving_future(txt: str) -> str:
    lines = txt.splitlines()
    end_future = find_future_block(lines)  # -1 if none
    body = "\n".join(lines)

    # remove duplicates first (we’ll re-insert cleanly)
    for imp in ENSURE_IMPORTS:
        body = re.sub(rf"^\s*{re.escape(imp)}\s*$", "", body, flags=re.M)
    # normalize consecutive blank lines
    body = re.sub(r"\n{3,}", "\n\n", body)

    lines = body.splitlines()
    insert_idx = (end_future + 1) if end_future >= 0 else 0

    # Insert imports after future block (keeping a blank line after imports)
    head = lines[:insert_idx]
    tail = lines[insert_idx:]
    to_add = [imp for imp in ENSURE_IMPORTS if imp not in body]
    if to_add:
        block = "\n".join(to_add) + "\n"
        # ensure a blank line after the inserted block if not present
        if tail and tail[0].strip():
            block += "\n"
        new = "\n".join(head) + ("\n" if head and head[-1].strip() else "") + block + "\n".join(tail)
    else:
        new = body
    # collapse extra blank lines
    new = re.sub(r"\n{3,}", "\n\n", new)
    return new

def ensure_includes_at_end(txt: str) -> str:
    # append missing include_router calls at the end (idempotent)
    missing = [inc for inc in ENSURE_INCLUDES if inc not in txt]
    if not missing:
        return txt
    tail = "\n".join(missing)
    if not txt.endswith("\n"):
        txt += "\n"
    txt += "\n" + tail + "\n"
    return txt

def main():
    if not SRV.exists():
        print("[SKIP] server.py not found:", SRV)
        return 0
    orig = SRV.read_text(encoding="utf-8")
    updated = ensure_imports_preserving_future(orig)
    updated = ensure_includes_at_end(updated)
    if updated != orig:
        backup(SRV)
        SRV.write_text(updated, encoding="utf-8")
        print("[OK] server.py imports/inclusions normalized (future block preserved).")
    else:
        print("[OK] server.py already normalized.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
