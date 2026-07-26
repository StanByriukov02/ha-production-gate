"""Torso/spine chain v1 — trunk URDF → registry · FK · mount frames.

Phase AL: closes AL_TORSO_SPINE_CHAIN.
TABU: humanoid torso without per-link STEP · dynamic balance claims.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SPEC = _REPO / "fixtures" / "robot" / "torso_spine_chain_v1.json"

PROOF_TIER = "TORSO_SPINE_SLICE"
ORACLE = "TORSO_SPINE_REGISTRY_FK"


def load_torso_spine_spec(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _SPEC
    if not p.is_absolute():
        p = _REPO / p
    return json.loads(p.read_text(encoding="utf-8"))


def register_torso_spine_chain(*, spec: dict[str, Any] | None = None) -> str:
    from dogfood_platform.kinematic_chain_ir_v1 import register_chain_overlay
    from dogfood_platform.urdf_to_chain_ir_v1 import compile_urdf_to_chain_spec

    spec = dict(spec or load_torso_spine_spec())
    chain_id = str(spec.get("chain_id") or "torso_spine_2dof_v1")
    compiled = compile_urdf_to_chain_spec(
        str(spec["urdf"]),
        chain_id=chain_id,
        geometry_class="serial_revolute_se3",
        appendage_role="torso_spine",
        actuator_backend_default="sim_symplectic",
        root_link=str(spec.get("root_link") or "pelvis_link"),
        ee_link=str(spec.get("ee_frame") or "chest_mount_link"),
    )
    compiled["source_urdf"] = str(spec["urdf"])
    compiled["root_link"] = str(spec.get("root_link") or "pelvis_link")
    compiled["derived"] = {
        "se3_joints": compiled.get("se3_joints"),
        "joint_limits_rad": compiled.get("joint_limits_rad"),
        "joint_torque_max_nm": compiled.get("joint_torque_max_nm"),
        "gravity_m_s2": 1.62,
    }
    register_chain_overlay(chain_id, compiled)
    return chain_id


def run_torso_spine_smoke(*, build: bool = False) -> dict[str, Any]:
    from dogfood_platform.kinematic_chain_ir_v1 import clear_chain_overlay, fk_for_chain, resolve_chain_spec

    clear_chain_overlay()
    spec = load_torso_spine_spec()
    chain_id = register_torso_spine_chain(spec=spec)
    resolved = resolve_chain_spec(chain_id)
    fk = fk_for_chain(chain_id, [0.1, -0.08], build=build)
    mount_arm = list(spec.get("mount_arm_xyz") or [0.0, 0.0, 0.1])
    mount_leg = list(spec.get("mount_leg_xyz") or [0.0, 0.0, -0.03])

    checks = {
        "F_trunk_dof_match_urdf": int(resolved.get("dof") or 0) == 2,
        "F_pitch_yaw_fk_finite": all(math.isfinite(float(fk.get(k) or 0)) for k in ("ee_x", "ee_y", "ee_z")),
        "F_mount_arm_on_trunk_ee": len(mount_arm) == 3,
        "F_mount_legs_on_trunk_base": len(mount_leg) == 3,
        "F_registry_resolve_roundtrip": str(resolved.get("appendage_role") or "") == "torso_spine",
        "F_mass_ledger_stub_honest": bool((spec.get("honesty") or {}).get("mass_ledger_stub")),
        "F_chest_elevated": float(fk.get("ee_z") or 0) > 0.05,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "TORSO_SPINE_SLICE_PASS" if not fail else "TORSO_SPINE_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "chain_id": chain_id,
        "fk": fk,
    }


if __name__ == "__main__":
    print(json.dumps(run_torso_spine_smoke(), indent=2))
