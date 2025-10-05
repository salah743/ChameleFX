
from __future__ import annotations
import logging, sys
from pathlib import Path

_LOGGERS = {}
def _ensure_runtime_logs() -> Path:
    base = Path(__file__).resolve().parents[1] / "runtime" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_logger(name: str) -> logging.Logger:
    if name in _LOGGERS:
        return _LOGGERS[name]
    logger = logging.getLogger(name); logger.setLevel(logging.INFO)
    if not logger.handlers:
        logs = _ensure_runtime_logs()
        fh = logging.FileHandler(logs / "app.log", encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt)
        logger.addHandler(fh); logger.addHandler(sh)
    _LOGGERS[name] = logger
    return logger
