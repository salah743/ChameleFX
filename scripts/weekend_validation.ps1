# Weekend Validation Autopilot for ChameleFX (Dubai weekend)
# Runs sequential API calls with small delays + retries.
$ErrorActionPreference = "Stop"

$BASE = "http://127.0.0.1:18124"
$LOG  = "D:\ChameleFX\scripts\weekend_validation.log"
$TS   = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

function Write-Log($msg) {
  Add-Content -Path $LOG -Value ("[$TS] " + $msg)
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

# 0) Ensure API is up
if (-not (Ping-Endpoint "$BASE/health")) {
  Write-Log "API /health not responding — skipping run."
  exit 1
}

# 1) PARITY (live vs backtest sizing)
try {
  $body = @{ symbol = "EURUSD"; params = @{ method = "kelly"; clamp = 0.35 } } | ConvertTo-Json
  $r1 = Invoke-RestMethod -Method Post -Uri "$BASE/validation/parity/run" -ContentType 'application/json' -Body $body
  Write-Log ("parity.run ok=" + $r1.ok + " drift=" + $r1.drift)
} catch {
  Write-Log ("parity.run error: " + $_.Exception.Message)
}

Start-Sleep -Seconds 2

# 2) SLIPPAGE refresh
try {
  $r2 = Invoke-RestMethod -Method Post -Uri "$BASE/execution/slippage/refresh"
  Write-Log ("slippage.refresh ok=" + $r2.ok + " count=" + $r2.count)
} catch {
  Write-Log ("slippage.refresh error: " + $_.Exception.Message)
}

Start-Sleep -Seconds 2

# 3) SLIPPAGE summary (for the log)
try {
  $r3 = Invoke-RestMethod -Uri "$BASE/execution/slippage/summary"
  Write-Log ("slippage.summary: count=" + $r3.count + " mean_bps=" + $r3.slip_bps_mean + " vwap=" + $r3.vwap)
} catch {
  Write-Log ("slippage.summary error: " + $_.Exception.Message)
}

Write-Log "Weekend validation run completed."
