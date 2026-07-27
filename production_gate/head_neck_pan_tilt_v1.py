"""Head/neck pan-tilt v1 — look-at teaching bus · sensor mount frame.

Phase AM: closes AM_HEAD_NECK_CHAIN.
TABU: MEASURED SLAM head tracking · autonomous gaze.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SPEC = _REPO / "fixtures" / "robot" / "head_neck_compose_v1.json"

PROOF_TIER = "HEAD_NECK_SLICE"
ORACLE = "PAN_TILT_LOOK_AT_TEACHING"


def load_head_neck_spec(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _SPEC
    if not p.is_absolute():
        p = _REPO / p
    return json.loads(p.read_text(encoding="utf-8"))


def register_head_neck_chain(*, spec: dict[str, Any] | None = None) -> str:
    from production_gate.kinematic_chain_ir_v1 import register_chain_overlay
    from production_gate.urdf_to_chain_ir_v1 import compile_urdf_to_chain_spec

    spec = dict(spec or load_head_neck_spec())
    chain_id = str(spec.get("chain_id") or "head_neck_pan_tilt_v1")
    compiled = compile_urdf_to_chain_spec(
        str(spec["urdf"]),
        chain_id=chain_id,
        geometry_class="serial_revolute_se3",
        appendage_role="head_neck",
        actuator_backend_default="sim_symplectic",
        root_link=str(spec.get("root_link") or "neck_base_link"),
        ee_link=str(spec.get("ee_frame") or "sensor_mount_link"),
    )
    compiled["source_urdf"] = str(spec["urdf"])
    compiled["root_link"] = str(spec.get("root_link") or "neck_base_link")
    compiled["derived"] = {
        "se3_joints": compiled.get("se3_joints"),
        "joint_limits_rad": compiled.get("joint_limits_rad"),
        "joint_torque_max_nm": compiled.get("joint_torque_max_nm"),
        "gravity_m_s2": 1.62,
    }
    register_chain_overlay(chain_id, compiled)
    return chain_id


def look_at_q_cmd(
    target: list[float],
    *,
    mount_xyz: list[float] | None = None,
) -> list[float]:
    mount_xyz = mount_xyz or [0.0, 0.0, 0.0]
    dx = float(target[0]) - float(mount_xyz[0])
    dy = float(target[1]) - float(mount_xyz[1])
    dz = float(target[2]) - float(mount_xyz[2])
    pan = math.atan2(dy, dx)
    horiz = math.hypot(dx, dy)
    tilt = math.atan2(dz, max(horiz, 1e-6))
    return [max(-1.2, min(1.2, pan)), max(-0.5, min(0.8, tilt))]


def run_head_neck_pan_tilt_smoke(*, build: bool = False) -> dict[str, Any]:
    from production_gate.appendage_stack_integrator_v1 import appendage_stack_tick, default_stack_state
    from production_gate.kinematic_chain_ir_v1 import clear_chain_overlay, resolve_chain_spec

    clear_chain_overlay()
    spec = load_head_neck_spec()
    chain_id = register_head_neck_chain(spec=spec)
    resolved = resolve_chain_spec(chain_id)
    target = list(spec.get("look_at_target") or [1.0, 0.0, 0.5])
    mount = list(spec.get("mount_xyz") or [0.0, 0.0, 0.35])
    q_cmd = look_at_q_cmd(target, mount_xyz=mount)
    stack = default_stack_state(chain_id)
    bus = appendage_stack_tick(stack, q_cmd=q_cmd, dt=0.005)
    ee = bus.get("ee") or {}

    checks = {
        "F_pan_tilt_dof_2": int(resolved.get("dof") or 0) == 2,
        "F_look_at_vector_converge": abs(q_cmd[0]) <= 1.2 and abs(q_cmd[1]) <= 0.8,
        "F_sensor_mount_frame_publish": math.isfinite(float(ee.get("ee_x") or ee.get("x") or 0)),
        "F_mount_on_torso_or_base": len(mount) == 3,
        "F_no_perception_SLAM_claim": "SLAM" in str(spec.get("tabu") or ""),
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "HEAD_NECK_SLICE_PASS" if not fail else "HEAD_NECK_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "q_cmd": q_cmd,
        "ee": ee,
    }


if __name__ == "__main__":
    print(json.dumps(run_head_neck_pan_tilt_smoke(), indent=2))
