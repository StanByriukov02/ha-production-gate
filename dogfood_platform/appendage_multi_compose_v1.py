"""Multi-appendage robot compose v1 — scout arm + LC-2 hip on one robot bus.

Mounts each chain stack · ticks independently · publishes world-frame EE poses.
TABU: claim universal robot OS · claim RT multi-appendage field servo.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_COMPOSE = _REPO / "fixtures" / "robot" / "appendage_robot_compose_v1.json"

PROOF_TIER = "APPENDAGE_MULTI_COMPOSE_SLICE"
ORACLE = "MULTI_APPENDAGE_ROBOT_BUS"


def load_robot_compose_spec(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _DEFAULT_COMPOSE
    if not p.is_absolute():
        p = _REPO / p
    return json.loads(p.read_text(encoding="utf-8"))


def _mount_ee_world(ee_local: dict[str, Any], mount: dict[str, Any]) -> dict[str, float]:
    from dogfood_platform.appendage_mount_se3_v1 import mount_ee_world

    return mount_ee_world(ee_local, mount, use_se3=True)


def init_multi_appendage_robot(spec: dict[str, Any]) -> dict[str, Any]:
    from dogfood_platform.appendage_stack_integrator_v1 import default_stack_state
    from dogfood_platform.kinematic_chain_ir_v1 import resolve_chain_spec

    appendages: dict[str, Any] = {}
    total_dof = 0
    backends: list[str] = []

    for row in spec.get("appendages") or []:
        aid = str(row["appendage_id"])
        chain_id = str(row["chain_id"])
        resolve_chain_spec(chain_id)
        stack = default_stack_state(chain_id)
        appendages[aid] = {
            "appendage_id": aid,
            "chain_id": chain_id,
            "role": row.get("role"),
            "mount_xyz": list(row.get("mount_xyz") or [0.0, 0.0, 0.0]),
            "mount_rpy": list(row.get("mount_rpy") or [0.0, 0.0, 0.0]),
            "stack": stack,
        }
        total_dof += int(stack.get("dof") or 0)

    for aid, row in appendages.items():
        chain_id = row["chain_id"]
        from dogfood_platform.actuator_plugin_bus_v1 import resolve_actuator_plugin

        backends.append(resolve_actuator_plugin(chain_id).backend_id)

    return {
        "robot_id": spec.get("robot_id"),
        "compose_id": spec.get("compose_id"),
        "base_frame": spec.get("base_frame") or "robot_base_link",
        "appendages": appendages,
        "total_dof": total_dof,
        "backends": backends,
        "ticks": 0,
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
    }


def multi_appendage_tick(
    robot: dict[str, Any],
    *,
    q_cmd_by_appendage: dict[str, list[float]] | None = None,
    dt: float = 0.005,
    torques_by_appendage: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    from dogfood_platform.appendage_stack_integrator_v1 import appendage_stack_tick

    q_cmd_by_appendage = q_cmd_by_appendage or {}
    torques_by_appendage = torques_by_appendage or {}
    buses: dict[str, Any] = {}

    for aid, row in (robot.get("appendages") or {}).items():
        stack = row["stack"]
        bus = appendage_stack_tick(
            stack,
            q_cmd=q_cmd_by_appendage.get(aid),
            dt=dt,
            torques=torques_by_appendage.get(aid),
        )
        ee_world = _mount_ee_world(bus.get("ee") or {}, row)
        buses[aid] = {
            **bus,
            "appendage_id": aid,
            "role": row.get("role"),
            "mount_xyz": row.get("mount_xyz"),
            "mount_rpy": row.get("mount_rpy"),
            "ee_world": ee_world,
            "mount_mode": "se3_motor",
        }

    robot["ticks"] = int(robot.get("ticks") or 0) + 1
    robot["bus"] = {
        "robot_id": robot.get("robot_id"),
        "ticks": robot["ticks"],
        "appendages": buses,
        "total_dof": robot.get("total_dof"),
    }
    return robot["bus"]


def run_multi_appendage_smoke(
    *,
    compose_path: Path | str | None = None,
) -> dict[str, Any]:
    spec = load_robot_compose_spec(compose_path)
    robot = init_multi_appendage_robot(spec)
    bus = multi_appendage_tick(
        robot,
        q_cmd_by_appendage={
            "scout_arm": [0.25, 0.15, -0.1],
            "lc2_hip_bench": [0.35],
        },
        torques_by_appendage={
            "scout_arm": [0.2, 0.1, 0.05],
            "lc2_hip_bench": [0.15],
        },
        dt=0.005,
    )

    scout = bus["appendages"]["scout_arm"]
    lc2 = bus["appendages"]["lc2_hip_bench"]
    mount_z = float((robot["appendages"]["lc2_hip_bench"].get("mount_xyz") or [0, 0, 0.18])[2])

    checks = {
        "F_two_appendages": len(bus.get("appendages") or {}) == 2,
        "F_total_dof_four": int(robot.get("total_dof") or 0) == 4,
        "F_dual_backend": set(robot.get("backends") or []) == {"sim_symplectic", "lc2_iron_teaching"},
        "F_scout_ee_world_mount": float(scout["ee_world"]["z"] or 0) >= 0.45,
        "F_lc2_ee_world_mount": abs(float(lc2["ee_world"]["z"] or 0) - mount_z) < 0.05
        or float(lc2["ee_world"]["x"] or 0) > 0,
        "F_scout_finite": math.isfinite(float(scout["ee_world"]["x"] or 0)),
        "F_ticks_one": int(robot.get("ticks") or 0) == 1,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "APPENDAGE_MULTI_COMPOSE_SLICE_PASS" if not fail else "APPENDAGE_MULTI_COMPOSE_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "robot_id": robot.get("robot_id"),
        "bus": bus,
    }
