"""H6 Physics gate / apoptosis — thin Python orchestration over Rust ha-physics-gate.

TABU: Python as production oracle for current_allowed / apoptosis bit.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BIN_STEM = "ha-physics-gate"
SCHEMA = "physics_gate_v1"
APOPTOSIS_FILENAME = "APOPTOSIS_v1.json"


class PhysicsGateError(ValueError):
    """Raised when physics gate is missing, incoherent, or apoptosis latched."""


def _exe_name() -> str:
    return _BIN_STEM + (".exe" if sys.platform == "win32" else "")


def find_ha_physics_gate_bin() -> Path:
    env = (os.environ.get("HA_PHYSICS_GATE_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(
                f"HA_PHYSICS_GATE_BIN set but not a file: {p} "
                "(no pure-Python gate fallback)"
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
        "ha-physics-gate binary missing — set HA_PHYSICS_GATE_BIN or "
        "cargo build -p ha_physics_gate --release "
        "(no pure-Python gate fallback)"
    )


def _run_cli(args: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    bin_path = find_ha_physics_gate_bin()
    return subprocess.run(
        [str(bin_path), *args],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        **hidden_run_kwargs(),
    )


def validate_physics_gate(doc: dict[str, Any] | str | Path) -> None:
    import tempfile

    if isinstance(doc, Path):
        json_path = doc
        if not json_path.is_file():
            raise FileNotFoundError(f"physics gate json not found: {json_path}")
        proc = _run_cli(["validate", "--json", str(json_path)])
    else:
        payload = doc if isinstance(doc, str) else json.dumps(doc, indent=2, ensure_ascii=False)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(payload if payload.endswith("\n") else payload + "\n")
            json_path = Path(tmp.name)
        try:
            proc = _run_cli(["validate", "--json", str(json_path)])
        finally:
            json_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise PhysicsGateError(f"physics_gate validate FAIL: {err}")


def emit_physics_gate(
    *,
    gate_id: str,
    digit_advise: str,
    traverse_feasible: bool,
    sinkage_risk: bool,
    budget_j: float,
    residual_j: float,
    prior_lie: float = 0.0,
    prior_apoptosis: bool = False,
    lie_threshold: float = 3.0,
    failure_modes_clear: bool = True,
) -> dict[str, Any]:
    proc = _run_cli(
        [
            "emit",
            f"--gate-id={gate_id}",
            f"--digit-advise={str(digit_advise).upper()}",
            f"--traverse-feasible={'true' if traverse_feasible else 'false'}",
            f"--sinkage-risk={'true' if sinkage_risk else 'false'}",
            f"--failure-modes-clear={'true' if failure_modes_clear else 'false'}",
            f"--budget-j={float(budget_j)}",
            f"--residual-j={float(residual_j)}",
            f"--prior-lie={float(prior_lie)}",
            f"--prior-apoptosis={'true' if prior_apoptosis else 'false'}",
            f"--lie-threshold={float(lie_threshold)}",
        ]
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-physics-gate emit failed: {err}")
    gate = json.loads(proc.stdout)
    validate_physics_gate(gate)
    return gate


def _digit_advise_from_planner(actuation_truth: dict[str, Any], dual_block: dict[str, Any]) -> str:
    """Governance digit = planner leg (not blind stub)."""
    planner = actuation_truth.get("planner") if isinstance(actuation_truth, dict) else {}
    cmd = str((planner or {}).get("command") or "").strip().lower()
    if not cmd:
        reg = (dual_block.get("regolith") or {}).get("proposal") or {}
        cmd = str(reg.get("command") or "").strip().lower()
    if cmd in ("traverse", "advance", "go"):
        return "ALLOW"
    return "DENY"


def apoptosis_path_for_project(project_id: str) -> Path:
    from production_gate.robot_project_desk_v1 import project_dir

    return project_dir(project_id) / APOPTOSIS_FILENAME


def load_apoptosis_state(project_id: str) -> dict[str, Any]:
    path = apoptosis_path_for_project(project_id)
    if not path.is_file():
        return {"lie_score": 0.0, "bit": False, "schema": "apoptosis_state_v1"}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {
        "lie_score": float(doc.get("lie_score") or 0.0),
        "bit": bool(doc.get("bit")),
        "schema": "apoptosis_state_v1",
        "updated_utc": doc.get("updated_utc"),
    }


def persist_apoptosis_state(project_id: str, gate: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime, timezone

    apo = gate.get("apoptosis") if isinstance(gate.get("apoptosis"), dict) else {}
    state = {
        "schema": "apoptosis_state_v1",
        "lie_score": float(gate.get("lie_score") or 0.0),
        "bit": bool(apo.get("bit")),
        "threshold": apo.get("threshold"),
        "irreversible": True,
        "gate_id": gate.get("gate_id"),
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "honesty": {
            "sim_slice": True,
            "silicon_fuse_backend": "c_file_efuse",
            "not_otp_silicon": True,
        },
    }
    path = apoptosis_path_for_project(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return state


def sync_silicon_fuse_after_gate(project_id: str, gate: dict[str, Any]) -> dict[str, Any]:
    """C eFUSE follows soft apoptosis: blow when bit latches; status always from C."""
    from production_gate.silicon_fuse_v1 import (
        blow_silicon_fuse,
        ensure_silicon_fuse,
        status_silicon_fuse,
    )

    ensure_silicon_fuse(project_id)
    apo = gate.get("apoptosis") if isinstance(gate.get("apoptosis"), dict) else {}
    if apo.get("bit"):
        return blow_silicon_fuse(project_id, lie_score=float(gate.get("lie_score") or 0.0))
    return status_silicon_fuse(project_id)


def build_physics_gate_for_run(
    project_id: str,
    *,
    condition: str,
    dual_block: dict[str, Any],
    actuation_truth: dict[str, Any],
    energy_claim: dict[str, Any],
) -> dict[str, Any]:
    """Build H6 gate via Rust; prior latch includes C fuse blown state."""
    from production_gate.failure_mode_gate_v1 import apply_failure_modes_to_physics
    from production_gate.silicon_fuse_v1 import ensure_silicon_fuse, status_silicon_fuse

    physics = dict(dual_block.get("physics") or {})
    physics = apply_failure_modes_to_physics(physics)
    dual_block["physics"] = physics
    traverse_feasible = bool(physics.get("traverse_feasible"))
    sinkage_risk = bool(physics.get("sinkage_risk"))
    fm = physics.get("failure_modes") if isinstance(physics.get("failure_modes"), dict) else {}
    failure_modes_clear = bool(fm.get("failure_modes_clear", True))
    digit = _digit_advise_from_planner(actuation_truth, dual_block)
    budget_j = float(energy_claim.get("budget_joules") or 1.0)
    residual_j = float(energy_claim.get("residual_joules") or 0.0)
    prior = load_apoptosis_state(project_id)
    ensure_silicon_fuse(project_id)
    fuse_prior = status_silicon_fuse(project_id)
    prior_apoptosis = bool(prior.get("bit")) or bool(fuse_prior.get("blown"))
    gate = emit_physics_gate(
        gate_id=f"{project_id}:{condition}",
        digit_advise=digit,
        traverse_feasible=traverse_feasible,
        sinkage_risk=sinkage_risk,
        budget_j=budget_j,
        residual_j=residual_j,
        prior_lie=float(prior.get("lie_score") or 0.0),
        prior_apoptosis=prior_apoptosis,
        failure_modes_clear=failure_modes_clear,
    )
    # Surface failure modes on gate receipt
    gate["failure_modes"] = fm
    persist_apoptosis_state(project_id, gate)
    return gate


def require_physics_gate_on_run(run_doc: dict[str, Any]) -> dict[str, Any]:
    gate = run_doc.get("physics_gate")
    if not isinstance(gate, dict) or gate.get("schema") != SCHEMA:
        raise PhysicsGateError("missing_physics_gate")
    validate_physics_gate(gate)
    apo = gate.get("apoptosis") if isinstance(gate.get("apoptosis"), dict) else {}
    if apo.get("bit"):
        raise PhysicsGateError("apoptosis_latched")
    if not gate.get("governance_coherent"):
        raise PhysicsGateError("governance_incoherent")
    return gate
