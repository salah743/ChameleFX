
from pathlib import Path
from patchlib import project_root, backup_write, ensure_import, replace_all

ROOT = project_root(Path(__file__))

# 1) file lock helper
fl = ROOT / "chamelefx/utils/filelock.py"
if not fl.exists():
    fl.write_text('''from __future__ import annotations
import os, contextlib
from pathlib import Path

@contextlib.contextmanager
def file_lock(path: str | os.PathLike):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lockp = p if p.suffix == ".lock" else p.with_suffix(p.suffix + ".lock")
    fh = None
    try:
        if os.name == "nt":
            import msvcrt
            fh = open(lockp, "a+b")
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            yield
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            fh.close()
        else:
            import fcntl
            fh = open(lockp, "a+b")
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            yield
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            fh.close()
    finally:
        try:
            if fh and not fh.closed:
                fh.close()
        except Exception:
            pass
''', encoding="utf-8")
    print("[B] created chamelefx/utils/filelock.py")
else:
    print("[B] filelock helper already present")

# 2) lock orders_outbox access in mt5_guard (best-effort)
mg = ROOT / "chamelefx/integrations/mt5_guard.py"
if mg.exists():
    txt = mg.read_text(encoding="utf-8")
    txt, _ = ensure_import(txt, "from chamelefx.utils.filelock import file_lock")
    if "orders_outbox.json" in txt and "with file_lock(" not in txt:
        txt = txt.replace("write_json_atomic(", "with file_lock('chamelefx/runtime/orders_outbox.json'):\n    write_json_atomic(")
        backup_write(mg, txt)
        print("[B] mt5_guard protected with file lock (best-effort)")
    else:
        print("[B] mt5_guard: no changes needed")
else:
    print("[B] mt5_guard.py not found")

# 3) silent except cleanup across core modules
targets = []
for sub in ["chamelefx/portfolio", "chamelefx/alpha", "chamelefx/router", "chamelefx/integrations", "app/api", "chamelefx/ui"]:
    p = ROOT / sub
    if p.exists():
        targets += list(p.rglob("*.py"))
count_files = 0
count_repl = 0
for path in targets:
    try:
        txt = path.read_text(encoding="utf-8")
    except Exception:
        continue
    original = txt
    txt, imp = ensure_import(txt, "from chamelefx.log import get_logger")
    txt, n1 = replace_all(txt, r"except:\s*pass", "except Exception:\n    get_logger(__name__).exception('Unhandled exception')")
    txt, n2 = replace_all(txt, r"except\s+Exception\s*:\s*pass", "except Exception:\n    get_logger(__name__).exception('Unhandled exception')")
    if imp or n1 or n2:
        backup_write(path, txt)
        count_files += 1
        count_repl += (n1 + n2)
print(f"[B] replaced silent excepts in {count_files} files; {count_repl} sites")

# 4) remove misplaced unittest clone if present
junk = ROOT / "chamelefx/databank/loader.py"
if junk.exists():
    try:
        junk.unlink()
        print("[B] removed chamelefx/databank/loader.py")
    except Exception:
        pass

print("\n[Batch B] Stability & Quality changes applied.")
