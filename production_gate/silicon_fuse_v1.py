"""H6-iron silicon fuse — thin Python glue over C/Rust ha-silicon-fuse.

TABU: Python as production oracle for blow/unblow. No clear API.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BIN_STEM = "ha-silicon-fuse"
SCHEMA = "silicon_fuse_v1"
FUSE_FILENAME = "SE_FUSE.bin"


class SiliconFuseError(ValueError):
    """Raised when fuse missing, blown, or C oracle fails."""


def _exe_name() -> str:
    return _BIN_STEM + (".exe" if sys.platform == "win32" else "")


def find_ha_silicon_fuse_bin() -> Path:
    env = (os.environ.get("HA_SILICON_FUSE_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(
                f"HA_SILICON_FUSE_BIN set but not a file: {p} "
                "(no pure-Python fuse fallback)"
            )
        return p.resolve()
    name = _exe_name()
    for candidate in (
        _REPO / "target" / "release" / name,
        _REPO / "target" / "debug" / name,
    ):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "ha-silicon-fuse binary missing — set HA_SILICON_FUSE_BIN or "
        "cargo build -p ha_silicon_fuse --release "
        "(no pure-Python fuse fallback)"
    )


def _run_cli(args: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    bin_path = find_ha_silicon_fuse_bin()
    return subprocess.run(
        [str(bin_path), *args],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        **hidden_run_kwargs(),
    )


def fuse_path_for_project(project_id: str) -> Path:
    from production_gate.robot_project_desk_v1 import project_dir

    return project_dir(project_id) / FUSE_FILENAME


def ensure_silicon_fuse(project_id: str) -> dict[str, Any]:
    path = fuse_path_for_project(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = _run_cli(["ensure", f"--fuse={path}"])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise SiliconFuseError(f"ha-silicon-fuse ensure failed: {err}")
    return status_silicon_fuse(project_id)


def status_silicon_fuse(project_id: str) -> dict[str, Any]:
    path = fuse_path_for_project(project_id)
    proc = _run_cli(["status", f"--fuse={path}"])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise SiliconFuseError(f"ha-silicon-fuse status failed: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA:
        raise SiliconFuseError("invalid silicon_fuse schema from C oracle")
    return doc


def blow_silicon_fuse(project_id: str, *, lie_score: float) -> dict[str, Any]:
    path = fuse_path_for_project(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = _run_cli(["blow", f"--fuse={path}", f"--lie-score={float(lie_score)}"])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise SiliconFuseError(f"ha-silicon-fuse blow failed: {err}")
    doc = json.loads(proc.stdout)
    if not doc.get("blown"):
        raise SiliconFuseError("blow returned blown=false — C oracle broken")
    return doc


def bind_body_to_silicon_fuse(
    project_id: str,
    body_sha256: str,
    *,
    allow_desk_rebind: bool = True,
) -> dict[str, Any]:
    """Bind body identity hash into C fuse (survives blow; does not clear blown).

    Desk body swap: if fuse already bound to a *different* digest and is not blown,
    start a new fuse epoch (delete SE_FUSE.bin → ensure → bind). This is NOT unblow.
    Blown fuse still refuses — operator must New project.
    """
    digest = str(body_sha256 or "").strip().lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise SiliconFuseError(f"body_sha256 must be 64 hex, got {digest!r}")
    path = fuse_path_for_project(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_silicon_fuse(project_id)
    proc = _run_cli(["bind-body", f"--fuse={path}", f"--body-sha256={digest}"])
    if proc.returncode == 0:
        return json.loads(proc.stdout)
    err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
    if allow_desk_rebind and "HA_FUSE_ERR_BOUND" in err:
        st = status_silicon_fuse(project_id)
        if st.get("blown"):
            raise SiliconFuseError(
                "silicon_fuse_blown — New project required to attach a different body"
            )
        # New desk body → new fuse epoch (bound digest is one-shot by design)
        path.unlink(missing_ok=True)
        ensure_silicon_fuse(project_id)
        proc2 = _run_cli(["bind-body", f"--fuse={path}", f"--body-sha256={digest}"])
        if proc2.returncode != 0:
            err2 = (proc2.stderr or proc2.stdout or "").strip() or f"exit {proc2.returncode}"
            raise SiliconFuseError(f"ha-silicon-fuse bind-body failed after desk rebind: {err2}")
        doc = json.loads(proc2.stdout)
        doc["desk_fuse_rebind"] = True
        doc["honesty"] = {
            "desk_rebind_new_epoch": True,
            "not_unblow": True,
            "not_measured": True,
        }
        return doc
    raise SiliconFuseError(f"ha-silicon-fuse bind-body failed: {err}")


def current_gate_allows(project_id: str) -> bool:
    """C CURRENT_GATE: True iff fuse not blown (current may flow)."""
    path = fuse_path_for_project(project_id)
    ensure_silicon_fuse(project_id)
    proc = _run_cli(["current-gate", f"--fuse={path}"])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-silicon-fuse current-gate failed: {err}")
    line = (proc.stdout or "").strip().splitlines()[-1].strip()
    if line == "1":
        return True
    if line == "0":
        return False
    raise RuntimeError(f"ha-silicon-fuse current-gate bad output: {line!r}")


def load_fuse_into_governance_state(state: dict[str, Any], fuse_path: str | Path) -> dict[str, Any]:
    """Attach C fuse MMIO snapshot into state['governance']['silicon_fuse']."""
    path = Path(fuse_path)
    proc = _run_cli(["ensure", f"--fuse={path}"])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-silicon-fuse ensure failed: {err}")
    proc = _run_cli(["status", f"--fuse={path}"])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-silicon-fuse status failed: {err}")
    doc = json.loads(proc.stdout)
    gov = state.setdefault("governance", {})
    gov["silicon_fuse"] = doc
    gov["silicon_fuse_path"] = str(path)
    return doc


def require_silicon_fuse_intact_on_project(project_id: str) -> dict[str, Any]:
    """Hard gate: fuse must exist and not be blown for artifact to exist."""
    ensure_silicon_fuse(project_id)
    st = status_silicon_fuse(project_id)
    if st.get("blown"):
        raise SiliconFuseError("silicon_fuse_blown")
    return st


def require_silicon_fuse_on_run(run_doc: dict[str, Any]) -> dict[str, Any]:
    fuse = run_doc.get("silicon_fuse")
    if not isinstance(fuse, dict) or fuse.get("schema") != SCHEMA:
        raise SiliconFuseError("missing_silicon_fuse")
    if fuse.get("blown"):
        raise SiliconFuseError("silicon_fuse_blown")
    if fuse.get("irreversible") is not True:
        raise SiliconFuseError("silicon_fuse_not_irreversible")
    if fuse.get("backend") != "c_file_efuse":
        raise SiliconFuseError("silicon_fuse_backend_invalid")
    return fuse
