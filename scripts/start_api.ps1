param([int]$Port = 18124)
$py = Join-Path $PSScriptRoot "..\py-portable\python\python.exe"
if (-not (Test-Path $py)) { $py = "py" }
Set-Location (Split-Path $PSScriptRoot -Parent)
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","app.api.server:app","--host","127.0.0.1","--port",$Port,"--log-level","debug" -WindowStyle Hidden
