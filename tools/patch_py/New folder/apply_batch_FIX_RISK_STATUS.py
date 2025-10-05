import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
api_dir = ROOT / "app" / "api"
api_dir.mkdir(parents=True, exist_ok=True)
risk_file = api_dir / "ext_risk_status.py"

if not risk_file.exists():
    risk_file.write_text(
        "from fastapi import APIRouter\n\n"
        "router = APIRouter()\n\n"
        "@router.get('/risk/state')\n"
        "async def get_risk_state():\n"
        "    return { 'ok': True, 'state': 'stub' }\n"
    )
    print("[OK] Created", risk_file)

print("[OK] ext_risk_status ensured.")
