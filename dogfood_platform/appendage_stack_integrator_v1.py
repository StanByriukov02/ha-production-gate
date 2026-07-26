"""Appendage stack integrator v1 — chain IR · FK · actuator · calibration in one tick."""
from __future__ import annotations

import math
from typing import Any

PROOF_TIER = "APPENDAGE_STACK_INTEGRATOR_SLICE"
ORACLE = "APPENDAGE_STACK_BUS"


def default_stack_state(chain_id: str) -> dict[str, Any]:
    from dogfood_platform.kinematic_chain_ir_v1 import resolve_chain_spec

    spec = resolve_chain_spec(chain_id)
    dof = int(spec.get("dof") or 1)
    return {
        "chain_id": chain_id,
        "dof": dof,
        "q": [0.0] * dof,
        "q_cmd": [0.0] * dof,
        "calibration": {
            "encoder_zero_rad": 0.0,
            "backlash_rad": 0.0,
        },
        "ticks": 0,
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
    }


def apply_calibration_to_q(q_raw: list[float], calibration: dict[str, Any]) -> list[float]:
    z = float(calibration.get("encoder_zero_rad") or 0.0)
    return [float(v) - z for v in q_raw]


def appendage_stack_tick(
    stack: dict[str, Any],
    *,
    q_cmd: list[float] | None = None,
    dt: float = 0.005,
    torques: list[float] | None = None,
    use_backlash_model: bool = False,
) -> dict[str, Any]:
    from dogfood_platform.actuator_plugin_bus_v1 import resolve_actuator_plugin
    from dogfood_platform.kinematic_chain_ir_v1 import fk_for_chain, resolve_chain_spec

    chain_id = str(stack["chain_id"])
    spec = resolve_chain_spec(chain_id)
    dof = int(stack.get("dof") or spec.get("dof") or 1)
    cmd = list(q_cmd if q_cmd is not None else stack.get("q_cmd") or [0.0] * dof)
    stack["q_cmd"] = cmd

    plugin = resolve_actuator_plugin(chain_id, wrap_backlash=use_backlash_model)
    g = float(spec.get("gravity_m_s2") or 1.62)
    act = plugin.tick(q_cmd=cmd, dt=dt, q=list(stack.get("q") or [0.0] * dof), torques=torques, g=g)
    q_raw = [float(x) for x in act.get("q") or stack["q"]]
    q_cal = apply_calibration_to_q(q_raw, stack.get("calibration") or {})
    stack["q"] = q_cal
    stack["ticks"] = int(stack.get("ticks") or 0) + 1

    fk = fk_for_chain(chain_id, q_cal, g=g, build=False)
    bus = {
        "chain_id": chain_id,
        "q": q_cal,
        "q_cmd": cmd,
        "q_raw": q_raw,
        "ee": {
            "x": fk.get("ee_x"),
            "y": fk.get("ee_y"),
            "z": fk.get("ee_z"),
        },
        "actuator": act,
        "calibration": stack.get("calibration"),
        "ticks": stack["ticks"],
        "backend": act.get("backend"),
    }
    stack["bus"] = bus
    return bus


def run_appendage_stack_smoke() -> dict[str, Any]:
    scout = "lunar_manipulator_chain_scout_3dof_v1"
    lc2 = "lc2_bench_hip_1dof_v1"

    scout_stack = default_stack_state(scout)
    scout_bus = appendage_stack_tick(
        scout_stack,
        q_cmd=[0.25, 0.15, -0.1],
        dt=0.005,
        torques=[0.2, 0.1, 0.05],
    )

    lc2_stack = default_stack_state(lc2)
    lc2_bus = appendage_stack_tick(
        lc2_stack,
        q_cmd=[0.35],
        dt=1.0 / 20000.0,
        torques=[0.15],
    )

    checks = {
        "F_scout_bus_ee": abs(float(scout_bus["ee"]["x"] or 0)) > 0,
        "F_scout_actuator_sim": scout_bus.get("backend") == "sim_symplectic",
        "F_lc2_bus_ee": float(lc2_bus["ee"]["x"] or 0) > 0 or abs(float(lc2_bus["ee"]["z"] or 0)) > 0,
        "F_lc2_actuator_iron": lc2_bus.get("backend") == "lc2_iron_teaching",
        "F_ticks_increment": int(scout_stack["ticks"]) == 1,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "APPENDAGE_STACK_INTEGRATOR_SLICE_PASS" if not fail else "APPENDAGE_STACK_INTEGRATOR_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "scout_bus": scout_bus,
        "lc2_bus": lc2_bus,
    }
