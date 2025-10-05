# tools/patch_py/apply_bundle_S_packaging.py
from __future__ import annotations
from pathlib import Path
import re, json, textwrap, time

ROOT = Path(__file__).resolve().parents[2]
APP  = ROOT / "app" / "api"
CFX  = ROOT / "chamelefx"
RUN  = CFX / "runtime"
DOC  = ROOT / "docs"
SCR  = ROOT / "scripts"
DAT  = ROOT / "data" / "history"
RUN.mkdir(parents=True, exist_ok=True)
SCR.mkdir(parents=True, exist_ok=True)
DOC.mkdir(parents=True, exist_ok=True)
DAT.mkdir(parents=True, exist_ok=True)

def w(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.strip() + "\n", encoding="utf-8")
    print("[S] wrote", p)

# ---------- Start scripts ----------
START_API = r"""
# scripts/start_api.ps1
param(
  [string]$Host = "127.0.0.1",
  [int]$Port = 18124
)
$ErrorActionPreference = "Stop"
$BASE = "http://$Host`:$Port"
function Test-Health {
  try { Invoke-RestMethod "$BASE/health" -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}
if (Test-Health) { Write-Host "[CFX] API already running on $BASE"; exit 0 }
$py = "D:\ChameleFX\py-portable\python\python.exe"
if (-not (Test-Path $py)) { $py = "python.exe" }
$cmd = "-m uvicorn app.api.server:app --host $Host --port $Port --reload"
Write-Host "[CFX] starting API on $BASE ..."
Start-Process -FilePath $py -ArgumentList $cmd -WorkingDirectory "D:\ChameleFX" -WindowStyle Minimized
Start-Sleep -Seconds 2
if (Test-Health) { Write-Host "[CFX] API up at $BASE" } else { Write-Host "[CFX] API failed to start"; exit 1 }
"""

START_MANAGER = r"""
# scripts/start_manager.ps1
$ErrorActionPreference = "Stop"
$py = "D:\ChameleFX\py-portable\python\python.exe"
if (-not (Test-Path $py)) { $py = "python.exe" }
# 1) Ensure API is up
& "$PSScriptRoot\start_api.ps1" -Host "127.0.0.1" -Port 18124
# 2) Launch Manager (single-instance lock already handled in app)
$mgr = "D:\ChameleFX\chamelefx\setup_gui.py"
if (-not (Test-Path $mgr)) { $mgr = "D:\ChameleFX\chamelefx\manager.py" }
Write-Host "[CFX] launching Manager ..."
Start-Process -FilePath $py -ArgumentList $mgr -WorkingDirectory "D:\ChameleFX" -WindowStyle Normal
"""

# ---------- Effective config API ----------
EXT_CFG = r"""
from __future__ import annotations
from fastapi import APIRouter
from pathlib import Path
from chamelefx.utils.validator import validate_and_fix_config

router = APIRouter()

@router.get("/ops/config/effective")
def ops_config_effective():
    cfgp = Path(__file__).resolve().parents[2] / "chamelefx" / "config.json"
    cfg = validate_and_fix_config(cfgp)
    return {"ok": True, "config": cfg}

@router.post("/ops/config/reload")
def ops_config_reload():
    cfgp = Path(__file__).resolve().parents[2] / "chamelefx" / "config.json"
    cfg = validate_and_fix_config(cfgp)
    return {"ok": True, "reloaded": True, "config": cfg}
"""

# ---------- Docs ----------
QUICKSTART = r"""
# ChameleFX — Quickstart

## Start
```powershell
cd D:\ChameleFX
.\scripts\start_api.ps1
.\scripts\start_manager.ps1
