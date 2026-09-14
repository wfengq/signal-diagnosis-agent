# signal-diagnosis-agent verification map

This directory is the maintained source for verifying the user-facing behavior
of signal-diagnosis-agent. Read the index before driving the app, then use the
matching feature file as the recipe.

## Baseline preconditions

- Work in `C:\Users\wei\Desktop\招聘\signal-diagnosis-agent` on the user's
  Windows machine. PowerShell. UTF-8 console if you capture Chinese paths.
- `.venv\Scripts\signal-diag.exe` exists (see Launch in SKILL.md).
- Do not set `DEEPSEEK_API_KEY` unless the feature file's preconditions say
  you are proving a RealLLM product run.
- Evidence root:
  `.cursor/skills/verify-signal-diagnosis-agent/evidence/`
- Never drive a `signal-diag serve` instance this run did not start, unless
  Doctor has proved it is this venv, this port, and this HEAD.
- Do not delete repo-root `output/` or `tmp/`.
- V0.2 contracts frozen. ScriptedPlanner is pytest-only.

## Driving conventions

- Start every recipe from this baseline unless its preconditions say otherwise.
- Prefer CLI subcommands and HTTP paths over clicking by coordinates.
- Treat every command as literal. Keep preset ids and flags unchanged.
- CLI actions: `.\.venv\Scripts\signal-diag.exe -- …`
- HTTP actions: `Invoke-RestMethod` against `http://127.0.0.1:8765`
- After Cleanup, proof files in `evidence/` must still exist.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final screen.
- CLI proof: command, stdout, stderr, exit code.
- HTTP proof: method, URL, status, body.
- Diagnose proof: a second read of the report or run snapshot, not only 202.
- Record the feature ID and entry point with every artifact.
- Report an unreachable path with the attempted command and unmet precondition.
- Do not report RealLLM as verified because ScriptedPlanner tests passed.
- Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the
user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with signal-diag CLI/HTTP` (pytest file uses pytest as harness)
4. `Gotchas`

## Features

- [List demo presets](./list-presets.md) — CLI `presets` and GET `/api/v1/presets`.
- [Local serve, health, UI shell](./local-serve-health.md) — `signal-diag serve`, health, evaluation-summary, `/`.
- [Diagnose a synthetic preset](./diagnose-synthetic.md) — CLI/HTTP product diagnose; fail-closed without credentials.
- [Diagnose a WAV file](./diagnose-wav.md) — bounded PCM WAV CLI/HTTP path.
- [ScriptedPlanner acceptance](./scripted-acceptance.md) — pytest deterministic Agent path; not a RealLLM proof.
