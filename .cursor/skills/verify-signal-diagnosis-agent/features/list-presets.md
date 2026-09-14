# List demo presets

A user can list the five Demo synthetic presets from the CLI or the Web UI
without a DeepSeek key. The same catalog backs `signal-diag diagnose synthetic`
and the UI preset `<select>`.

## Sub-features

- `presets-cli` prints the Demo catalog from `signal-diag presets`.
- `presets-http` returns the same catalog from `GET /api/v1/presets`.
- `presets-ids` exposes ids `clean_periodic`, `clipping`, `harmonic_distortion`, `combined_distortion`, `noise_inconclusive` (from `src\signal_diag\app\presets.py`).

## How to get to it (user POV)

- In a terminal at the repo root, run `signal-diag presets`.
- Open `http://127.0.0.1:8765/`, choose **Demo preset**, open the Preset select.
- Call `GET /api/v1/presets` (what the UI uses to fill the select).

## Driving it with signal-diag CLI/HTTP

Preconditions:

- `.venv\Scripts\signal-diag.exe` exists.
- No DeepSeek key required.
- HTTP path requires a serve instance this run started on port 8765 (or the port recorded in evidence).
- Doctor has listed the five ids from source `presets.py` / CLI.

- **CLI catalog.** Run `.\.venv\Scripts\signal-diag.exe presets`. Exit code `0`. Stdout lists the five `preset_id` values above (labels: Clean periodic, Clipping, Harmonic distortion, Combined distortion, Inconclusive noise). Save stdout to `evidence/presets-cli.txt`.
- **HTTP catalog.** With serve up, run `Invoke-RestMethod http://127.0.0.1:8765/api/v1/presets`. Status 200. Body is a JSON array of descriptors with `preset_id`, `label`, `description`, `sample_rate_hz` 48000, `duration_s` 1.0, `channels` 1. Save to `evidence/presets-http.json`.
- **Ids match.** The CLI ids and HTTP `preset_id` set are identical. Missing `clipping` fails the proof.
- **Proof.** Both artifacts exist after Cleanup and contain `clipping` and `noise_inconclusive`.

## Gotchas

- `signal-diag diagnose synthetic clipping` is a different feature; listing is not diagnosing.
- HTTP 503 on diagnose does not mean presets failed; presets must load without credentials.
- Do not use evaluation-manifest case ids as Demo preset ids. The Demo catalog is isolated in `app\presets.py`.
