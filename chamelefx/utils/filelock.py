
from __future__ import annotations
import os, contextlib
from pathlib import Path

@contextlib.contextmanager
def file_lock(path: str | os.PathLike):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    lockp = p if p.suffix == ".lock" else p.with_suffix(p.suffix + ".lock")
    fh = None
    try:
        if os.name == "nt":
            import msvcrt
            fh = open(lockp, "a+b")
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1); yield
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1); fh.close()
        else:
            import fcntl
            fh = open(lockp, "a+b")
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX); yield
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN); fh.close()
    finally:
        try:
            if fh and not fh.closed: fh.close()
        except Exception: pass
