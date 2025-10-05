$ErrorActionPreference = "Stop"
$Root = "D:\ChameleFX"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
function Backup($p){ if(Test-Path $p){ Copy-Item $p "$p.bak.$ts" -Force } }

Write-Host "== Fixing Setup GUI loopback & enforcing ports =="

# A) setup_gui.py loopback fix
$setup = Join-Path $Root "chamelefx\setup_gui.py"
if(Test-Path $setup){
  Backup $setup
  $txt = Get-Content $setup -Raw
  $fixed = $txt -replace "http://12\.0\.0\.1:(\{?PORT\}?|\d+)", "http://127.0.0.1:`$1"
  if($fixed -ne $txt){
    Set-Content $setup $fixed -Encoding UTF8
    Write-Host "[OK] setup_gui.py loopback fixed  127.0.0.1"
  } else { Write-Host "[SKIP] setup_gui.py already uses 127.0.0.1" }
} else { Write-Host "[WARN] setup_gui.py not found at $setup" }

# B) Enforce API port 8088 in common files
$files = @("chamelefx\manager.py","chamelefx\manager_core\api_client.py","app\api\server.py") | % { Join-Path $Root $_ } | ? { Test-Path $_ }
foreach($f in $files){
  Backup $f
  $raw = Get-Content $f -Raw
  $raw2 = $raw -replace "http://127\.0\.0\.1:(808[0-9]|80[0-9]{2})","http://127.0.0.1:18123"
  if($raw2 -ne $raw){ Set-Content $f $raw2 -Encoding UTF8; Write-Host "[OK] Port 8088 enforced in $([IO.Path]::GetFileName($f))" }
  else { Write-Host "[SKIP] $([IO.Path]::GetFileName($f)) already 8088/dynamic" }
}
Write-Host "== Done =="
