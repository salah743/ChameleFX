param([int]$Port = 18124, [int]$TimeoutSec = 20)

# Resolve portable python or fall back to 'py'
$py = Join-Path $PSScriptRoot "..\py-portable\python\python.exe"
if (-not (Test-Path $py)) { $py = "py" }

# If already listening, exit quietly
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) { Write-Host "[OK] API already listening on $Port (PID $($listener.OwningProcess))"; exit 0 }

# Launch uvicorn hidden from project root
Set-Location (Split-Path $PSScriptRoot -Parent)
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","app.api.server:app","--host","127.0.0.1","--port",$Port,"--log-level","debug" -WindowStyle Hidden

# Poll health until ready
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$healthUrl = "http://127.0.0.1:$Port/health"
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 500
  try { $r = Invoke-RestMethod $healthUrl -TimeoutSec 2; if ($r.ok) { Write-Host "[OK] API healthy on $Port"; exit 0 } } catch {}
}
Write-Warning "[WARN] API not healthy after $TimeoutSec s. Run in foreground to see logs:"
Write-Host    "       $py -m uvicorn app.api.server:app --host 127.0.0.1 --port $Port --log-level debug"
