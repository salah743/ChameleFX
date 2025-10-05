
from pathlib import Path
import re
from patchlib import project_root, backup_write

ROOT = project_root(Path(__file__))
p = ROOT / "app/api/server.py"
if not p.exists():
    print(f"[WARN] {p} not found")
else:
    txt = p.read_text(encoding="utf-8")

    # Fix alpha_seed block
    txt = re.sub(
        r"""# \[KO9\][\s\S]*?try:[\s\S]*?from app\.api\.ext_alpha_seed[\s\S]*?app\.include_router\(alpha_seed_router\)[\s\S]*?except[^\n]*?as e:[\s\S]*?print\([\s\S]*?\)""" ,
        '# [KO9] include alpha seeder\ntry:\n    from app.api.ext_alpha_seed import router as alpha_seed_router\n    app.include_router(alpha_seed_router)\nexcept Exception as e:\n    print("[API] ext_alpha_seed not loaded:", repr(e))',
        txt, flags=re.M
    )

    # Fix orders_recent block
    txt = re.sub(
        r"""# \[BATCH51\][\s\S]*?try:[\s\S]*?from app\.api\.ext_orders_recent[\s\S]*?app\.include_router\(orders_recent_router\)[\s\S]*?except[^\n]*?as e:[\s\S]*?print\([\s\S]*?\)""" ,
        "# [BATCH51] include recent orders router\ntry:\n    from app.api.ext_orders_recent import router as orders_recent_router\n    app.include_router(orders_recent_router)\nexcept Exception as e:\n    print('[API] app.api.ext_orders_recent not loaded:', repr(e))",
        txt, flags=re.M
    )

    backup_write(p, txt)
    print("[OK] cleaned server.py try/except blocks")
