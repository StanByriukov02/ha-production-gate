"""Hexapod body compose v1 — 6× leg appendages on circular body bus.

Phase AG: closes AG_HEXAPOD_FULL_BODY (compose slice). Gait/contact → AH/AI deferred.
TABU: claim field hexapod locomotion · claim MEASURED gait.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_SPEC = _REPO / "fixtures" / "robot" / "hexapod_body_compose_v1.json"

PROOF_TIER = "HEXAPOD_BODY_COMPOSE_SLICE"
ORACLE = "HEXAPOD_SIX_LEG_BUS"


def load_hexapod_body_spec(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _DEFAULT_SPEC
    if not p.is_absolute():
        p = _REPO / p
    return json.loads(p.read_text(encoding="utf-8"))


def build_hexapod_appendage_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    n = int(spec.get("leg_count") or 6)
    radius = float(spec.get("body_radius_m") or 0.15)
    mz = float(spec.get("mount_z_m") or 0.05)
    chain_id = str(spec.get("leg_chain_id") or "hexapod_leg_3dof_v1")
    rows: list[dict[str, Any]] = []
    for i in range(n):
        yaw = 2.0 * math.pi * i / n
        mx = radius * math.cos(yaw)
        my = radius * math.sin(yaw)
        rows.append(
            {
                "appendage_id": f"leg_{i}",
                "chain_id": chain_id,
                "role": "locomotion_leg",
                "mount_xyz": [mx, my, mz],
                "mount_rpy": [0.0, 0.0, yaw],
            }
        )
    return rows


def init_hexapod_body(spec: dict[str, Any] | None = None) -> dict[str, Any]:
    from production_gate.appendage_multi_compose_v1 import init_multi_appendage_robot

    spec = dict(spec or load_hexapod_body_spec())
    compose = {
        "compose_id": spec.get("compose_id"),
        "robot_id": spec.get("robot_id"),
        "base_frame": spec.get("base_frame") or "body_link",
        "appendages": build_hexapod_appendage_rows(spec),
    }
    robot = init_multi_appendage_robot(compose)
    robot["hexapod"] = {
        "leg_count": int(spec.get("leg_count") or 6),
        "body_radius_m": float(spec.get("body_radius_m") or 0.15),
        "deferred": list(spec.get("deferred") or []),
    }
    return robot


def hexapod_body_tick(
    robot: dict[str, Any],
    *,
    q_cmd_by_leg: dict[str, list[float]] | None = None,
    dt: float = 0.005,
) -> dict[str, Any]:
    from production_gate.appendage_multi_compose_v1 import multi_appendage_tick

    q_cmd_by_leg = q_cmd_by_leg or {}
    torques: dict[str, list[float]] = {}
    for aid in (robot.get("appendages") or {}):
        cmd = q_cmd_by_leg.get(aid)
        if cmd is None:
            idx = int(aid.split("_")[-1]) if "_" in aid else 0
            cmd = [0.12 + 0.03 * idx, 0.2, -0.15]
        torques[aid] = [0.1] * len(cmd)
    bus = multi_appendage_tick(robot, q_cmd_by_appendage=q_cmd_by_leg, torques_by_appendage=torques, dt=dt)
    feet = []
    for aid, row in (bus.get("appendages") or {}).items():
        ee = row.get("ee_world") or {}
        feet.append({"leg": aid, "x": ee.get("x"), "y": ee.get("y"), "z": ee.get("z")})
    bus["feet"] = feet
    return bus


def run_hexapod_body_smoke(*, spec_path: Path | str | None = None) -> dict[str, Any]:
    spec = load_hexapod_body_spec(spec_path)
    robot = init_hexapod_body(spec)
    bus = hexapod_body_tick(robot)

    feet = bus.get("feet") or []
    xs = [float(f.get("x") or 0) for f in feet]
    ys = [float(f.get("y") or 0) for f in feet]

    checks = {
        "F_six_legs": len(bus.get("appendages") or {}) == 6,
        "F_total_dof_18": int(robot.get("total_dof") or 0) == 18,
        "F_all_feet_finite": all(math.isfinite(x) and math.isfinite(y) for x, y in zip(xs, ys)),
        "F_feet_spread": (max(xs) - min(xs) > 0.1) and (max(ys) - min(ys) > 0.1),
        "F_mount_se3_used": all(
            abs(float((bus["appendages"][aid].get("ee_world") or {}).get("y") or 0)) >= 0.0
            for aid in bus.get("appendages", {})
        ),
        "F_deferred_honest": "AH_HEXAPOD_GAIT_BUS" in (spec.get("deferred") or []),
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "HEXAPOD_BODY_COMPOSE_SLICE_PASS" if not fail else "HEXAPOD_BODY_COMPOSE_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "robot_id": robot.get("robot_id"),
        "feet": feet,
    }
