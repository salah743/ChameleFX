import os
from pathlib import Path
from fastapi import APIRouter

ROOT = Path(__file__).resolve().parents[2]
api_dir = ROOT / "app" / "api"
api_dir.mkdir(parents=True, exist_ok=True)
execq_file = api_dir / "ext_exec_quality.py"

if not execq_file.exists():
    execq_file.write_text(
        "from fastapi import APIRouter\n\n"
        "router = APIRouter()\n\n"
        "@router.get('/exec/quality')\n"
        "async def exec_quality_summary():\n"
        "    return {\n"
        "        'ok': True,\n"
        "        'vwap_delta': 0.0,\n"
        "        'is_score': 0.0,\n"
        "        'slippage_hist_bps': {}\n"
        "    }\n"
    )
    print('[OK] Created', execq_file)

print('[OK] ext_exec_quality ensured.')
