"""Phase B Task 6: regression workbench static UI."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "src" / "signal_diag" / "app" / "static"
APP_API = PROJECT_ROOT / "src" / "signal_diag" / "app" / "api.py"
SECTION_IDS = (
    "goal-panel",
    "files-panel",
    "results-panel",
    "retest-panel",
    "export-panel",
)
FORBIDDEN_HTML_SINKS = (
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
)


def _static_text(name: str) -> str:
    path = STATIC_DIR / name
    assert path.is_file(), f"missing packaged asset {name}"
    return path.read_text(encoding="utf-8")


def test_regression_packaged_assets_and_section_order() -> None:
    html = _static_text("regression.html")
    script = _static_text("regression.js")
    assert 'href="/static/styles.css"' in html
    assert 'src="/static/regression.js"' in script or 'src="/static/regression.js"' in html
    positions = [html.index(f'id="{section}"') for section in SECTION_IDS]
    assert positions == sorted(positions)
    assert "Reporting measurement changes only" in html
    assert "no approved comparison tolerances yet" in html


def test_regression_js_api_bindings_and_safety() -> None:
    script = _static_text("regression.js")
    for sink in FORBIDDEN_HTML_SINKS:
        assert sink not in script
    assert "/api/v1/regression/capabilities" in script
    assert "/api/v1/regression/cases" in script
    assert "pendingRequestIds" in script
    assert "state.caseId" in script or "caseId" in script
    assert "textContent" in script
    assert "replaceChildren" in script
    assert "service restarted" in script.casefold() or "no longer available" in script.casefold()
    assert "pass-badge" not in script
    assert "overall pass" not in script.casefold()
    assert re.search(
        r"fundamental_hz:\s*200\.0",
        script,
    ) is None


def test_index_links_to_regression_workbench() -> None:
    html = _static_text("index.html")
    assert 'href="/regression"' in html


def test_api_static_media_types_include_regression_js() -> None:
    api_source = APP_API.read_text(encoding="utf-8")
    assert '"regression.js": "text/javascript; charset=utf-8"' in api_source


def test_regression_html_has_no_pass_badge() -> None:
    html = _static_text("regression.html")
    assert "pass-badge" not in html
    assert not re.search(r"class=\"[^\"]*pass[^\"]*\"", html, flags=re.IGNORECASE)


def test_ui_has_declaration_inputs_and_no_wording_literals() -> None:
    html = _static_text("regression.html")
    js = _static_text("regression.js")
    for element_id in ("fs-periodic", "fs-baseline-independent", "fs-candidate-independent"):
        assert f'id="{element_id}"' in html
    assert html.count('value="unknown" selected') >= 3
    assert "full_scale_checks" in js and "full_scale_declarations" in js and "lines" in js
    assert "full-scale threshold" not in js.casefold()
    assert "overall pass" not in js.casefold()


def test_ui_renders_ratio_notice_from_payload() -> None:
    js = _static_text("regression.js")
    assert "clipping_ratio_notice" in js and "flat-top" not in js.casefold()
