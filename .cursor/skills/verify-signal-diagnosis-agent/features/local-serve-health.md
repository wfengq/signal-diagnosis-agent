# Local serve, health, UI shell

A user can start the local no-auth Demo server, open the Web UI, and load
health / presets / accepted evaluation summary without submitting a diagnosis
and without a DeepSeek key.

## Sub-features

- `serve-bind` starts `signal-diag serve --host 127.0.0.1 --port 8765`.
- `health` answers `GET /api/v1/health` with `"status":"ok"`.
- `ui-shell` serves `GET /` HTML titled `Signal Diagnosis Agent` with the no-auth and 1%/5% demo-threshold banners.
- `evaluation-summary` returns the accepted official summary via `GET /api/v1/evaluation-summary` with no model call.

## How to get to it (user POV)

- Run `signal-diag serve --host 127.0.0.1 --port 8765` (README Demo).
- Open `http://127.0.0.1:8765/` in a browser.
- Health/presets/evaluation-summary load in the background without credentials.

## Driving it with signal-diag CLI/HTTP

Preconditions:

- Launch recorded a PID in `evidence/serve.pid`.
- Port 8765 (or the recorded port) is owned by that PID.
- `DEEPSEEK_API_KEY` may be absent.

- **Ready.** Poll `Invoke-RestMethod http://127.0.0.1:8765/api/v1/health` until `"status":"ok"` or 15s timeout. Save body to `evidence/health.json`. `planner_configured` is a boolean; false is expected without a key.
- **UI shell.** `Invoke-WebRequest http://127.0.0.1:8765/` status 200. Content includes `<title>Signal Diagnosis Agent</title>`, `form#diagnose-form`, `button#submit-run`, and the banner `local single-user/no-auth service`. Save a snippet to `evidence/ui-index.html`.
- **Evaluation summary.** `GET /api/v1/evaluation-summary` status 200 JSON. This is the committed accepted bundle summary, not a live model run. Save to `evidence/evaluation-summary.json`.
- **Static assets.** `GET /static/app.js` and `GET /static/styles.css` return 200.
- **Proof.** `health.json` has `"status":"ok"`; `ui-index.html` contains the title; the serve PID is the one in `evidence/serve.pid`.

## Gotchas

- Port 8000 is **not** the documented Demo port. Use 8765 unless Doctor recorded a conflict.
- Binding `0.0.0.0` is out of scope; do not.
- `planner_configured: false` is not a failed Doctor. Submitting a diagnosis without a key must not be reported as a UI-shell failure.
- Evaluation-summary is frozen evidence, not proof that this process called DeepSeek.
- If 8765 is taken by another owner's process, do not kill it; pick another port or stop.
