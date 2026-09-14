# launch-serve.ps1 — start signal-diag serve on 127.0.0.1:8765, record PID
# Invoke from repo root:
#   powershell -NoProfile -File .\.cursor\skills\verify-signal-diagnosis-agent\helpers\launch-serve.ps1
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = (Get-Location).Path
$evidence = Join-Path $repo '.cursor\skills\verify-signal-diagnosis-agent\evidence'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$cli = Join-Path $repo '.venv\Scripts\signal-diag.exe'
if (-not (Test-Path -LiteralPath $cli)) {
  Write-Output "missing $cli"
  exit 2
}
$pidFile = Join-Path $evidence 'serve.pid'
if (Test-Path -LiteralPath $pidFile) {
  $old = [int]((Get-Content -LiteralPath $pidFile -Raw).Trim())
  if (Get-Process -Id $old -ErrorAction SilentlyContinue) {
    Write-Output "already running pid $old"
    exit 0
  }
}
$log = Join-Path $evidence 'serve-stdout.txt'
$err = Join-Path $evidence 'serve-stderr.txt'
$p = Start-Process -FilePath $cli `
  -ArgumentList @('serve','--host','127.0.0.1','--port','8765') `
  -WorkingDirectory $repo -PassThru -NoNewWindow `
  -RedirectStandardOutput $log -RedirectStandardError $err
$p.Id | Set-Content -Encoding utf8 $pidFile
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/health' -TimeoutSec 2
    if ($h.status -eq 'ok') { $ok = $true; break }
  } catch { }
}
if (-not $ok) {
  Write-Output "serve pid $($p.Id) started but health not ready; see serve-stderr.txt"
  exit 1
}
Write-Output "serve pid $($p.Id) health ok"
exit 0
