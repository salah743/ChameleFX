
from pathlib import Path
import re
from patchlib import project_root, backup_write, ensure_import

ROOT = project_root(Path(__file__))

# Create chamelefx/log.py
log_mod = ROOT / "chamelefx/log.py"
if not log_mod.exists():
    log_mod.write_text("""from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def get_logger(name: str = "chamelefx"):
    try:
        root = Path(__file__).resolve().parents[1]
        logdir = root / "runtime" / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        logfile = logdir / "app.log"
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            fh = RotatingFileHandler(logfile, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        return logger
    except Exception:
        return logging.getLogger(name)
""", encoding="utf-8")
    print("[OK] created chamelefx/log.py")
else:
    print("[SKIP] chamelefx/log.py already present")

# Replace silent excepts in selected files
targets = [
    ROOT / "chamelefx/alpha/features.py",
    ROOT / "chamelefx/alpha/ensemble.py",
    ROOT / "chamelefx/integrations/mt5_guard.py",
    ROOT / "app/api/server.py",
    ROOT / "chamelefx/ui/alpha_tab.py",
]
for path in targets:
    if not path.exists():
        print(f"[WARN] {path} not found")
        continue
    txt = path.read_text(encoding="utf-8")
    txt, imp = ensure_import(txt, "from chamelefx.log import get_logger")
    new = re.sub(r"""except(?:\s+Exception)?\s*:\s*pass""", "except Exception:\n    get_logger(__name__).exception('Unhandled exception')", txt, flags=re.M)
    if imp or new != txt:
        backup_write(path, new)
        print(f"[OK] patched silent excepts in {path}")
    else:
        print(f"[SKIP] no silent excepts changed in {path}")
