---
name: verify-signal-diagnosis-agent
description: >-
  Drive signal-diagnosis-agent on the local Windows checkout via its argparse
  CLI (signal-diag) and FastAPI HTTP/Web UI (port 8765). Use when proving
  diagnosis, presets, health, WAV/synthetic submit, or ScriptedPlanner
  acceptance without claiming a RealLLM product run.
---

# Verify signal-diagnosis-agent

Project-local control skill for the S1 distortion-diagnosis Agent
(`signal-diagnosis-agent`). Write for the next agent that has never seen the
app. Surfaces: **CLI + FastAPI Web UI + JSON API**. Primary verification
surface is **CLI + HTTP** (easiest to drive with evidence). The native Web UI
is the same FastAPI app at `http://127.0.0.1:8765/`.

Repo on the user's machine:

```text
C:\Users\wei\Desktop\招聘\signal-diagnosis-agent
```

Expect branch `main` (renamed from `codex/v0.2-real-world-validation` on
2026-10-06). Confirm HEAD with `git rev-parse HEAD` before treating any prior
SHA as current.

V0.2 product contracts are frozen (`AGENTS.md`, `docs/CONTRACTS_V0_2.md`).
`RealLLMPlanner` is the product path. `ScriptedPlanner` is a test double and
**never** a silent product fallback. Missing `DEEPSEEK_API_KEY` must surface
`planner_not_configured` (CLI exit 2 / HTTP 503). Do not report RealLLM as
verified without credentials. Do not announce release-ready. Do not commit or
push unless the user explicitly asks.

This checkout also contains later V0.3 contextual study code on the same
branch. This skill verifies the V0.2 user surfaces (CLI / HTTP / UI) and the
deterministic ScriptedPlanner pytest path. A v9.x RealLLM eval bundle is not
proof of this skill.

## Launch

Working directory: the repo root above. PowerShell. Prefer the existing
`.venv` (this machine already ran pytest 3.11/3.12/3.14). Do not invent a
new product command.

One-time deps (only if `.\.venv\Scripts\signal-diag.exe` is missing):

```powershell
Set-Location -LiteralPath 'C:\Users\wei\Desktop\招聘\signal-diagnosis-agent'
uv sync --extra app --extra llm --extra dev
```

If `uv` is unavailable, the README path is:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[app,llm,dev]"
```

**HTTP / Web UI instance** (long-running). Port **8765** is the documented Demo
port (8000 was busy on the acceptance machine). Record the PID you started.
Ready when `GET /api/v1/health` returns JSON with `"status":"ok"`.

```powershell
$repo = 'C:\Users\wei\Desktop\招聘\signal-diagnosis-agent'
Set-Location -LiteralPath $repo
$evidence = Join-Path $repo '.cursor\skills\verify-signal-diagnosis-agent\evidence'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$log = Join-Path $evidence 'serve-stdout.txt'
$err = Join-Path $evidence 'serve-stderr.txt'
# Do not set DEEPSEEK_API_KEY unless the user asked for a RealLLM run.
$p = Start-Process -FilePath (Join-Path $repo '.venv\Scripts\signal-diag.exe') `
  -ArgumentList @('serve','--host','127.0.0.1','--port','8765') `
  -WorkingDirectory $repo -PassThru -NoNewWindow `
  -RedirectStandardOutput $log -RedirectStandardError $err
$p.Id | Set-Content -Encoding utf8 (Join-Path $evidence 'serve.pid')
# Wait until health answers (see Doctor). Teardown: see Cleanup.
```

Equivalent documented command if you already have a foreground terminal:

```text
signal-diag serve --host 127.0.0.1 --port 8765
```

The process prints a local single-user/no-auth warning. Do not bind `0.0.0.0`
or expose the port.

**CLI-only drives** (presets, diagnose, pytest) do not need a server: launch
means the venv is installed, then each drive is its own process.

Two instances cannot share port 8765. If 8765 is already in use, either drive
that instance only after Doctor proves it is **this** venv's `signal-diag`
(see Doctor), or start a second instance on a free port and record that port
in evidence. Never kill a process you did not start.

## Doctor

Read-only. Run first whenever anything looks off.

```powershell
powershell -NoProfile -File .\.cursor\skills\verify-signal-diagnosis-agent\helpers\doctor.ps1
```

The helper (repo-relative) checks:

1. `git rev-parse HEAD` and `git branch --show-current` (record in evidence).
2. `.\.venv\Scripts\signal-diag.exe` exists.
3. `.\.venv\Scripts\signal-diag.exe presets` exits 0 and lists the five Demo
   preset ids (see features/list-presets.md).
4. If a serve PID file exists: that PID is still running, and
   `GET http://127.0.0.1:8765/api/v1/health` returns `"status":"ok"` plus
   `planner_configured` / `planner_identity`. Confirm `planner_configured` is
   `$true` only when `DEEPSEEK_API_KEY` is present in **that** process env.
5. `GET http://127.0.0.1:8765/` returns HTML titled `Signal Diagnosis Agent`.

Dump live HTTP routes from source rather than guessing (api.py is the contract):

```powershell
Select-String -LiteralPath 'src\signal_diag\app\api.py' -Pattern '@app\.(get|post)\('
```

