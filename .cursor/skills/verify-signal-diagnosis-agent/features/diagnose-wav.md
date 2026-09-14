# Diagnose a WAV file

A user submits a bounded integer-PCM WAV (CLI path or UI file input). The same
`DiagnosisApplicationService` runs as for presets. Without credentials the
product path fails closed.

## Sub-features

- `wav-cli-demo` — `signal-diag diagnose wav docs\demo\phase5\v0_2_acceptance\input_clipping_16bit.wav`
- `wav-http` — `POST /api/v1/runs/wav` multipart upload
- `wav-reject` — RIFX / IEEE float / >2 channels / oversize rejected (`unsupported_wav` / `invalid_wav` / `payload_too_large` / `signal_limit_exceeded`)
- `wav-channel` — `--channel mixdown` (default), `left`, or `right`

## How to get to it (user POV)

- CLI: `signal-diag diagnose wav path\to\file.wav`
- CLI reports: `signal-diag diagnose wav path\to\file.wav --channel mixdown --output json --html-output report.html`
- UI: **WAV file** radio (default), choose a `.wav`, **Run diagnosis**.
- HTTP: POST multipart to `/api/v1/runs/wav`.

## Driving it with signal-diag CLI/HTTP

Preconditions:

- Demo fixture exists: `docs\demo\phase5\v0_2_acceptance\input_clipping_16bit.wav`.
- WAV boundary (README): little-endian RIFF/WAVE integer PCM, 8/16/24/32-bit, mono or stereo, 8 kHz–192 kHz, max 20 MiB / 2e6 frames / 30 s.
- Default: no `DEEPSEEK_API_KEY`. RealLLM bullets only if credentials present and `planner_configured` is true.

- **Fail-closed CLI.** `.\.venv\Scripts\signal-diag.exe diagnose wav docs\demo\phase5\v0_2_acceptance\input_clipping_16bit.wav`. Without a key, exit 2 / `planner_not_configured`. Save to `evidence/diagnose-wav-nokey.txt`.
- **Fixture present.** `Test-Path` the demo WAV; record size. A missing fixture is a skip with that path, not a product failure.
- **Reject path (no model).** Feed a non-WAV or empty file if you need boundary proof; expect exit 2 and a usage/input code, not a diagnosis.
- **RealLLM CLI (credentials only).** Same command with `--output json --html-output evidence\wav-report.html`. Exit 0. Capture JSON.
- **Proof (default).** Fail-closed artifact plus `Test-Path` of the demo WAV. Do not claim RealLLM WAV diagnosis without the key.

## Gotchas

- Mixdown is the default channel; stereo files still need an explicit channel if you assert left/right.
- Do not grab files from repo-root `output/` or `tmp/` as fixtures (user data).
- External-study WAVs under `private/external_wav/` are gitignored and not a Demo fixture.
- UI accept attribute is `.wav,audio/wav`; other audio types should fail closed.
