"""T-CX420–T-CX423: Web UI layout and Chinese interface (web-ui-layout design)."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "src" / "signal_diag" / "app" / "static"

TECH_PANEL_IDS = (
    "declaration-panel",
    "qualification-panel",
    "limitation-panel",
    "waveform-panel",
    "trace-panel",
    "evidence-panel",
    "rules-panel",
    "knowledge-panel",
)
MANUAL_FORM_IDS = (
    "diagnose-form",
    "source-mode-wav",
    "source-mode-preset",
    "wav-file",
    "preset-id",
    "diagnostic-mode",
    "nominal-fundamental-hz",
    "reference-file",
    "question",
    "channel",
    "submit-run",
)


def _text(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def _function_body(script: str, name: str) -> str:
    start = script.index(f"function {name}")
    rest = script[start + 1 :]
    match = re.search(r"\n(?:async )?function ", rest)
    return script[start:] if match is None else script[start : start + 1 + match.start()]


def _element(html: str, element_id: str) -> str:
    match = re.search(rf'<[a-z]+[^>]*\bid="{re.escape(element_id)}"[^>]*>', html)
    assert match is not None, element_id
    return match.group(0)


def test_t_cx420_intake_first_and_manual_form_collapsed() -> None:
    html = _text("index.html")
    assert html.index('id="intake-panel"') < html.index('id="manual-panel"')
    manual = _element(html, "manual-panel")
    assert manual.startswith("<details")
    assert " open" not in manual
    start = html.index('id="manual-panel"')
    end = html.index("</details>", start)
    block = html[start:end]
    for element_id in MANUAL_FORM_IDS:
        assert f'id="{element_id}"' in block, element_id
    assert "高级：手动设置上下文" in block


def test_t_cx421_summary_card_and_collapsed_technical_panels() -> None:
    html = _text("index.html")
    script = _text("app.js")
    assert 'id="summary-card"' in html
    summary = _function_body(script, "renderSummary")
    for field in ("outcome", "confidence_label", "stimulus_context", "context_origin", "claims"):
        assert field in summary, field
    assert "report-json" in html[html.index('id="summary-card"') :]
    for panel_id in TECH_PANEL_IDS:
        wrapper = html.rindex("<details", 0, html.index(f'id="{panel_id}"'))
        tag = html[wrapper : html.index(">", wrapper) + 1]
        assert 'class="tech-panel"' in tag, panel_id
        assert " open" not in tag, panel_id
    assert _element(html, "tech-panels").count("hidden") == 1
    terminal = _function_body(script, "renderTerminal")
    assert "setTechPanelVisible" in terminal
    evaluation = html.rindex("<details", 0, html.index('id="evaluation-panel"'))
    assert html.index('id="evaluation-panel"') > html.index('id="tech-panels"')
    assert " open" not in html[evaluation : html.index(">", evaluation)]
    assert html.index('id="summary-card"') < html.index('id="guidance-panel"')
    assert html.index('id="guidance-panel"') < html.index('id="tech-panels"')


def test_t_cx422_two_column_grid_without_frameworks() -> None:
    html = _text("index.html")
    css = _text("styles.css")
    assert 'class="layout"' in html
    assert 'class="col-input"' in html
    assert 'class="col-results"' in html
    assert "grid-template-columns" in css
    assert re.search(r"@media \(min-width: 1100px\)", css)
    assert "position: sticky" in css
    for marker in ("cdn", "react", "vue", "tailwind", "bootstrap"):
        assert marker not in html.casefold()


def test_t_cx423_chinese_interface_keeps_pinned_english() -> None:
    html = _text("index.html")
    script = _text("app.js")
    page = f"{html}\n{script}"
    assert '<html lang="zh-CN">' in html
    for chinese in ("描述问题", "诊断摘要", "技术细节", "运行状态", "上下文升级建议"):
        assert chinese in page, chinese
    pinned_html = (
        "local single-user/no-auth",
        "1% clipping",
        "5% THD",
        "Why does this signal sound distorted?",
        "Unknown one-WAV signal",
        "Declared single tone",
        "Compare with clean reference",
    )
    for text in pinned_html:
        assert text in html, text
    pinned_script = (
        "Unknown one-WAV signal",
        "Declared single tone",
        "Compare with clean reference",
        "Optional upgrades:",
        "reference WAV",
        "nominal fundamental (Hz)",
        "stimulus kind single tone",
        "held-out Agent slots",
        "behavioral-failure",
        "outcome error",
        "V0.2 demonstration targets are not industry standards or SLAs.",
    )
    for text in pinned_script:
        assert text in script, text
    assert "Why does this signal sound distorted?" in _text("intake_flow.js")
