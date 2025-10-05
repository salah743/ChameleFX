
from pathlib import Path
from patchlib import project_root, backup_write

ROOT = project_root(Path(__file__))
readme = ROOT / "README.md"
append = """

## Operations Notes (added by patch batch)

- Ops routes (`/ops/*`) are gated by default. To enable temporarily:
  1. Create `chamelefx/runtime/admin.key` containing a secret.
  2. Or set in `config.json`: `"ops": {"expose": true, "admin_key": "<SECRET>"}`
  3. Call ops endpoints with header `X-Admin-Key: <SECRET>`.
- API CORS now restricted to `http://127.0.0.1` and `http://localhost` by default.
- UI HTTP calls enforce a default timeout (5s).
"""
if readme.exists():
    backup_write(readme, readme.read_text(encoding="utf-8") + append)
    print("[OK] README updated with new ops/cors notes")
else:
    print("[SKIP] README.md not found")
