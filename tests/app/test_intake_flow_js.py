"""T-CX418–T-CX419: browser intake helpers, executed under Node (D047, §25).

Node runs the packaged ``static/intake_flow.js`` unchanged. GitHub's
``ubuntu-latest`` runner ships Node; a missing binary fails these tests rather
than skipping them.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from signal_diag.app.pcm_wav import encode_pcm32_wav

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "src" / "signal_diag" / "app" / "static"
FLOW_JS = STATIC_DIR / "intake_flow.js"
CASES_PATH = Path(__file__).resolve().parent / "fixtures" / "intake_assembly_cases.json"
FORBIDDEN_HTML_SINKS = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write")


def _node(script: str, tmp_path: Path) -> Any:
    node = shutil.which("node")
    assert node is not None, "T-CX418/T-CX419 require Node on PATH"
    harness = tmp_path / "harness.js"
    harness.write_text(
        f"const flow = require({json.dumps(str(FLOW_JS))});\n{script}\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(harness)], capture_output=True, text=True, timeout=60, check=False
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_t_cx419_js_assembly_matches_shared_table(tmp_path: Path) -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    script = f"""
const cases = {json.dumps(cases)};
const out = {{}};
for (const item of cases) {{
  try {{
    const got = flow.assembleIntakeSubmission(item.selection, item.filenames, item.test_file);
    out[item.id] = got;
  }} catch (error) {{
    out[item.id] = {{ error: error.code || "uncoded" }};
  }}
}}
process.stdout.write(JSON.stringify(out));
"""
    results = _node(script, tmp_path)
    for case in cases:
        assert results[case["id"]] == case["expected"], case["id"]


def test_t_cx419_js_downgrade_message_matches_python(tmp_path: Path) -> None:
    from signal_diag.agent.intake import ConfirmedContext
    from signal_diag.app.intake_flow import IntakeAssembly, downgrade_message

    shapes = [
        (None, ["mode"]),
        ("paired_reference", ["reference_file"]),
        ("nominal_single_tone", ["nominal_fundamental_hz", "stimulus_kind"]),
        (None, []),
    ]
    script = f"""
const shapes = {json.dumps(shapes)};
process.stdout.write(JSON.stringify(shapes.map(([from, fields]) =>
  flow.intakeDowngradeMessage({{ downgraded_from: from, unconfirmed_fields: fields }}))));
"""
    js_messages = _node(script, tmp_path)
    py_messages = [
        downgrade_message(
            IntakeAssembly(
                confirmed=ConfirmedContext(mode="single_signal"),
                downgraded_from=source,  # type: ignore[arg-type]
                unconfirmed_fields=tuple(fields),
            )
        )
        for source, fields in shapes
    ]
    assert js_messages == py_messages


def test_t_cx418_draft_request_carries_metadata_only(tmp_path: Path) -> None:
    script = """
const body = flow.buildDraftRequestBody("the 1 kHz tone is harsh", ["new.wav", "old.wav"],
  "new.wav", [48000, null]);
const full = flow.buildDraftRequestBody("t", ["new.wav"], "new.wav", [44100]);
process.stdout.write(JSON.stringify({ body, full }));
"""
    payload = _node(script, tmp_path)
    assert payload["body"] == {
        "text": "the 1 kHz tone is harsh",
        "filenames": ["new.wav", "old.wav"],
        "test_file": "new.wav",
        "sample_rates_hz": [],
    }
    assert payload["full"]["sample_rates_hz"] == [44100]


def test_t_cx418_diagnose_form_carries_confirmed_fields_and_audio(tmp_path: Path) -> None:
    script = """
const files = {
  "new.wav": new Blob([new Uint8Array([1, 2, 3])]),
  "old.wav": new Blob([new Uint8Array([4, 5])]),
};
const describe = (form) => {
  const out = {};
  for (const [key, value] of form.entries()) {
    out[key] = typeof value === "string" ? value : { file: value.name, size: value.size };
  }
  return out;
};
const paired = flow.assembleIntakeSubmission(
  { mode: "paired_reference", reference_file: "old.wav" }, ["new.wav", "old.wav"], "new.wav");
