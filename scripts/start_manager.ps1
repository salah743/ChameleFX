
param([int]$Port = 18124)
$py = Join-Path $PSScriptRoot "..\py-portable\python\python.exe"
if (-not (Test-Path $py)) { $py = "py" }
$api = Join-Path $PSScriptRoot "start_api.ps1"
if (Test-Path $api) { powershell -NoProfile -ExecutionPolicy Bypass -File $api | Out-Null }
Set-Location (Split-Path $PSScriptRoot -Parent)
Start-Process -FilePath $py -ArgumentList "-c","import chamelefx.setup_gui as s; s.main()" -WindowStyle Normal
