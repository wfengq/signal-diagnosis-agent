# Diagnose a synthetic preset

A user asks “Why does this signal sound distorted?” of a Demo preset. The
product path uses `RealLLMPlanner`. Without `DEEPSEEK_API_KEY` the app
returns `planner_not_configured` and does **not** fall back to ScriptedPlanner.

## Sub-features

- `synthetic-cli-no-key` — `signal-diag diagnose synthetic clipping` exits 2 with `planner_not_configured` when the key is missing.
- `synthetic-http-no-key` — `POST /api/v1/runs/synthetic` returns 503 with the same code.
- `synthetic-cli-real` — with a key, CLI completes (exit 0) a diagnosis for preset `clipping` and can write JSON/HTML reports.
- `synthetic-http-real` — with a key, POST 202 then a terminal snapshot/report; UI `button#submit-run` with Demo preset selected.

## How to get to it (user POV)

- CLI: `signal-diag diagnose synthetic clipping`
- CLI with reports: `signal-diag diagnose synthetic clipping --output json --html-output report.html`
- UI: choose **Demo preset**, pick Clipping, keep default question, click **Run diagnosis**.
- HTTP: `POST /api/v1/runs/synthetic` with `preset_id=clipping`, `user_request=Why does this signal sound distorted?`, `channel=mixdown`.

## Driving it with signal-diag CLI/HTTP

Preconditions:

- Doctor passed. Default: **no** `DEEPSEEK_API_KEY` in the shell or serve process.
- Only run the RealLLM bullets if the user provided a key for this session and `planner_configured` is true. Otherwise stop after the fail-closed bullets and report the RealLLM entry point as **not verified**.

- **Fail-closed CLI.** In an env where `Test-Path env:DEEPSEEK_API_KEY` is false, run `.\.venv\Scripts\signal-diag.exe diagnose synthetic clipping`. Expect exit **2** (usage/config). Stderr/stdout names `planner_not_configured`. Save to `evidence/diagnose-synthetic-nokey.txt`. This **is** proof of the no-silent-fallback contract.
- **Fail-closed HTTP.** `Invoke-WebRequest -Method POST -Uri http://127.0.0.1:8765/api/v1/runs/synthetic -ContentType 'application/json' -Body '{"preset_id":"clipping","user_request":"Why does this signal sound distorted?","channel":"mixdown"}'`. Expect status **503** and error code `planner_not_configured`. Save body to `evidence/diagnose-synthetic-nokey-http.json`.
- **RealLLM CLI (credentials only).** `$env:DEEPSEEK_API_KEY` set. `.\.venv\Scripts\signal-diag.exe diagnose synthetic clipping --output json --html-output evidence\clipping-report.html`. Exit 0. JSON includes a structured diagnosis that cites same-run `ev_*` evidence. Save JSON to `evidence/clipping-report.json`.
- **RealLLM HTTP (credentials only).** POST synthetic → 202 with a run id. Poll the GET run route from `api.py` until status is not `queued`/`running`. Fetch the JSON/HTML report links the UI exposes (`#report-json`, `#report-html`). A 202 without a completed snapshot is not proof.
- **Proof (default credential-less run).** The two fail-closed artifacts exist after Cleanup. Do not label this feature “RealLLM verified”.

## Gotchas

- Never inject ScriptedPlanner through the product CLI/API to “make diagnose pass”.
- Preset id is `clipping`, not `clip` or an evaluation case id.
- Exit 0 on diagnose includes inconclusive / no-supported-fault; still capture the report.
- Combined/harmonic/noise presets are additional entry points; a clipping-only proof does not cover them — record skip, do not claim them.
- V0.3 contextual WAV submit is a different product surface; do not use it to prove this V0.2 Demo preset path.