const nominal = flow.assembleIntakeSubmission(
  { mode: "nominal_single_tone", nominal_fundamental_hz: 440, stimulus_kind: "single_tone" },
  ["new.wav", "old.wav"], "new.wav");
const downgraded = flow.assembleIntakeSubmission(
  { mode: "paired_reference", reference_file: null }, ["new.wav", "old.wav"], "new.wav");
process.stdout.write(JSON.stringify({
  paired: describe(flow.buildIntakeDiagnoseForm(paired, files, "new.wav", "mixdown")),
  nominal: describe(flow.buildIntakeDiagnoseForm(nominal, files, "new.wav", "left")),
  downgraded: describe(flow.buildIntakeDiagnoseForm(downgraded, files, "new.wav", "mixdown")),
}));
"""
    forms = _node(script, tmp_path)
    common = {
        "test_file": {"file": "new.wav", "size": 3},
        "user_request": "Why does this signal sound distorted?",
        "context_origin": "intake_confirmed",
    }
    assert forms["paired"] == {
        **common,
        "mode": "paired_reference",
        "channel": "mixdown",
        "reference_file": {"file": "old.wav", "size": 2},
    }
    assert forms["nominal"] == {
        **common,
        "mode": "nominal_single_tone",
        "channel": "left",
        "nominal_fundamental_hz": "440",
        "stimulus_kind": "single_tone",
    }
    assert forms["downgraded"] == {**common, "mode": "single_signal", "channel": "mixdown"}


def test_t_cx418_wav_header_sample_rate_matches_python(tmp_path: Path) -> None:
    from signal_diag.app.intake_flow import wav_header_sample_rate

    samples = np.zeros((32, 1), dtype=np.float32)
    blobs = {
        "pcm8k": encode_pcm32_wav(samples, sample_rate_hz=8000),
        "pcm48k": encode_pcm32_wav(samples, sample_rate_hz=48000),
        "empty": b"",
        "junk": b"RIFF\x00\x00\x00\x00WAVEjunk",
        "text": b"not a wav file at all",
    }
    script = f"""
const blobs = {json.dumps({name: list(data) for name, data in blobs.items()})};
const out = {{}};
for (const [name, bytes] of Object.entries(blobs)) {{
  out[name] = flow.wavHeaderSampleRate(new Uint8Array(bytes).buffer);
}}
process.stdout.write(JSON.stringify(out));
"""
    js_rates = _node(script, tmp_path)
    for name, data in blobs.items():
        expected = wav_header_sample_rate(data)
        assert js_rates[name] == (None if expected is None else int(expected)), name


def _function_body(script: str, name: str) -> str:
    start = script.index(f"function {name}")
    rest = script[start + 1 :]
    match = re.search(r"\n(?:async )?function ", rest)
    return script[start:] if match is None else script[start : start + 1 + match.start()]


def test_t_cx418_ui_wiring_keeps_audio_out_of_the_draft_request() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    flow = FLOW_JS.read_text(encoding="utf-8")
    assert html.index('src="/static/intake_flow.js"') < html.index('src="/static/app.js"')
    for element_id in (
        "intake-text",
        "intake-files",
        "intake-test-file",
        "intake-draft",
        "intake-confirm",
        "intake-mode",
        "intake-mode-confirmed",
        "intake-reference",
        "intake-reference-confirmed",
        "intake-nominal-hz",
        "intake-nominal-confirmed",
        "intake-stimulus-kind",
        "intake-stimulus-confirmed",
        "intake-plan",
        "intake-diagnose",
    ):
        assert f'id="{element_id}"' in html, element_id
    assert "Copy confirmed fields into" not in html
    draft = _function_body(app, "requestIntakeDraft")
    assert "buildDraftRequestBody" in draft
    assert "JSON.stringify" in draft
    assert "FormData" not in draft
    assert "arrayBuffer" not in draft
    diagnose = _function_body(app, "submitIntakeDiagnosis")
    assert "buildIntakeDiagnoseForm" in diagnose
    assert "assembleIntakeSubmission" in diagnose
    assert "pollRun" in diagnose
    assert "context_origin" in _function_body(app, "renderDeclaration")
    for sink in FORBIDDEN_HTML_SINKS:
        assert sink not in flow
        assert sink not in app
