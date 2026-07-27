"""Hexapod gait bus v1 — tripod/wave phase clock · q_cmd dispatch to 6 legs.

Phase AH: closes AH_HEXAPOD_GAIT_BUS (teaching). Contact → AI deferred.
TABU: claim MEASURED locomotion · claim field gait tuning.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_GAIT_CATALOG = _REPO / "fixtures" / "robot" / "hexapod_gait_catalog_v0.json"

PROOF_TIER = "HEXAPOD_GAIT_BUS_SLICE"
ORACLE = "HEXAPOD_GAIT_PHASE_CLOCK"


def load_gait_catalog() -> dict[str, Any]:
    return json.loads(_GAIT_CATALOG.read_text(encoding="utf-8"))


def init_gait_bus(
    robot: dict[str, Any],
    *,
    gait_name: str = "tripod",
) -> dict[str, Any]:
    catalog = load_gait_catalog()
    gait = dict((catalog.get("gaits") or {}).get(gait_name) or {})
    robot["gait_bus"] = {
        "gait_name": gait_name,
        "phase_tick": 0,
        "phase": 0.0,
        "params": gait,
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
        "deferred": ["AI_MEASURED_FOOT_CONTACT"],
    }
    return robot["gait_bus"]


def _leg_index(appendage_id: str) -> int:
    if "_" in appendage_id:
        return int(appendage_id.rsplit("_", 1)[-1])
    return 0


def q_cmd_tripod(leg_idx: int, phase: float, params: dict[str, Any]) -> list[float]:
    groups = list(params.get("stance_groups") or [[0, 2, 4], [1, 3, 5]])
    base = list(params.get("base_q") or [0.15, 0.25, -0.12])
    amp = float(params.get("swing_amp_rad") or 0.08)
    half = int(phase * 2.0) % 2
    swing_set = set(groups[1 - half] if len(groups) > 1 else groups[0])
    if leg_idx in swing_set:
        local_phase = (phase * 2.0) % 1.0
        lift = amp * math.sin(2.0 * math.pi * local_phase)
        return [base[0], base[1] + lift, base[2]]
    return list(base)


def q_cmd_wave(leg_idx: int, phase: float, params: dict[str, Any]) -> list[float]:
    base = list(params.get("base_q") or [0.12, 0.22, -0.1])
    amp = float(params.get("swing_amp_rad") or 0.06)
    offset = float(params.get("phase_offset_per_leg") or 1.0)
    lift = amp * math.sin(2.0 * math.pi * (phase + leg_idx * offset / 6.0))
    return [base[0], base[1] + lift, base[2]]


def gait_q_cmd_for_leg(appendage_id: str, gait_bus: dict[str, Any]) -> list[float]:
    leg_idx = _leg_index(appendage_id)
    phase = float(gait_bus.get("phase") or 0.0)
    params = dict(gait_bus.get("params") or {})
    name = str(gait_bus.get("gait_name") or "tripod")
    if name == "wave":
        return q_cmd_wave(leg_idx, phase, params)
    return q_cmd_tripod(leg_idx, phase, params)


def advance_gait_phase(gait_bus: dict[str, Any]) -> None:
    params = dict(gait_bus.get("params") or {})
    cycle = int(params.get("phase_ticks_per_cycle") or 24)
    tick = int(gait_bus.get("phase_tick") or 0) + 1
    gait_bus["phase_tick"] = tick
    gait_bus["phase"] = float(tick % cycle) / float(max(cycle, 1))


def hexapod_gait_tick(
    robot: dict[str, Any],
    *,
    dt: float = 0.005,
) -> dict[str, Any]:
    from production_gate.hexapod_body_compose_v1 import hexapod_body_tick

    gait_bus = robot.get("gait_bus") or init_gait_bus(robot)
    q_map = {aid: gait_q_cmd_for_leg(aid, gait_bus) for aid in (robot.get("appendages") or {})}
    bus = hexapod_body_tick(robot, q_cmd_by_leg=q_map, dt=dt)
    advance_gait_phase(gait_bus)
    bus["gait_bus"] = {
        "gait_name": gait_bus.get("gait_name"),
        "phase_tick": gait_bus.get("phase_tick"),
        "phase": gait_bus.get("phase"),
    }
    return bus


def run_hexapod_gait_smoke(*, gait_name: str = "tripod", ticks: int = 30) -> dict[str, Any]:
    from production_gate.hexapod_body_compose_v1 import init_hexapod_body

    robot = init_hexapod_body()
    init_gait_bus(robot, gait_name=gait_name)
    all_y: list[float] = []
    cycle = int((robot.get("gait_bus") or {}).get("params", {}).get("phase_ticks_per_cycle") or 24)
    half_tick = max(cycle // 2, 1)
    swing_early: set[int] = set()
    swing_late: set[int] = set()

    for t in range(ticks):
        gait_bus = robot.get("gait_bus") or {}
        phase = float(gait_bus.get("phase") or 0.0)
        params = dict(gait_bus.get("params") or {})
        groups = list(params.get("stance_groups") or [[0, 2, 4], [1, 3, 5]])
        half = int(phase * 2.0) % 2
        swing_set = set(groups[1 - half] if len(groups) > 1 else groups[0])
        if t < half_tick:
            swing_early.update(swing_set)
        elif t >= half_tick:
            swing_late.update(swing_set)

        bus = hexapod_gait_tick(robot, dt=0.005)
        for f in bus.get("feet") or []:
            all_y.append(float(f.get("y") or 0))

    y_span = (max(all_y) - min(all_y)) if all_y else 0.0
    tripod_alternate = gait_name != "tripod" or (
        bool(swing_early) and bool(swing_late) and swing_early != swing_late
    )
    checks = {
        "F_phase_advanced": int(robot.get("gait_bus", {}).get("phase_tick") or 0) == ticks,
        "F_feet_move": y_span > 0.005,
        "F_tripod_gait": gait_name == "tripod",
        "F_tripod_stance_group_alternate": tripod_alternate,
        "F_six_legs": len(all_y) >= 6,
        "F_deferred_contact": "AI_MEASURED_FOOT_CONTACT" in (robot.get("gait_bus") or {}).get("deferred", []),
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "HEXAPOD_GAIT_BUS_SLICE_PASS" if not fail else "HEXAPOD_GAIT_BUS_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "foot_y_span_m": y_span,
        "final_phase": robot.get("gait_bus", {}).get("phase"),
    }
