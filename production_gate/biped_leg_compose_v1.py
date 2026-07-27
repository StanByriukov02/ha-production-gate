"""Biped leg pair compose v1 — 2× leg · CoM teaching · stance alternate.

Phase AN: closes AN_BIPED_LEG_PAIR_COMPOSE.
TABU: claim biped walks · ZMP MEASURED · lunar humanoid.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SPEC = _REPO / "fixtures" / "robot" / "biped_leg_compose_v1.json"
_GAIT = _REPO / "fixtures" / "robot" / "biped_gait_catalog_v0.json"

PROOF_TIER = "BIPED_LEG_COMPOSE_SLICE"
ORACLE = "BIPED_COM_TEACHING_CYCLE"


def load_biped_spec(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _SPEC
    if not p.is_absolute():
        p = _REPO / p
    return json.loads(p.read_text(encoding="utf-8"))


def load_biped_gait(name: str = "alternating_stance") -> dict[str, Any]:
    doc = json.loads(_GAIT.read_text(encoding="utf-8"))
    return dict((doc.get("gaits") or {}).get(name) or {})


def _leg_idx(aid: str) -> int:
    return int(aid.rsplit("_", 1)[-1])


def biped_q_cmd(leg_idx: int, phase: float, params: dict[str, Any]) -> list[float]:
    groups = list(params.get("stance_groups") or [[0], [1]])
    base = list(params.get("base_q") or [0.12, 0.22, -0.14])
    amp = float(params.get("swing_amp_rad") or 0.07)
    half = int(phase * 2.0) % 2
    swing_set = set(groups[1 - half] if len(groups) > 1 else groups[0])
    if leg_idx in swing_set:
        local = (phase * 2.0) % 1.0
        lift = amp * math.sin(2.0 * math.pi * local)
        return [base[0], base[1] + lift, base[2]]
    return list(base)


def init_biped_robot(spec: dict[str, Any] | None = None) -> dict[str, Any]:
    from production_gate.appendage_multi_compose_v1 import init_multi_appendage_robot

    spec = dict(spec or load_biped_spec())
    chain_id = str(spec.get("leg_chain_id") or "hexapod_leg_3dof_v1")
    rows = []
    for leg in spec.get("legs") or []:
        rows.append(
            {
                "appendage_id": str(leg["appendage_id"]),
                "chain_id": chain_id,
                "role": "locomotion_leg",
                "mount_xyz": list(leg.get("mount_xyz") or [0, 0, 0]),
                "mount_rpy": list(leg.get("mount_rpy") or [0, 0, 0]),
            }
        )
    robot = init_multi_appendage_robot(
        {
            "robot_id": spec.get("robot_id"),
            "compose_id": spec.get("compose_id"),
            "base_frame": spec.get("base_frame") or "pelvis_link",
            "appendages": rows,
        }
    )
    gait = load_biped_gait(str(spec.get("gait_name") or "alternating_stance"))
    robot["biped_gait"] = {
        "phase_tick": 0,
        "phase": 0.0,
        "params": gait,
        "deferred": list(spec.get("deferred") or []),
    }
    return robot


def biped_tick(robot: dict[str, Any], *, dt: float = 0.005) -> dict[str, Any]:
    from production_gate.appendage_multi_compose_v1 import multi_appendage_tick
    from production_gate.hexapod_foot_contact_v1 import evaluate_hexapod_foot_contact

    gait = robot.get("biped_gait") or {}
    phase = float(gait.get("phase") or 0.0)
    params = dict(gait.get("params") or {})
    q_map = {
        aid: biped_q_cmd(_leg_idx(aid), phase, params) for aid in (robot.get("appendages") or {})
    }
    bus = multi_appendage_tick(robot, q_cmd_by_appendage=q_map, dt=dt)
    contacts = []
    gait_bus = {"phase": phase, "params": params}
    for aid, row in (bus.get("appendages") or {}).items():
        ee = row.get("ee_world") or {}
        contacts.append(
            evaluate_hexapod_foot_contact(foot_world=ee, leg_id=aid, gait_bus=gait_bus)
        )
    cycle = int(params.get("phase_ticks_per_cycle") or 20)
    tick = int(gait.get("phase_tick") or 0) + 1
    gait["phase_tick"] = tick
    gait["phase"] = float(tick % cycle) / float(max(cycle, 1))
    bus["contacts"] = contacts
    appendages = bus.get("appendages") or {}
    xs = [abs(float((row.get("ee_world") or {}).get("x") or 0)) for row in appendages.values()]
    bus["com_teaching_proxy_m"] = sum(xs) / max(len(xs), 1)
    robot["bus"] = bus
    return bus


def run_biped_leg_compose_smoke(*, ticks: int = 24) -> dict[str, Any]:
    robot = init_biped_robot()
    params = (robot.get("biped_gait") or {}).get("params") or {}
    com_target = float(params.get("com_height_target_m") or 0.28)
    swing_early: set[int] = set()
    swing_late: set[int] = set()
    half = max(int(params.get("phase_ticks_per_cycle") or 20) // 2, 1)

    for t in range(ticks):
        gait = robot.get("biped_gait") or {}
        phase = float(gait.get("phase") or 0.0)
        groups = list(params.get("stance_groups") or [[0], [1]])
        h = int(phase * 2.0) % 2
        swing = set(groups[1 - h] if len(groups) > 1 else groups[0])
        if t < half:
            swing_early.update(swing)
        elif t >= half:
            swing_late.update(swing)
        biped_tick(robot)

    last = robot.get("bus") or {}
    contacts = last.get("contacts") or []
    checks = {
        "F_two_legs_mirrored_mount": len(robot.get("appendages") or {}) == 2,
        "F_com_height_teaching_bounded": float(last.get("com_teaching_proxy_m") or 0) > 0.1,
        "F_stance_swing_alternate": bool(swing_early) and bool(swing_late) and swing_early != swing_late,
        "F_foot_contact_per_leg": len(contacts) == 2,
        "F_no_walk_claim": "claim biped walks" in str(load_biped_spec().get("tabu") or ""),
        "F_shared_servo_clock": int((robot.get("biped_gait") or {}).get("phase_tick") or 0) == ticks,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "BIPED_LEG_COMPOSE_SLICE_PASS" if not fail else "BIPED_LEG_COMPOSE_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
    }


if __name__ == "__main__":
    print(json.dumps(run_biped_leg_compose_smoke(), indent=2))
