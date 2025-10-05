# tools/patch_py/apply_batch_M3_future_top.py
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET_DIRS = [ROOT/"chamelefx", ROOT/"app"/"api"]

FUTURE_RE = re.compile(r"^\s*from __future__ import ([^\n]+)\n?$", re.MULTILINE)

def normalize_future(path: Path) -> bool:
    try:
        txt = path.read_text(encoding="utf-8")
    except Exception:
        return False

    # collect all future imports
    futures = FUTURE_RE.findall(txt)
    if not futures:
        return False

    # combine unique features in order
    features = []
    for f in futures:
        for part in [x.strip() for x in f.split(",")]:
            if part and part not in features:
                features.append(part)

    # strip all future lines
    stripped = FUTURE_RE.sub("", txt).lstrip("\n")

    # if file already starts with the exact combined line, skip write
    combined = f"from __future__ import {', '.join(features)}\n"
    if stripped.startswith(combined):
        return False

    # write: combined future at very top + the rest
    new_txt = combined + stripped
    path.write_text(new_txt, encoding="utf-8")
    return True

def main():
    changed = 0
    files = []
    for root in TARGET_DIRS:
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            files.append(p)

    for p in files:
        try:
            if normalize_future(p):
                print("[M3] fixed:", p)
                changed += 1
        except Exception as e:
            print(f"[M3] skip {p}: {e}")

    print(f"[M3] done. files changed: {changed}")

if __name__ == "__main__":
    main()
