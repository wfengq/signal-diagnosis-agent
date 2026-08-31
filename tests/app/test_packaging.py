"""Checkpoint AC — packaging metadata, demo WAV, smoke scripts, and CI (T281–T284)."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import tomllib
from pathlib import Path
from types import ModuleType

from signal_diag.signal import load_wav_bytes

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
CI_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
CREATE_WAV_PATH = PROJECT_ROOT / "scripts" / "create_phase5_demo_wav.py"
SMOKE_PATH = PROJECT_ROOT / "scripts" / "smoke_installed_phase5.py"
VERIFY_PATH = PROJECT_ROOT / "scripts" / "verify_phase5_wheel.py"
DEMO_WAV_SHA256 = "970c37cc879b32fea80f66cdbc31305b45d04c654b53fbf0633e4ed4dcdf416e"
EXPECTED_PACKAGE_DATA = {
    "signal_diag.app": ["static/*.html", "static/*.css", "static/*.js"],
    "signal_diag.evaluation": ["manifests/*.yaml", "assets/*.json"],
    "signal_diag.knowledge": ["corpus/*.md"],
    "signal_diag.rules": ["profiles/*.yaml"],
}


def _load_script(path: Path, module_name: str) -> ModuleType:
    assert path.is_file(), f"missing script {path}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _pyproject() -> dict[str, object]:
    assert PYPROJECT_PATH.is_file()
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def test_t281_console_entry_and_extras_exist() -> None:
    data = _pyproject()
    project = data["project"]
    assert project["scripts"] == {"signal-diag": "signal_diag.app.cli:main"}
    extras = project["optional-dependencies"]
    assert "app" in extras
    assert "llm" in extras
    assert "dev" in extras
    app_extra = "\n".join(extras["app"]).lower()
    llm_extra = "\n".join(extras["llm"]).lower()
    dev_extra = "\n".join(extras["dev"]).lower()
    assert "fastapi" in app_extra
    assert "openai" in llm_extra
    assert "pytest" in dev_extra
    assert "build" in dev_extra


def test_t281_core_install_does_not_require_fastapi() -> None:
    data = _pyproject()
    core = "\n".join(data["project"]["dependencies"]).lower()
    assert "fastapi" not in core
    assert "uvicorn" not in core
    assert "python-multipart" not in core
    assert "openai" not in core


def test_t281_package_data_declares_static_and_evaluation_assets() -> None:
    data = _pyproject()
    package_data = data["tool"]["setuptools"]["package-data"]
    for key, patterns in EXPECTED_PACKAGE_DATA.items():
        assert package_data[key] == patterns


def test_t282_demo_wav_bytes_match_pcm_contract_and_sha256() -> None:
    module = _load_script(CREATE_WAV_PATH, "create_phase5_demo_wav")
    payload = module.build_demo_wav_bytes()
    assert hashlib.sha256(payload).hexdigest() == DEMO_WAV_SHA256
    loaded = load_wav_bytes(payload, filename="input_clipping_16bit.wav")
    info = loaded.source_info
    assert info.num_frames == 48_000
    assert info.sample_rate_hz == 48_000
    assert info.bits_per_sample == 16
    assert info.channels == 1
    assert loaded.record.meta.sample_rate_hz == 48_000
    assert loaded.record.samples.shape[0] == 48_000


def test_t282_demo_wav_script_writes_only_cli_output(tmp_path: Path) -> None:
    module = _load_script(CREATE_WAV_PATH, "create_phase5_demo_wav_cli")
    dest = tmp_path / "out" / "input_clipping_16bit.wav"
    dest.parent.mkdir()
    assert module.main(["--output", str(dest)]) == 0
    assert dest.is_file()
    leftovers = [path for path in tmp_path.rglob("*") if path.is_file() and path != dest]
    assert leftovers == []
    loaded = load_wav_bytes(dest.read_bytes(), filename=dest.name)
    assert loaded.source_info.num_frames == 48_000
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == DEMO_WAV_SHA256


def test_t282_installed_smoke_script_is_present_and_closes_without_model() -> None:
    text = SMOKE_PATH.read_text(encoding="utf-8")
    assert "from signal_diag.app import build_product_service, list_demo_presets" in text
    assert "from signal_diag.app.reporting import load_accepted_evaluation_summary" in text
    assert "from signal_diag.signal import load_wav_bytes" in text
    assert "assert len(list_demo_presets()) == 5" in text
    assert "assert load_accepted_evaluation_summary().agent_slot_count == 80" in text
    assert "build_product_service(environ={})" in text
    assert "assert service.list_presets()" in text
    assert "aclose" in text
    assert "submit_wav" not in text
    assert "submit_synthetic" not in text
    assert "RealLLMPlanner(" not in text


def test_t282_verify_script_never_uses_repo_build_dir() -> None:
    text = VERIFY_PATH.read_text(encoding="utf-8")
    assert "tempfile" in text
    assert "copytree" in text or "copy_tree" in text
    assert "smoke_installed_phase5.py" in text
    assert "[app,llm]" in text or "'[app,llm]'" in text or '"[app,llm]"' in text
    assert "assets/*.json" in text or "phase4_3_1_official_summary.json" in text
    lowered = text.lower()
    assert "rmtree(repo" not in lowered
    assert "unlink(repo" not in lowered


def test_t284_ci_runs_secret_free_python_matrix() -> None:
    text = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "3.11" in text
    assert "3.12" in text
    assert ".[app,llm,dev]" in text
    assert "python -m pytest -q -rxXs -p no:cacheprovider" in text
    assert "python -m ruff check --no-cache src tests scripts" in text
    assert "python -m mypy --no-incremental src" in text
    assert "python scripts/verify_phase5_wheel.py" in text
    assert "DEEPSEEK_API_KEY" not in text
    assert "secrets:" not in text
    assert "docker" not in text.lower()
    assert "run_phase3_real_model_eval" not in text
    assert "run_real_model_eval" not in text
    assert "pytest.skip" not in text
    assert "xfail" not in text
    assert "allow_skip" not in text
