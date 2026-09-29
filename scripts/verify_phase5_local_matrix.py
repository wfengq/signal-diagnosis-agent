#!/usr/bin/env python3
"""Run Phase 5 dual-version clean-environment verification (OQ-011 / D031)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE4_3_1_MERGED_BASELINE = "36ae7c9"
DIFF_CHECK_COMMAND = "git diff --check"
PHASE5_COMMANDS = (
    "python -m pytest -q -rxXs -p no:cacheprovider",
    "python -m ruff check --no-cache src tests scripts",
    "python -m mypy --no-incremental src",
    "python scripts/verify_phase5_wheel.py",
)


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("DEEPSEEK_API_KEY", None)
    return env


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _rmtree(path: Path) -> None:
    last_error: Exception | None = None
    for _ in range(20):
        try:
            shutil.rmtree(path)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.25)
    if last_error is not None:
        raise last_error


def _cleanup_temp_root(temp_root: Path) -> None:
    if not temp_root.exists():
        return
    root = temp_root.resolve()
    for child in list(root.iterdir()):
        resolved = child.resolve()
        if not _is_under(resolved, root) or resolved == root:
            continue
        if resolved.is_symlink() or resolved.is_file():
            resolved.unlink()
        elif resolved.is_dir():
            _rmtree(resolved)
    try:
        root.rmdir()
    except OSError:
        return


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(command, cwd=cwd, env=env, check=False, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _require_minor(python: Path, expected: tuple[int, int]) -> None:
    probe = subprocess.run(
        [
            str(python),
            "-c",
            "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if probe.returncode != 0:
        raise SystemExit(f"failed to probe {python}: {probe.stderr}")
    found = probe.stdout.strip()
    wanted = f"{expected[0]}.{expected[1]}"
    if found != wanted:
        raise SystemExit(f"{python} is Python {found}, expected {wanted}")


def _command_argv(python: Path, command: str) -> list[str]:
    parts = command.split()
    if parts[0] != "python":
        raise SystemExit(f"refusing unexpected command: {command}")
    return [str(python), *parts[1:]]


def _verify_one(
    *,
    label: str,
    interpreter: Path,
    expected: tuple[int, int],
    venv_dir: Path,
) -> None:
    _require_minor(interpreter, expected)
    env = _child_env()
    _run([str(interpreter), "-m", "venv", str(venv_dir)], cwd=REPO_ROOT, env=env)
    venv_py = _venv_python(venv_dir)
    probe = subprocess.run(
        [
            str(venv_py),
            "-c",
            "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if probe.returncode != 0 or probe.stdout.strip() != f"{expected[0]}.{expected[1]}":
        raise SystemExit(
            f"venv {venv_dir} is {probe.stdout.strip() or probe.stderr}, "
            f"expected {expected[0]}.{expected[1]}"
        )
    extra = ".[app,llm,dev]"
    _run(
        [
            str(venv_py),
            "-m",
            "pip",
            "install",
            "--retries",
            "10",
            extra,
        ],
        cwd=REPO_ROOT,
        env=env,
    )
    for command in PHASE5_COMMANDS:
        print(f"[{label}] {command}", flush=True)
        _run(_command_argv(venv_py, command), cwd=REPO_ROOT, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-3.11", dest="python_311", type=Path, required=True)
    parser.add_argument("--python-3.12", dest="python_312", type=Path, required=True)
    args = parser.parse_args(argv)
    python_311 = args.python_311.resolve()
    python_312 = args.python_312.resolve()
    if not python_311.is_file() or not python_312.is_file():
        raise SystemExit("both --python-3.11 and --python-3.12 must be interpreter files")
    temp_root: Path | None = None
    try:
        temp_root = Path(tempfile.mkdtemp(prefix="signal-diag-phase5-matrix-"))
        _verify_one(
            label="3.11",
            interpreter=python_311,
            expected=(3, 11),
            venv_dir=temp_root / "venv-311",
        )
        _verify_one(
            label="3.12",
            interpreter=python_312,
            expected=(3, 12),
            venv_dir=temp_root / "venv-312",
        )
        _run(
            [*DIFF_CHECK_COMMAND.split(), f"{PHASE4_3_1_MERGED_BASELINE}..HEAD"],
            cwd=REPO_ROOT,
            env=_child_env(),
        )
        print("local 3.11/3.12 clean-environment verification passed", flush=True)
        return 0
    finally:
        if temp_root is not None:
            _cleanup_temp_root(temp_root)


if __name__ == "__main__":
    raise SystemExit(main())
