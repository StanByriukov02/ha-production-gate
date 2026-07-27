"""ManipulatorIntegratorPort v1 — Rust kinematics tick · live state · kernel mutex.

Phase B: joint bus + symplectic step on kernel tick. Python glue only.
TABU: RT servo · claim flight arm · Python FK truth.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CHAIN = _REPO / "fixtures" / "robot" / "lunar_manipulator_chain_v1.json"
_CONTRACT = _REPO / "fixtures" / "robot" / "manipulator_kinematics_port_v0.json"

PROOF_TIER = "HAL_MANIPULATOR_SLICE"
BACKEND_RUST_SERIAL = "manipulator_rust_serial_arm_v1"

MANIP_PHASE_IDLE = "idle"
MANIP_PHASE_HOLD = "hold"
MANIP_PHASE_MOVE = "move"
MANIP_PHASE_GRASP = "grasp"

DEFAULT_JOINT_Q = [0.2, 0.3, -0.1]
DEFAULT_JOINT_Q_DOT = [0.0, 0.0, 0.0]
KP_TEACHING = 8.0
KD_TEACHING = 1.2


def load_chain() -> dict[str, Any]:
    return json.loads(_CHAIN.read_text(encoding="utf-8"))


def default_carrier_manipulator_fields() -> dict[str, Any]:
    return {
        "manipulator_phase": MANIP_PHASE_IDLE,
        "manipulator_command": "idle",
        "joint_positions_rad": list(DEFAULT_JOINT_Q),
        "joint_velocities_rad_s": list(DEFAULT_JOINT_Q_DOT),
        "joint_torques_nm": [0.0, 0.0, 0.0],
        "joint_positions_target_rad": list(DEFAULT_JOINT_Q),
        "ee_pose": {"ee_x": 0.0, "ee_y": 0.0, "ee_theta": 0.0},
        "ee_pose_motor": None,
        "ee_pose_motor128_hex": None,
        "manipulator_backend": BACKEND_RUST_SERIAL,
        "manipulator_mutex": None,
        "manipulator_material_bind": None,
        "manipulator_material_derate": None,
        "manipulator_torque_scale": 1.0,
        "manipulator_governance_hold": None,
        "ee_pose_world_motor": None,
        "construct_work_zone": None,
        "construct_arm_mutex": None,
        "grasp_bind": None,
        "grasp_state": None,
        "grasp_command_force_n": None,
        "grasp_envelope": None,
        "joint_encoder_counts": None,
        "iron_hal_mmio": None,
    }


def ensure_carrier_manipulator_defaults(carrier: dict[str, Any]) -> dict[str, Any]:
    defaults = default_carrier_manipulator_fields()
    for key, val in defaults.items():
        if key not in carrier:
            carrier[key] = val if not isinstance(val, list) else list(val)
    return carrier


def init_manipulator_integrator_bind(
    state: dict[str, Any],
    *,
    enabled: bool = True,
    backend: str = BACKEND_RUST_SERIAL,
    dt_s: float = 0.005,
) -> dict[str, Any]:
    chain = load_chain()
    state["manipulator_integrator"] = {
        "enabled": enabled,
        "backend": backend,
        "chain_id": chain.get("chain_id"),
        "dt_s": dt_s,
        "g_m_s2": float((chain.get("gravity") or {}).get("lunar_m_s2") or 1.62),
        "proof_tier": PROOF_TIER,
    }
    for cid, carrier in (state.get("carriers") or {}).items():
        ensure_carrier_manipulator_defaults(carrier)
    return state["manipulator_integrator"]


def ensure_manipulator_integrator_bind(state: dict[str, Any]) -> dict[str, Any]:
    if "manipulator_integrator" in state:
        return state["manipulator_integrator"]
    return init_manipulator_integrator_bind(state, enabled=True)


def manipulator_integrator_enabled(state: dict[str, Any]) -> bool:
    return bool((state.get("manipulator_integrator") or {}).get("enabled"))


def _ee_to_motor(ee_x: float, ee_y: float, ee_theta: float) -> dict[str, float]:
    from production_gate.slam_se3_motor_v1 import motor_from_axis_angle

    half = ee_theta * 0.5
    m = motor_from_axis_angle((0.0, 0.0, 1.0), half, (ee_x, ee_y, 0.0))
    return {
        "qw": round(m.qw, 6),
        "qx": round(m.qx, 6),
        "qy": round(m.qy, 6),
        "qz": round(m.qz, 6),
        "tx": round(m.tx, 6),
        "ty": round(m.ty, 6),
        "tz": round(m.tz, 6),
    }


def _refresh_ee_from_joints(carrier: dict[str, Any], *, g: float, build: bool) -> dict[str, Any]:
    from production_gate.manipulator_kinematics_port_v1 import RustSerialArmBackend

    q = list(carrier.get("joint_positions_rad") or DEFAULT_JOINT_Q)
    fk = RustSerialArmBackend().fk(q, g=g, build=build)
    carrier["ee_pose"] = {
        "ee_x": round(float(fk["ee_x"]), 6),
        "ee_y": round(float(fk["ee_y"]), 6),
        "ee_theta": round(float(fk["ee_theta"]), 6),
    }
    carrier["ee_pose_motor"] = _ee_to_motor(fk["ee_x"], fk["ee_y"], fk["ee_theta"])
    try:
        from production_gate.manipulator_ee_pose_cxx_parity_v1 import motor7_to_rotor_hex

        carrier["ee_pose_motor128_hex"] = motor7_to_rotor_hex(carrier["ee_pose_motor"])
    except Exception:
        carrier["ee_pose_motor128_hex"] = None
    carrier["manipulator_backend"] = BACKEND_RUST_SERIAL
    return fk


def resolve_traverse_arm_mutex(carrier: dict[str, Any]) -> str:
    """Return arm_hold | arm_move | arm_idle."""
    if carrier.get("construct_arm_traverse_hold"):
        return "arm_hold"
    live_cmd = str(carrier.get("command") or "idle")
    manip_cmd = str(carrier.get("manipulator_command") or "idle")
    if manip_cmd == "move" and live_cmd == "traverse":
        return "arm_hold"
    if manip_cmd == "move":
        return "arm_move"
    if manip_cmd == "grasp":
        return "arm_grasp"
    if manip_cmd in ("hold",):
        return "arm_hold"
    return "arm_idle"


def _pd_torques(
    q: list[float],
    q_dot: list[float],
    q_target: list[float],
    *,
    kp: float = KP_TEACHING,
    kd: float = KD_TEACHING,
) -> list[float]:
    torques: list[float] = []
    for i in range(len(q)):
        torques.append(kp * (q_target[i] - q[i]) - kd * q_dot[i])
    return torques


def _advance_joint_dynamics(
    state: dict[str, Any],
    carrier: dict[str, Any],
    *,
    q: list[float],
    q_dot: list[float],
    torques: list[float],
    dt: float,
    g: float,
    build: bool,
) -> tuple[list[float], list[float], list[float]]:
    from production_gate.manipulator_iron_hal_port_v1 import resolve_manipulator_iron_hal_port

    iron = resolve_manipulator_iron_hal_port(state)
    if iron is not None:
        iron.apply_torque_tick(state, carrier, torques=torques, dt=dt, g=g)
        return (
            list(carrier.get("joint_positions_rad") or q),
            list(carrier.get("joint_velocities_rad_s") or q_dot),
            list(carrier.get("joint_torques_nm") or torques),
        )
    from production_gate.manipulator_kinematics_port_v1 import RustSerialArmBackend

    rep = RustSerialArmBackend().symplectic_step(
        q=q,
        q_dot=q_dot,
        torques=torques,
        steps=1,
        dt=dt,
        g=g,
        build=build,
    )
    final = rep.get("final_state") or {}
    q_out = [round(float(x), 6) for x in final.get("q") or q]
    qd_out = [round(float(x), 6) for x in final.get("q_dot") or q_dot]
    t_out = [round(float(x), 4) for x in torques]
    return q_out, qd_out, t_out


def advance_manipulator_tick(
    state: dict[str, Any],
    carrier: dict[str, Any],
    *,
    build: bool = True,
) -> dict[str, Any]:
    """One kernel tick — symplectic joint step when mutex allows move."""
    ensure_carrier_manipulator_defaults(carrier)
    cfg = state.get("manipulator_integrator") or {}
    g = float(cfg.get("g_m_s2") or 1.62)
    dt = float(cfg.get("dt_s") or 0.005)

    coord_row: dict[str, Any] = {"coord_active": False}
    try:
        from production_gate.fleet_construct_arm_coord_v1 import apply_construct_arm_coord_before_tick

        cid = str(carrier.get("carrier_id") or "scout_A")
        coord_row = apply_construct_arm_coord_before_tick(state, cid)
        if coord_row.get("coord_active") and not coord_row.get("allowed"):
            carrier["manipulator_phase"] = MANIP_PHASE_HOLD
            carrier["manipulator_mutex"] = "arm_hold"
            carrier["joint_torques_nm"] = [0.0, 0.0, 0.0]
            fk = _refresh_ee_from_joints(carrier, g=g, build=build)
            return {
                "mutex": "arm_hold",
                "manipulator_phase": MANIP_PHASE_HOLD,
                "joint_positions_rad": carrier.get("joint_positions_rad"),
                "ee_pose": carrier.get("ee_pose"),
                "fk": fk,
                "governance": {"coord_active": True},
                "construct_arm_coord": coord_row,
            }
    except Exception:
        coord_row = {"coord_active": False}

    gov_row: dict[str, Any] = {"governance_active": False, "allowed": True, "torque_scale": 1.0}
    try:
        from production_gate.robot_os_manipulator_governed_actuation_v1 import (
            apply_manipulator_governance_before_tick,
            manipulator_governance_enabled,
        )

        if manipulator_governance_enabled(state):
            gov_row = apply_manipulator_governance_before_tick(
                state,
                str(carrier.get("carrier_id") or "scout_A"),
            )
    except Exception:
        gov_row = {"governance_active": False, "allowed": True, "torque_scale": 1.0}

    mutex = resolve_traverse_arm_mutex(carrier)
    if gov_row.get("governance_active") and not gov_row.get("allowed"):
        mutex = "arm_hold"
    carrier["manipulator_mutex"] = mutex

    q = [float(x) for x in carrier.get("joint_positions_rad") or DEFAULT_JOINT_Q]
    q_dot = [float(x) for x in carrier.get("joint_velocities_rad_s") or DEFAULT_JOINT_Q_DOT]
    q_tgt = [float(x) for x in carrier.get("joint_positions_target_rad") or q]

    if mutex == "arm_move":
        torques = _pd_torques(q, q_dot, q_tgt)
        torque_scale = float(gov_row.get("torque_scale") or carrier.get("manipulator_torque_scale") or 1.0)
        try:
            from production_gate.robot_os_manipulator_governance_interceptor_v1 import (
                clip_joint_torques,
                load_manipulator_governance_envelope,
            )

            envelope = load_manipulator_governance_envelope()
            torques = clip_joint_torques(torques, envelope=envelope, torque_scale=torque_scale)
        except Exception:
            torques = [round(t * torque_scale, 4) for t in torques]
        q, q_dot, torques = _advance_joint_dynamics(
            state,
            carrier,
            q=q,
            q_dot=q_dot,
            torques=torques,
            dt=dt,
            g=g,
            build=build,
        )
        carrier["joint_positions_rad"] = q
        carrier["joint_velocities_rad_s"] = q_dot
        carrier["joint_torques_nm"] = torques
        carrier["manipulator_phase"] = MANIP_PHASE_MOVE
    elif mutex == "arm_grasp":
        from production_gate.manipulator_grasp_force_port_v1 import load_grasp_force_envelope
        from production_gate.manipulator_grasp_loop_v1 import advance_grasp_force_tick

        grasp_rep = advance_grasp_force_tick(state, carrier, build=build)
        env = load_grasp_force_envelope()
        gi = int(env.get("gripper_joint_index") or 2)
        hold_kp = float(env.get("arm_hold_kp") or 12.0)
        hold_kd = float(env.get("arm_hold_kd") or 1.5)
        torques = [0.0, 0.0, 0.0]
        for i in range(min(gi, len(q))):
            torques[i] = hold_kp * (q_tgt[i] - q[i]) - hold_kd * q_dot[i]
        if gi < len(torques):
            torques[gi] = float(grasp_rep.get("gripper_torque_nm") or 0.0)
        q, q_dot, torques = _advance_joint_dynamics(
            state,
            carrier,
            q=q,
            q_dot=q_dot,
            torques=torques,
            dt=dt,
            g=g,
            build=build,
        )
        carrier["joint_positions_rad"] = q
        carrier["joint_velocities_rad_s"] = q_dot
        carrier["joint_torques_nm"] = torques
        carrier["manipulator_phase"] = MANIP_PHASE_GRASP
    elif mutex == "arm_hold":
        carrier["manipulator_phase"] = MANIP_PHASE_HOLD
        carrier["joint_torques_nm"] = [0.0, 0.0, 0.0]
    else:
        carrier["manipulator_phase"] = MANIP_PHASE_IDLE

    fk = _refresh_ee_from_joints(carrier, g=g, build=build)
    world_row: dict[str, Any] = {}
    try:
        from production_gate.fleet_construct_arm_coord_v1 import apply_construct_arm_coord_after_tick

        world_row = apply_construct_arm_coord_after_tick(
            state,
            str(carrier.get("carrier_id") or "scout_A"),
        )
    except Exception:
        world_row = {}
    return {
        "mutex": mutex,
        "manipulator_phase": carrier.get("manipulator_phase"),
        "joint_positions_rad": carrier.get("joint_positions_rad"),
        "ee_pose": carrier.get("ee_pose"),
        "fk": fk,
        "governance": gov_row,
        "construct_arm_coord": coord_row,
        "ee_pose_world": world_row,
        "grasp": carrier.get("grasp_state"),
    }


def manipulator_tick_snapshot(state: dict[str, Any], carrier_id: str) -> dict[str, Any]:
    if not manipulator_integrator_enabled(state):
        return {"manipulator_kernel_active": False}
    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    ensure_carrier_manipulator_defaults(carrier)
    ee = carrier.get("ee_pose") or {}
    motor = carrier.get("ee_pose_motor")
    return {
        "manipulator_kernel_active": True,
        "manipulator_backend": carrier.get("manipulator_backend"),
        "manipulator_phase": carrier.get("manipulator_phase"),
        "manipulator_mutex": carrier.get("manipulator_mutex"),
        "joint_positions_rad": carrier.get("joint_positions_rad"),
        "ee_pose": ee,
        "ee_pose_motor_present": isinstance(motor, dict) and motor.get("qw") is not None,
        "ee_x": ee.get("ee_x"),
        "ee_y": ee.get("ee_y"),
    }


def run_manipulator_hal_smoke(*, build: bool = True) -> dict[str, Any]:
    from production_gate.fleet_live_state_v1 import empty_state
    from production_gate.robot_os_hal_sim_v1 import attach_sim_hal_to_kernel
    from production_gate.robot_os_kernel_v1 import RobotOsKernel

    state = empty_state(carrier_ids=("scout_A",))
    state["clifford_bind"] = {
        "profile_id": "lunar_crater_5km",
        "stack_replay_hash": "manip_hal_slice_hash",
        "map_ledger_hash": "c0ffee0000000001",
    }
    init_manipulator_integrator_bind(state)
    c = state["carriers"]["scout_A"]
    c.update(
        {
            "phase": "idle",
            "command": "idle",
            "segment_start_m": 0.0,
            "segment_end_m": 600.0,
            "cursor_m": 0.0,
            "ticks": 0,
            "map_hash": "c0ffee0000000001",
            "manipulator_command": "move",
            "joint_positions_target_rad": [0.45, 0.35, -0.12],
        }
    )

    kernel = RobotOsKernel("scout_A", wh_budget_wh=10_000.0)
    attach_sim_hal_to_kernel(kernel, state)

    q_before = list(c["joint_positions_rad"])
    for _ in range(5):
        state = kernel.tick_state(state)
    c = state["carriers"]["scout_A"]
    q_after_move = list(c["joint_positions_rad"])
    arm_moved = any(abs(a - b) > 1e-5 for a, b in zip(q_after_move, q_before))
    ee_after_idle = dict(c.get("ee_pose") or {})

    c["command"] = "traverse"
    c["phase"] = "traverse"
    c["manipulator_command"] = "move"
    q_at_mutex = list(c["joint_positions_rad"])
    cursor_before = float(c["cursor_m"])
    for _ in range(3):
        state = kernel.tick_state(state)
    c = state["carriers"]["scout_A"]
    q_during_traverse = list(c["joint_positions_rad"])
    cursor_after = float(c["cursor_m"])
    joints_frozen = all(abs(a - b) < 1e-5 for a, b in zip(q_during_traverse, q_at_mutex))
    traverse_advanced = cursor_after > cursor_before
    mutex_ok = c.get("manipulator_mutex") == "arm_hold"

    checks = {
        "F_integrator_enabled": manipulator_integrator_enabled(state),
        "F_arm_moves_when_idle": arm_moved,
        "F_ee_pose_present": ee_after_idle.get("ee_x") is not None,
        "F_ee_pose_motor": isinstance(c.get("ee_pose_motor"), dict),
        "F_traverse_arm_mutex_hold": mutex_ok and joints_frozen,
        "F_traverse_advances_under_mutex": traverse_advanced,
        "F_joint_fields_on_carrier": len(c.get("joint_positions_rad") or []) == 3,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "MANIPULATOR_HAL_SLICE_PASS" if not fail else "MANIPULATOR_HAL_SLICE_FAIL",
        "proof_tier": PROOF_TIER,
        "checks": checks,
        "fail": fail,
        "q_before": q_before,
        "q_after_idle_move": q_after_move,
        "q_during_traverse": q_during_traverse,
        "cursor_delta_m": round(cursor_after - cursor_before, 4),
        "manipulator_mutex": c.get("manipulator_mutex"),
        "product_ready": False,
    }
