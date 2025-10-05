param([int]$Port = 18124)
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) { Write-Host "[OK] Nothing listening on $Port"; exit 0 }
if ($listener.OwningProcess -eq $PID) { Write-Warning "Refusing to kill this PowerShell (PID $PID). Run from another window."; exit 1 }
Stop-Process -Id $listener.OwningProcess -Force
Write-Host "[OK] Killed PID $($listener.OwningProcess) on port $Port"
