import os
from pathlib import Path
from fastapi import APIRouter

ROOT = Path(__file__).resolve().parents[2]
api_dir = ROOT / "app" / "api"
api_dir.mkdir(parents=True, exist_ok=True)
alerts_file = api_dir / "ext_alerts.py"

if not alerts_file.exists():
    alerts_file.write_text(
        "from fastapi import APIRouter\n\n"
        "router = APIRouter()\n\n"
        "@router.get('/alerts')\n"
        "async def get_alerts():\n"
        "    return { 'ok': True, 'alerts': [] }\n"
    )
    print('[OK] Created', alerts_file)

print('[OK] ext_alerts ensured.')
