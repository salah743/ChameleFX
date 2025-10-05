# Weekend Feedback Autopilot for ChameleFX (Dubai weekend)
# Applies conservative regime-multiplier nudges from Bundle O
$ErrorActionPreference = "Stop"

$BASE = "http://127.0.0.1:18124"
$LOG  = "D:\ChameleFX\scripts\weekend_feedback.log"

function Write-Log($msg) {
  $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  Add-Content -Path $LOG -Value ("[$ts] " + $msg)
}

function Ping-Endpoint($url, $retries=8, $delay=3) {
  for ($i=1; $i -le $retries; $i++) {
    try {
      $r = Invoke-RestMethod -Uri $url -TimeoutSec 5
      return $true
    } catch {
      Start-Sleep -Seconds $delay
    }
  }
  return $false
}

# 0) API up?
if (-not (Ping-Endpoint "$BASE/health")) {
  Write-Log "API /health not responding — skipping feedback run."
  exit 1
}

# 1) Preview planned nudges (log them)
try {
  $syms = @('EURUSD','GBPUSD','USDJPY')  # adjust as you like
  $prev = Invoke-RestMethod -Method Post `
    -Uri "$BASE/alpha/feedback/preview" `
    -ContentType 'application/json' `
    -Body (@{symbols=$syms} | ConvertTo-Json -Depth 5)
  Write-Log ("preview: " + ($prev | ConvertTo-Json -Depth 6))
} catch {
  Write-Log ("preview error: " + $_.Exception.Message)
}

Start-Sleep -Seconds 2

# 2) Apply nudges
try {
  $apply = Invoke-RestMethod -Method Post `
    -Uri "$BASE/alpha/feedback/apply" `
    -ContentType 'application/json' `
    -Body (@{symbols=$syms} | ConvertTo-Json -Depth 5)
  Write-Log ("apply: " + ($apply | ConvertTo-Json -Depth 6))
} catch {
  Write-Log ("apply error: " + $_.Exception.Message)
}

Write-Log "Weekend feedback run completed."
