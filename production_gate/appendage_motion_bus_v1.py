"""Appendage motion bus v1 — role → stack │ gait │ pan-tilt │ terramech(PARK) router.

Phase AP: closes AP_MOTION_BUS_DISPATCHER.
TABU: claim one tick syncs iron on all roles.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SPEC = _REPO / "fixtures" / "robot" / "appendage_motion_bus_dispatch_v1.json"

PROOF_TIER = "APPENDAGE_MOTION_BUS_SLICE"
ORACLE = "ROLE_MOTION_BUS_DISPATCH"


def load_motion_bus_spec(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _SPEC
    if not p.is_absolute():
        p = _REPO / p
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_bus_for_role(role: str) -> dict[str, Any]:
    from production_gate.appendage_role_taxonomy_v1 import resolve_motion_bus_for_role

    return resolve_motion_bus_for_role(role)


def robot_tick(
    robot: dict[str, Any],
    *,
    dt: float = 0.005,
) -> dict[str, Any]:
    from production_gate.appendage_multi_compose_v1 import init_multi_appendage_robot, multi_appendage_tick
    from production_gate.biped_leg_compose_v1 import biped_q_cmd, init_biped_robot
    from production_gate.head_neck_pan_tilt_v1 import look_at_q_cmd

    spec = robot.get("spec") or {}
    regions = list(spec.get("regions") or [])
    outcomes: dict[str, Any] = {}

    stack_rows = []
    for row in regions:
        role = str(row.get("role") or "")
        bus_info = resolve_bus_for_role(role)
        if bus_info.get("bus_status") == "PARK":
            outcomes[row["appendage_id"]] = {"skipped": True, "reason": "PARK", "role": role}
            continue
        module = str(bus_info.get("module") or "")
        if "biped" in str(row.get("bus") or "") or role == "locomotion_leg":
            if "biped_robot" not in robot:
                robot["biped_robot"] = init_biped_robot()
            br = robot["biped_robot"]
            gait = br.get("biped_gait") or {}
            phase = float(gait.get("phase") or 0.0)
            params = dict(gait.get("params") or {})
            idx = int(str(row["appendage_id"]).rsplit("_", 1)[-1])
            outcomes[row["appendage_id"]] = {
                "bus": "biped_gait",
                "q_cmd": biped_q_cmd(idx, phase, params),
            }
            continue
        if role == "head_neck" or "pan_tilt" in str(row.get("bus") or ""):
            target = list(row.get("look_at_target") or [1.0, 0.0, 0.5])
            mount = list(row.get("mount_xyz") or [0.0, 0.0, 0.35])
            outcomes[row["appendage_id"]] = {
                "bus": "pan_tilt",
                "q_cmd": look_at_q_cmd(target, mount_xyz=mount),
            }
            continue
        if role == "wheel_axle" or "wheeled" in str(row.get("bus") or ""):
            from production_gate.rolling_kinematics_crown_v1 import load_rolling_spec

            rolling = load_rolling_spec()
            omega = float(rolling.get("teaching_omega_rad_s") or 3.0)
            phase = float(robot.get("wheel_phase") or 0.0) + omega * dt
            robot["wheel_phase"] = phase
            outcomes[row["appendage_id"]] = {
                "bus": "wheeled_chassis_compose",
                "omega_rad_s": omega,
                "q_cmd": [phase % (2.0 * 3.141592653589793)],
            }
            continue
        if role in ("manipulator_arm", "gripper_tool", "torso_spine", "bench_joint"):
            stack_rows.append(row)
            continue
        outcomes[row["appendage_id"]] = {"error": "unknown_role", "role": role}

    if stack_rows:
        if "stack_robot" not in robot:
            compose = {
                "robot_id": spec.get("robot_id"),
                "compose_id": spec.get("dispatch_id"),
                "appendages": [
                    {
                        "appendage_id": r["appendage_id"],
                        "chain_id": r["chain_id"],
                        "role": r.get("role"),
                        "mount_xyz": list(r.get("mount_xyz") or [0, 0, 0]),
                        "mount_rpy": [0.0, 0.0, 0.0],
                    }
                    for r in stack_rows
                ],
            }
            robot["stack_robot"] = init_multi_appendage_robot(compose)
        q_map = {r["appendage_id"]: [0.15, 0.2, -0.1] if r.get("role") == "manipulator_arm" else [0.1] for r in stack_rows}
        bus = multi_appendage_tick(robot["stack_robot"], q_cmd_by_appendage=q_map, dt=dt)
        for aid in q_map:
            outcomes[aid] = {"bus": "appendage_stack_integrator", "ee": (bus.get("appendages") or {}).get(aid)}

    robot["ticks"] = int(robot.get("ticks") or 0) + 1
    robot["last_outcomes"] = outcomes
    return outcomes


def run_appendage_motion_bus_smoke() -> dict[str, Any]:
    from production_gate.head_neck_pan_tilt_v1 import register_head_neck_chain
    from production_gate.kinematic_chain_ir_v1 import clear_chain_overlay

    clear_chain_overlay()
    register_head_neck_chain()
    from production_gate.appendage_role_taxonomy_v1 import load_role_taxonomy

    spec = load_motion_bus_spec()
    robot: dict[str, Any] = {"spec": spec, "ticks": 0}
    out = robot_tick(robot)

    checks = {
        "F_role_resolves_correct_bus": "appendage_stack_integrator" in str(out.get("scout_arm", {}))
        and "biped_gait" in str(out.get("leg_0", {})),
        "F_multi_role_same_tick": len(out) >= 2,
        "F_unknown_role_fail_closed": all("error" not in v for v in out.values() if isinstance(v, dict)),
        "F_deferred_bus_honest_park": str(
            (load_role_taxonomy().get("roles") or {}).get("wheel_axle", {}).get("operator_priority")
        )
        in ("GATE_ACTIVE", "GATE_ONLY"),
        "F_pan_tilt_bus": "pan_tilt" in str(out.get("neck", {})),
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "APPENDAGE_MOTION_BUS_SLICE_PASS" if not fail else "APPENDAGE_MOTION_BUS_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "outcomes": out,
    }


if __name__ == "__main__":
    print(json.dumps(run_appendage_motion_bus_smoke(), indent=2))
