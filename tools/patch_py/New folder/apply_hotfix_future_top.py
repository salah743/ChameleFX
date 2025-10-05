# -*- coding: utf-8 -*-
"""
Ensure ALL `from __future__ import ...` lines in app/api/server.py
are placed at the very beginning of the module (right after an initial
module docstring if present), before any other imports or code.

Idempotent: safe to re-run.
"""
from __future__ import annotations
import io, re, time, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRV  = ROOT / "app" / "api" / "server.py"

FUTURE_RE = re.compile(r'^\s*from\s+__future__\s+import\s+.+\s*$')

def backup(p: Path):
    if p.exists():
        shutil.copy2(p, p.with_suffix(p.suffix + f".bak.{int(time.time())}"))

def split_docstring(lines: list[str]) -> tuple[int, int]:
    """
    If the file starts with a module docstring (after optional blank lines/comments),
    return (start_idx, end_idx_exclusive) of that docstring block.
    Otherwise return (-1, -1).
    """
    i = 0
    n = len(lines)

    # skip leading blank lines and comments (shebang or encoding ok to keep above)
    while i < n and (lines[i].strip() == "" or lines[i].lstrip().startswith("#") or lines[i].startswith("\ufeff")):
        i += 1
    if i >= n:
        return (-1, -1)

    line = lines[i].lstrip()
    if line.startswith(('"""', "'''")):
        quote = '"""' if line.startswith('"""') else "'''"
        # single-line docstring?
        if line.count(quote) >= 2:
            return (i, i+1)
        # multi-line: find closing
        j = i + 1
        while j < n:
            if quote in lines[j]:
                return (i, j+1)
            j += 1
        # unterminated - treat as no docstring
        return (-1, -1)
    return (-1, -1)

def main():
    if not SRV.exists():
        print("[SKIP] server.py not found")
        return 0

    text = SRV.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Collect all future-import lines and remove them from the body
    futures = []
    body_lines = []
    for ln in lines:
        if FUTURE_RE.match(ln):
            if ln.strip() not in futures:
                futures.append(ln.strip())
        else:
            body_lines.append(ln)

    if not futures:
        print("[OK] No future imports found to move.")
        return 0

    # Find docstring block at top (after blanks/comments)
    ds_start, ds_end = split_docstring(body_lines)

    new_lines: list[str] = []
    if ds_start >= 0:
        # keep everything up to the end of docstring, then future block
        new_lines.extend(body_lines[:ds_end])
        # ensure exactly one blank line after docstring
        if len(new_lines) and new_lines[-1].strip() != "":
            new_lines.append("")
        new_lines.extend(futures)
        new_lines.append("")
        # then the rest (skipping any accidental duplicate blank lines)
        rest = body_lines[ds_end:]
        new_lines.extend(rest)
    else:
        # place futures at absolute top
        new_lines.extend(futures)
        new_lines.append("")
        new_lines.extend(body_lines)

    # Normalize excessive blank lines
    out = "\n".join(new_lines)
    out = re.sub(r"\n{3,}", "\n\n", out) + ("\n" if not out.endswith("\n") else "")

    if out != text:
        backup(SRV)
        SRV.write_text(out, encoding="utf-8")
        print("[OK] Moved future import block to the top (after docstring if present).")
    else:
        print("[OK] server.py already compliant.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
