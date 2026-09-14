# doctor.ps1 — read-only: is this checkout worth driving?
# Invoke from repo root:
#   . .\.cursor\skills\verify-signal-diagnosis-agent\helpers\doctor.ps1
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = (Get-Location).Path
$evidence = Join-Path $repo '.cursor\skills\verify-signal-diagnosis-agent\evidence'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null

$cli = Join-Path $repo '.venv\Scripts\signal-diag.exe'
$report = [ordered]@{
  repo = $repo
  head = $null
  branch = $null
  cli_exists = Test-Path -LiteralPath $cli
  presets_exit = $null
  presets_ids = @()
  health = $null
  serve_pid = $null
  serve_running = $false
  ok = $false
  errors = @()
}

if (Test-Path -LiteralPath (Join-Path $repo '.git')) {
  $report.head = (git rev-parse HEAD).Trim()
  $report.branch = (git branch --show-current).Trim()
  $report.head | Set-Content -Encoding utf8 (Join-Path $evidence 'git-head.txt')
} else {
  $report.errors += 'not a git checkout'
}

if (-not $report.cli_exists) {
  $report.errors += 'missing .venv\Scripts\signal-diag.exe'
} else {
  $p = Start-Process -FilePath $cli -ArgumentList @('presets') -WorkingDirectory $repo -Wait -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $evidence 'presets-cli.txt') `
    -RedirectStandardError (Join-Path $evidence 'presets-cli.err.txt')
  $report.presets_exit = $p.ExitCode
  $txt = Get-Content -LiteralPath (Join-Path $evidence 'presets-cli.txt') -Raw -ErrorAction SilentlyContinue
  $low = if ($txt) { $txt.ToLowerInvariant() } else { '' }
  foreach ($id in @('clean_periodic','clipping','harmonic_distortion','combined_distortion','noise_inconclusive')) {
    if ($low.Contains($id.ToLowerInvariant())) { $report.presets_ids += $id }
  }
  if ($report.presets_exit -ne 0) { $report.errors += "presets exit $($report.presets_exit)" }
  if ($report.presets_exit -eq 0 -and -not $txt) { $report.errors += 'presets stdout empty' }
  if ($report.presets_ids.Count -lt 5 -and $report.presets_exit -eq 0) {
    # CLI may print labels; require at least the word clipping plus nonempty catalog
    if (-not $low.Contains('clipping')) { $report.errors += 'preset catalog missing clipping' }
  }
}

$pidFile = Join-Path $evidence 'serve.pid'
if (Test-Path -LiteralPath $pidFile) {
  $sid = [int]((Get-Content -LiteralPath $pidFile -Raw).Trim())
  $report.serve_pid = $sid
  $proc = Get-Process -Id $sid -ErrorAction SilentlyContinue
  $report.serve_running = $null -ne $proc
}

$port = 8765
$healthUrl = "http://127.0.0.1:$port/api/v1/health"
try {
  $report.health = Invoke-RestMethod -Uri $healthUrl -Method GET -TimeoutSec 5
} catch {
  if ($report.serve_running) { $report.errors += "health failed: $($_.Exception.Message)" }
}

$report.ok = ($report.errors.Count -eq 0) -and $report.cli_exists -and ($report.presets_exit -eq 0)
$json = $report | ConvertTo-Json -Depth 6
$json | Set-Content -Encoding utf8 (Join-Path $evidence 'doctor.json')
Write-Output $json
if (-not $report.ok) { exit 1 }
exit 0
