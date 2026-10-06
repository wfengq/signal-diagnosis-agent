#!/usr/bin/env python3
"""Build sdist/wheel in a Temp copy and smoke-install without using repo build/."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORE_DIR_NAMES = {
    ".git",
    "build",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    ".tox",
    "dist",
}
REQUIRED_WHEEL_ASSETS = (
    "signal_diag/app/static/index.html",
    "signal_diag/app/static/styles.css",
    "signal_diag/app/static/app.js",
    "signal_diag/app/static/intake_flow.js",
    "signal_diag/rules/profiles/s1_distortion_v1.yaml",
    "signal_diag/knowledge/corpus/clipping.md",
    "signal_diag/knowledge/corpus/harmonic_distortion.md",
    "signal_diag/knowledge/corpus/inconclusive.md",
    "signal_diag/evaluation/manifests/s1_distortion_v1.yaml",
    "signal_diag/evaluation/manifests/s1_distortion_v1_1.yaml",
    "signal_diag/evaluation/manifests/s1_distortion_v1_2.yaml",
    "signal_diag/evaluation/assets/phase4_3_1_official_summary.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _ignore(_directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in IGNORE_DIR_NAMES or name.endswith(
            (".pyc", ".pyo", ".pyd", ".egg-info")
        ):
            ignored.add(name)
    return ignored


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
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


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _select_artifact(directory: Path, suffix: str) -> Path:
    matches = sorted(path for path in directory.iterdir() if path.suffix == suffix)
    if len(matches) != 1:
        names = ", ".join(path.name for path in matches) or "<none>"
        raise SystemExit(f"expected one *{suffix} in {directory}, found: {names}")
    return matches[0]


def main() -> int:
    python = sys.executable
    temp_root: Path | None = None
    try:
        temp_root = Path(tempfile.mkdtemp(prefix="signal-diag-phase5-wheel-"))
        copied = temp_root / "src_tree"
        venv_dir = temp_root / "venv"
        smoke_cwd = temp_root / "smoke_cwd"
        shutil.copytree(REPO_ROOT, copied, ignore=_ignore)
        smoke_cwd.mkdir()
        _run(
            [python, "-m", "build", "--sdist", "--wheel", "--no-isolation"],
            cwd=copied,
            env=_child_env(),
        )
        dist_dir = copied / "dist"
        sdist = _select_artifact(dist_dir, ".gz")
        wheel = _select_artifact(dist_dir, ".whl")
        _run([python, "-m", "venv", str(venv_dir)], cwd=temp_root, env=_child_env())
        venv_py = _venv_python(venv_dir)
        extra_req = f"{wheel}[app,llm]"
        _run(
            [
                str(venv_py),
                "-m",
                "pip",
                "install",
                "--retries",
                "10",
                extra_req,
            ],
            cwd=temp_root,
            env=_child_env(),
        )
        smoke_copy = smoke_cwd / "smoke_installed_phase5.py"
        shutil.copy2(REPO_ROOT / "scripts" / "smoke_installed_phase5.py", smoke_copy)
        _run([str(venv_py), str(smoke_copy)], cwd=smoke_cwd, env=_child_env())
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
        missing = [asset for asset in REQUIRED_WHEEL_ASSETS if asset not in names]
        if missing:
            raise SystemExit("wheel missing package data:\n" + "\n".join(missing))
        print(f"sdist {sdist.name} sha256={_sha256(sdist)}")
        print(f"wheel {wheel.name} sha256={_sha256(wheel)}")
        return 0
    finally:
        if temp_root is not None:
            _cleanup_temp_root(temp_root)


if __name__ == "__main__":
    raise SystemExit(main())
