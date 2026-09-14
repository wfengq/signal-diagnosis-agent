# cleanup.ps1 — stop only the serve PID this run started. Keep evidence/.
# Invoke from repo root:
#   . .\.cursor\skills\verify-signal-diagnosis-agent\helpers\cleanup.ps1
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = (Get-Location).Path
$evidence = Join-Path $repo '.cursor\skills\verify-signal-diagnosis-agent\evidence'
$pidFile = Join-Path $evidence 'serve.pid'
if (-not (Test-Path -LiteralPath $pidFile)) {
  Write-Output 'no serve.pid; nothing to stop'
  exit 0
}
$sid = [int]((Get-Content -LiteralPath $pidFile -Raw).Trim())
$proc = Get-Process -Id $sid -ErrorAction SilentlyContinue
if ($null -eq $proc) {
  Write-Output "pid $sid already gone"
} else {
  Stop-Process -Id $sid -Force
  Start-Sleep -Seconds 1
  if (Get-Process -Id $sid -ErrorAction SilentlyContinue) {
    Write-Output "pid $sid still running after Stop-Process"
    exit 1
  }
  Write-Output "stopped pid $sid"
}
# Do not remove evidence artifacts. Do not touch output/ or tmp/.
if (-not (Test-Path -LiteralPath $evidence)) {
  Write-Output 'ERROR: evidence directory missing after cleanup'
  exit 1
}
Get-ChildItem -LiteralPath $evidence | Select-Object Name, Length | Format-Table | Out-String | Write-Output
exit 0