Known routes from `src\signal_diag\app\api.py`:

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/health` | none | `"status":"ok"`; `planner_configured` boolean |
| GET | `/api/v1/presets` | none | Demo catalog |
| GET | `/api/v1/evaluation-summary` | none | accepted official summary, no model call |
| POST | `/api/v1/runs/synthetic` | none | body `{preset_id,user_request,channel}`; **202**; 503 if planner missing |
| POST | `/api/v1/runs/wav` | none | multipart WAV; **202**; 503 if planner missing |

`api.py` continues after the POST handlers with run-snapshot / report / static
routes (`get_run`, `_completed_snapshot`, packaged `index.html` /
`styles.css` / `app.js`). **Read those remaining `@app.get` lines before
polling a run.** Do not invent paths.

If health is ok but `planner_configured` is false, HTTP diagnose submits are
expected to fail closed with `planner_not_configured` (503). That is a passing
Doctor for credential-less verification, not a reason to swap in
ScriptedPlanner.

## Drive

Harness: **signal-diag CLI/HTTP** (PowerShell + `Invoke-RestMethod` /
`signal-diag.exe`). Prefer CLI for one-shot commands; HTTP for the live
server and Web UI. pytest is the harness for ScriptedPlanner acceptance only.

Stable handles (use these, not coordinates):

- CLI entry: `signal-diag` / `.\.venv\Scripts\signal-diag.exe`
- Subcommands: `presets`, `diagnose synthetic <preset_id>`, `diagnose wav <path>`, `serve`
- Documented diagnose flags: `--channel mixdown`, `--output json`, `--html-output <file>`
- Default question: `Why does this signal sound distorted?`
- HTTP origin: `http://127.0.0.1:8765`
- UI: `form#diagnose-form`, `button#submit-run`, `select#preset-id`,
  `textarea#question`, `input#source-mode-preset`, `input#source-mode-wav`
- Banner text in `src\signal_diag\app\static\index.html` (no-auth warning and
  1%/5% demo thresholds)

CLI exit codes (README / `cli.py`): **0** completed Agent result (including
inconclusive / no-supported-fault); **1** Agent/runtime/application failure;
**2** usage, input, or configuration error (`planner_not_configured` is in
the usage/config set).

Read `features/README.md` and the matching feature file before driving.
Start from the baseline in that README.

## Evidence

Directory (survive Cleanup):

```text
.cursor/skills/verify-signal-diagnosis-agent/evidence/
```

Do not write proof into `output/` or `tmp/` at repo root (user data lives
there). Do not delete those directories.

Proof standards:

- Exercise the real CLI or HTTP user path, not internal setters.
- Capture the command/request **and** the resulting payload/exit code.
- For a mutation (diagnose), capture a second read (report JSON, GET run
  snapshot, or HTML report) — a 202 alone is not proof.
- `ScriptedPlanner` pytest is valid proof **only** for the scripted-acceptance
  feature. It does not prove the product RealLLM path.
- Missing credentials: prove the fail-closed error (`planner_not_configured`),
  never a completed diagnosis attributed to RealLLM.
- Do not treat committed Phase 4/5 bundles as a live proof of this run.

Minimum artifacts for a CLI/HTTP proof:

- `git-head.txt`, `doctor.json` / `doctor-health.json`
- command transcript with exit code (`presets-cli.txt` or similar)
- HTTP body (`presets-http.json`, `health.json`)
- `serve.pid` if a server was started
- After Cleanup: the same files still exist

## Cleanup

Kill **only** the PID in `evidence/serve.pid` (the process this run started).
Never `Stop-Process -Name signal-diag` / `Get-Process | Stop-Process`.

```powershell
powershell -NoProfile -File .\.cursor\skills\verify-signal-diagnosis-agent\helpers\cleanup.ps1
```

Cleanup removes the serve process and scratch logs you redirected **only if**
you copied them into evidence first. It must **not** delete
`evidence/` artifacts, `output/`, `tmp/`, `.venv`, or user WAVs.

After cleanup, confirm `evidence/` still contains the proof files and that
the saved PID is no longer running.

## Helpers

All helpers are PowerShell, UTF-8, invoked from repo root:

```powershell
powershell -NoProfile -File .\.cursor\skills\verify-signal-diagnosis-agent\helpers\launch-serve.ps1
powershell -NoProfile -File .\.cursor\skills\verify-signal-diagnosis-agent\helpers\doctor.ps1
powershell -NoProfile -File .\.cursor\skills\verify-signal-diagnosis-agent\helpers\prove-presets.ps1
powershell -NoProfile -File .\.cursor\skills\verify-signal-diagnosis-agent\helpers\cleanup.ps1
```

`prove-presets.ps1` is the seeded end-to-end recipe: launch serve on 8765 →
doctor → drive `list-presets` (CLI + HTTP) → write evidence. Then run
`cleanup.ps1` and confirm `evidence/` still has those files. `prove-presets.ps1`
already calls launch + doctor; the extra launch/doctor lines are for
step-by-step runs.

## Feature map

`.cursor/skills/verify-signal-diagnosis-agent/features/`

Keep `/maintain-verification-skill` in mind as the app changes.
