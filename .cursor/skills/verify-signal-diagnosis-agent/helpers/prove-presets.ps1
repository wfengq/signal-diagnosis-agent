# prove-presets.ps1 — e2e: launch serve -> doctor -> drive list-presets -> leave evidence
# Cleanup is a separate helper so proof files survive teardown.
# Invoke from repo root:
#   powershell -NoProfile -File .\.cursor\skills\verify-signal-diagnosis-agent\helpers\prove-presets.ps1
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = (Get-Location).Path
$here = Join-Path $repo '.cursor\skills\verify-signal-diagnosis-agent\helpers'
$evidence = Join-Path $repo '.cursor\skills\verify-signal-diagnosis-agent\evidence'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null

& powershell -NoProfile -File (Join-Path $here 'launch-serve.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& powershell -NoProfile -File (Join-Path $here 'doctor.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$cli = Join-Path $repo '.venv\Scripts\signal-diag.exe'
# CLI drive (doctor already wrote presets-cli.txt; re-run for an explicit drive artifact)
$driveOut = Join-Path $evidence 'drive-presets-cli.txt'
$driveErr = Join-Path $evidence 'drive-presets-cli.err.txt'
$p = Start-Process -FilePath $cli -ArgumentList @('presets') -WorkingDirectory $repo -Wait -PassThru -NoNewWindow `
  -RedirectStandardOutput $driveOut -RedirectStandardError $driveErr
if ($p.ExitCode -ne 0) { Write-Output "presets drive exit $($p.ExitCode)"; exit $p.ExitCode }

$presets = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/presets' -Method GET -TimeoutSec 5
$presets | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $evidence 'presets-http.json')
$health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/health' -Method GET -TimeoutSec 5
$health | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $evidence 'health.json')
try {
  $page = Invoke-WebRequest -Uri 'http://127.0.0.1:8765/' -TimeoutSec 5
  $page.Content.Substring(0, [Math]::Min(2000, $page.Content.Length)) |
    Set-Content -Encoding utf8 (Join-Path $evidence 'ui-index.html')
} catch {
  $_.Exception.Message | Set-Content -Encoding utf8 (Join-Path $evidence 'ui-index.err.txt')
}

$ids = @('clean_periodic','clipping','harmonic_distortion','combined_distortion','noise_inconclusive')
$cliTxt = (Get-Content -LiteralPath $driveOut -Raw).ToLowerInvariant()
$httpTxt = Get-Content -LiteralPath (Join-Path $evidence 'presets-http.json') -Raw
$missing = @()
foreach ($id in $ids) {
  $inCli = $cliTxt.Contains($id) -or $cliTxt.Contains(($id -replace '_',' '))
  $inHttp = $httpTxt.Contains($id)
  if (-not $inCli -or -not $inHttp) { $missing += $id }
}
$result = [ordered]@{
  feature = 'list-presets'
  cli_exit = $p.ExitCode
  health_status = $health.status
  planner_configured = $health.planner_configured
  missing_ids = $missing
  ok = ($missing.Count -eq 0) -and ($p.ExitCode -eq 0) -and ($health.status -eq 'ok')
}
$result | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $evidence 'prove-presets.json')
Write-Output ($result | ConvertTo-Json)
if (-not $result.ok) { exit 1 }
exit 0
