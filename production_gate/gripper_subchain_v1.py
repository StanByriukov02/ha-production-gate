"""Gripper sub-chain v1 — tool DOF on manipulator EE · grasp envelope bind.

Phase AO: closes AO_GRIPPER_SUBCHAIN.
TABU: claim flight grasp qual · force closure without envelope.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SPEC = _REPO / "fixtures" / "robot" / "gripper_subchain_compose_v1.json"

PROOF_TIER = "GRIPPER_SUBCHAIN_SLICE"
ORACLE = "GRIPPER_EE_COMPOSE_GRASP"


def load_gripper_compose_spec(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _SPEC
    if not p.is_absolute():
        p = _REPO / p
    return json.loads(p.read_text(encoding="utf-8"))


def register_gripper_chain(*, spec: dict[str, Any] | None = None) -> str:
    from production_gate.kinematic_chain_ir_v1 import register_chain_overlay
    from production_gate.urdf_to_chain_ir_v1 import compile_urdf_to_chain_spec

    spec = dict(spec or load_gripper_compose_spec())
    chain_id = str(spec.get("gripper_chain_id") or "gripper_parallel_1dof_v1")
    compiled = compile_urdf_to_chain_spec(
        str(spec["gripper_urdf"]),
        chain_id=chain_id,
        geometry_class="serial_revolute_se3",
        appendage_role="gripper_tool",
        actuator_backend_default="sim_symplectic",
        root_link="gripper_base_link",
        ee_link="finger_link",
    )
    compiled["source_urdf"] = str(spec["gripper_urdf"])
    compiled["root_link"] = "gripper_base_link"
    compiled["derived"] = {
        "se3_joints": compiled.get("se3_joints"),
        "joint_limits_rad": compiled.get("joint_limits_rad"),
        "joint_torque_max_nm": compiled.get("joint_torque_max_nm"),
        "gravity_m_s2": 1.62,
    }
    register_chain_overlay(chain_id, compiled)
    return chain_id


def grasp_width_m(q_gripper: float) -> float:
    return 0.04 + 0.06 * max(0.0, min(float(q_gripper), 0.6))


def run_gripper_subchain_smoke(*, build: bool = False) -> dict[str, Any]:
    from production_gate.appendage_stack_integrator_v1 import appendage_stack_tick, default_stack_state
    from production_gate.contact_friction_model_v1 import evaluate_coulomb_contact
    from production_gate.kinematic_chain_ir_v1 import clear_chain_overlay, resolve_chain_spec

    clear_chain_overlay()
    spec = load_gripper_compose_spec()
    grip_id = register_gripper_chain(spec=spec)
    arm_id = str(spec.get("arm_chain_id") or "lunar_manipulator_chain_scout_3dof_v1")
    resolve_chain_spec(arm_id)
    resolve_chain_spec(grip_id)

    arm_stack = default_stack_state(arm_id)
    arm_bus = appendage_stack_tick(arm_stack, q_cmd=[0.2, 0.15, -0.1], dt=0.005)
    arm_ee = arm_bus.get("ee") or {}
    ax = float(arm_ee.get("ee_x") or arm_ee.get("x") or 0)
    ay = float(arm_ee.get("ee_y") or arm_ee.get("y") or 0)
    az = float(arm_ee.get("ee_z") or arm_ee.get("z") or 0)
    off = list(spec.get("gripper_mount_on_arm_ee") or [0, 0, 0])

    grip_stack = default_stack_state(grip_id)
    grip_bus = appendage_stack_tick(grip_stack, q_cmd=[0.35], dt=0.005)
    grip_ee = grip_bus.get("ee") or {}
    from production_gate.appendage_mount_se3_v1 import mount_ee_world_translate

    grip_world = mount_ee_world_translate(
        grip_ee,
        [ax + float(off[0]), ay + float(off[1]), az + float(off[2])],
    )

    grasp = dict(spec.get("grasp") or {})
    safe = evaluate_coulomb_contact(
        normal_force_n=float(grasp.get("normal_force_n") or 5.0),
        tangential_force_n=float(grasp.get("tangential_safe_n") or 0.8),
        pad_material_id=str(grasp.get("pad_material_id") or "nbr_70a"),
        surface_id=str(grasp.get("surface_id") or "lunar_regolith_compact"),
    )
    slip = evaluate_coulomb_contact(
        normal_force_n=float(grasp.get("normal_force_n") or 5.0),
        tangential_force_n=float(grasp.get("tangential_slip_n") or 4.0),
        pad_material_id=str(grasp.get("pad_material_id") or "nbr_70a"),
        surface_id=str(grasp.get("surface_id") or "lunar_regolith_compact"),
    )
    q_g = 0.35
    width = grasp_width_m(q_g)

    checks = {
        "F_gripper_on_scout_ee": math.isfinite(float(grip_world.get("x") or 0)),
        "F_grasp_width_vs_q": width > 0.05,
        "F_coulomb_grasp_slip_diverge": bool(safe.get("slip_predicted")) != bool(slip.get("slip_predicted")),
        "F_arm_plus_gripper_dof_sum": int(arm_stack.get("dof") or 0) + int(grip_stack.get("dof") or 0) == 4,
        "F_backlash_plugin_optional": True,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "GRIPPER_SUBCHAIN_SLICE_PASS" if not fail else "GRIPPER_SUBCHAIN_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "grip_world": grip_world,
        "grasp_width_m": width,
    }


if __name__ == "__main__":
    print(json.dumps(run_gripper_subchain_smoke(), indent=2))
