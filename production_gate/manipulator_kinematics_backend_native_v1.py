"""Native manipulator kinematics backend — Rust subprocess glue only."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BIN_NAME = "manipulator_kinematics_step"


def _release_bin() -> Path:
    exe = _BIN_NAME + (".exe" if sys.platform == "win32" else "")
    return _REPO / "target" / "release" / exe


def ensure_manipulator_kinematics_native_built(*, release: bool = True) -> Path:
    bin_path = _release_bin() if release else _REPO / "target" / "debug" / (
        _BIN_NAME + (".exe" if sys.platform == "win32" else "")
    )
    if bin_path.is_file():
        return bin_path
    cmd = ["cargo", "build", "-p", "universe_kinematic", "--bin", _BIN_NAME]
    if release:
        cmd.append("--release")
    subprocess.run(cmd, cwd=_REPO, check=True)
    if not bin_path.is_file():
        raise FileNotFoundError(f"manipulator kinematics binary missing after build: {bin_path}")
    return bin_path


def run_manipulator_kinematics_native(payload: dict[str, Any], *, build: bool = True) -> dict[str, Any]:
    bin_path = ensure_manipulator_kinematics_native_built(release=True) if build else _release_bin()
    proc = subprocess.run(
        [str(bin_path)],
        input=json.dumps(payload),
        cwd=_REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)
