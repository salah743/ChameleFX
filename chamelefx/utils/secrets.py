
from __future__ import annotations
import os
from typing import Optional, Tuple

def _env(name: str) -> Optional[str]:
    v = os.environ.get(name) or os.environ.get(name.lower())
    return v.strip() if isinstance(v, str) else None

def _keyring_get(svc: str, user: str) -> Optional[str]:
    try:
        import keyring
    except Exception:
        return None
    try:
        return keyring.get_password(svc, user)
    except Exception:
        return None

def get_mt5_credentials() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    login = _env("CHAM_MT5_LOGIN") or _env("MT5_LOGIN")
    server = _env("CHAM_MT5_SERVER") or _env("MT5_SERVER")
    pw = _env("CHAM_MT5_PASSWORD") or _env("MT5_PASSWORD")
    if (not pw) and login:
        pw = _keyring_get("ChameleFX_MT5", login) or _keyring_get("MT5", login)
    return login, pw, server
