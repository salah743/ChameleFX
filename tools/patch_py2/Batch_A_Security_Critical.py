
from pathlib import Path
import re, json
from patchlib import project_root, backup_write, ensure_import, sub_once, replace_all

ROOT = project_root(Path(__file__))

# 1) secrets helper
secrets_py = ROOT / "chamelefx/utils/secrets.py"
if not secrets_py.exists():
    secrets_py.write_text('''from __future__ import annotations
import os
from typing import Optional, Tuple

def _env(name: str) -> Optional[str]:
    v = os.environ.get(name) or os.environ.get(name.lower())
    return v.strip() if isinstance(v, str) else None

def _keyring_get(svc: str, user: str) -> Optional[str]:
    try:
        import keyring  # optional
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
''', encoding="utf-8")
    print("[A] created chamelefx/utils/secrets.py")
else:
    print("[A] secrets helper already present")

# 2) scrub setup_gui password persistence
sg = ROOT / "chamelefx/setup_gui.py"
if sg.exists():
    txt = sg.read_text(encoding="utf-8")
    new, n1 = replace_all(txt, r'("password"\s*:\s*)[^,\}\n]+', r'\1null')
    new, n2 = replace_all(new, r"('password'\s*:\s*)[^,\}\n]+", r"\1None")
    if new != txt:
        backup_write(sg, new)
        print(f"[A] scrubbed password persistence in setup_gui.py ({n1+n2} replacements)")
    else:
        print("[A] setup_gui.py: no password writes found (skipped)")
else:
    print("[A] setup_gui.py not found (skipped)")

# 3) wire mt5_guard to secrets
mg = ROOT / "chamelefx/integrations/mt5_guard.py"
if mg.exists():
    txt = mg.read_text(encoding="utf-8")
    txt, _ = ensure_import(txt, "from chamelefx.utils.secrets import get_mt5_credentials")
    if "def _mt5_creds" not in txt:
        txt += "\n\ndef _mt5_creds():\n    login, pw, server = get_mt5_credentials()\n    return {\"login\": login, \"password\": pw, \"server\": server}\n"
    backup_write(mg, txt)
    print("[A] mt5_guard wired to secure credential loader")
else:
    print("[A] mt5_guard.py not found (skipped)")

# 4) scorer.py fix (_jload)
scorer = ROOT / "chamelefx/router/scorer.py"
if scorer.exists():
    txt = scorer.read_text(encoding="utf-8")
    txt2, changed = sub_once(txt, r"def\s+_jload\([^)]*\):\s*.*?return\s*\(json\.loads\(.*?\)\s*-\s*\(_pen\s*\*\s*1e-4\)\).*?except\s+Exception:\s*return\s+default",
                             "def _jload(p: Path, default):\n    try:\n        return json.loads(p.read_text(encoding='utf-8'))\n    except Exception:\n        return default", flags=re.S)
    if changed:
        backup_write(scorer, txt2)
        print("[A] scorer.py: fixed _jload TypeError/undefined _pen")
    else:
        print("[A] scorer.py: _jload looked sane (no change)")
else:
    print("[A] scorer.py not found (skipped)")

print("\n[Batch A] Security & Critical fixes applied.")
