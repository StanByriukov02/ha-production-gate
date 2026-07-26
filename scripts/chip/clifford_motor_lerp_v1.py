"""Motor Lerp candidates + scope metrics (T3)."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_REPO = Path(__file__).resolve().parents[2]


def _oracle():
    from scripts.chip import clifford_pga8_oracle_v0 as o

    return o


def _motor7_module():
    from dogfood_platform.slam_se3_motor_v1 import Motor, Vec3

    return Motor, Vec3


def _pga8_from_angle_z(theta: float):
    from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8

    return MotorPGA8.from_blades(s=math.cos(theta / 2), e12=math.sin(theta / 2))


def _coeffs_to_motor7(coeffs: list[int]):
    from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8
    from scripts.chip.clifford_motor7_pga8_bridge_v0 import pga8_rotor_to_motor7_quat

    Motor, _ = _motor7_module()
    qw, qx, qy, qz = pga8_rotor_to_motor7_quat(MotorPGA8(tuple(coeffs)))
    return Motor(qw, qx, qy, qz, 0.0, 0.0, 0.0)


def _quat_slerp(m0, m1, t: float):
    """Gold reference — motor7 quaternion slerp + translation lerp."""
    import numpy as np

    q0 = np.array([m0.qw, m0.qx, m0.qy, m0.qz], dtype=float)
    q1 = np.array([m1.qw, m1.qx, m1.qy, m1.qz], dtype=float)
    dot = float(np.clip(np.dot(q0, q1), -1.0, 1.0))
    if dot < 0.0:
        q1 = -q1
        dot = -dot
    if dot > 0.9995:
        q = q0 + t * (q1 - q0)
    else:
        theta_0 = math.acos(dot)
        sin_theta_0 = math.sin(theta_0)
        theta = theta_0 * t
        s0 = math.sin(theta_0 - theta) / sin_theta_0
        s1 = math.sin(theta) / sin_theta_0
        q = s0 * q0 + s1 * q1
    q = q / np.linalg.norm(q)
    tx = m0.tx + t * (m1.tx - m0.tx)
    ty = m0.ty + t * (m1.ty - m0.ty)
    tz = m0.tz + t * (m1.tz - m0.tz)
    Motor, _ = _motor7_module()
    return Motor(float(q[0]), float(q[1]), float(q[2]), float(q[3]), tx, ty, tz)


def lerp_coeff_norm(c0: list[int], c1: list[int], t: float) -> list[int]:
    o = _oracle()
    out = []
    for a, b in zip(c0, c1):
        if not a and not b:
            out.append(0)
            continue
        v = (1.0 - t) * o.bf16_to_f32(a) + t * o.bf16_to_f32(b)
        out.append(o.f32_to_bf16(v))
    return o.norm_coeffs(out)


def lerp_quat_slerp_trans(c0: list[int], c1: list[int], t: float) -> list[int]:
    o = _oracle()
    m0 = _coeffs_to_motor7(c0)
    m1 = _coeffs_to_motor7(c1)
    m = _quat_slerp(m0, m1, t)
    from scripts.chip.clifford_motor7_pga8_bridge_v0 import motor7_quat_to_pga8_rotor

    rotor = motor7_quat_to_pga8_rotor(m)
    return list(rotor.coeffs)


def lerp_screw_linear(c0: list[int], c1: list[int], t: float) -> list[int]:
    """Screw-linear proxy: nlerp coeffs on even rotor lanes + norm."""
    o = _oracle()
    even = (0, 4, 5, 6)
    out = list(c0)
    for k in even:
        if c0[k] or c1[k]:
            v = (1.0 - t) * o.bf16_to_f32(c0[k]) + t * o.bf16_to_f32(c1[k])
            out[k] = o.f32_to_bf16(v)
    return o.norm_coeffs(out)


CANDIDATES: dict[str, Callable[[list[int], list[int], float], list[int]]] = {
    "coeff_lerp_norm": lerp_coeff_norm,
    "quat_slerp_trans": lerp_quat_slerp_trans,
    "screw_linear_norm": lerp_screw_linear,
}

IRON_OP_ESTIMATE = {
    "coeff_lerp_norm": {"lerp_adds": 8, "norm_macro": 1, "geo_prod": 0},
    "quat_slerp_trans": {"lerp_adds": 0, "norm_macro": 0, "geo_prod": 0, "host_trig": True},
    "screw_linear_norm": {"lerp_adds": 4, "norm_macro": 1, "geo_prod": 0},
}


def _angular_error_rad(coeffs: list[int], gold_coeffs: list[int]) -> float:
    m = _coeffs_to_motor7(coeffs)
    g = _coeffs_to_motor7(gold_coeffs)
    dot = abs(m.qw * g.qw + m.qx * g.qx + m.qy * g.qy + m.qz * g.qz)
    dot = min(1.0, max(-1.0, dot))
    return 2.0 * math.acos(dot)


def _scope_lc2_hip(n: int = 24) -> tuple[list[int], list[int]]:
    a = _pga8_from_angle_z(0.0).as_list()
    b = _pga8_from_angle_z(math.pi / 4).as_list()
    return a, b


def _scope_bench_cross_axis() -> tuple[list[int], list[int]]:
    """Stress: incompatible 90° axes — coeff nlerp diverges from slerp gold."""
    from dogfood_platform.slam_se3_motor_v1 import motor_from_axis_angle
    from scripts.chip.clifford_motor7_pga8_bridge_v0 import motor7_quat_to_pga8_rotor

    rz = motor_from_axis_angle((0.0, 0.0, 1.0), math.pi / 2, (0.0, 0.0, 0.0))
    rx = motor_from_axis_angle((1.0, 0.0, 0.0), math.pi / 2, (0.0, 0.0, 0.0))
    return list(motor7_quat_to_pga8_rotor(rz).coeffs), list(motor7_quat_to_pga8_rotor(rx).coeffs)


def _scope_lunar_slow(n: int = 48) -> tuple[list[int], list[int]]:
    return _pga8_from_angle_z(0.0).as_list(), _pga8_from_angle_z(math.pi / 6).as_list()


def _scope_lunar_vibe(n: int = 32) -> tuple[list[int], list[int]]:
    base = _pga8_from_angle_z(0.05).as_list()
    wobble = _pga8_from_angle_z(0.05 + 0.02).as_list()
    return base, wobble


def _scope_cave_slam() -> tuple[list[int], list[int]]:
    from dogfood_platform.slam_pga8_motion_v1 import SlamPose

    trail = json.loads(
        (_REPO / "fixtures/twin/robot_chassis_motion_trail_v1.json").read_text(encoding="utf-8")
    )
    pts = trail["points"]
    p0 = SlamPose.identity()
    p1 = SlamPose.identity()
    p1_rot = _pga8_from_angle_z(0.08)
    from scripts.chip.clifford_motor7_pga8_bridge_v0 import motor7_quat_to_pga8_rotor

    p1 = SlamPose(rotor=p1_rot, translation=(pts[-1]["x_m"], pts[-1]["y_m"], pts[-1]["z_m"]))
    return list(p0.rotor.coeffs), list(p1.rotor.coeffs)


SCOPES: dict[str, Any] = {
    "lc2_bench_hip": {"fn": _scope_lc2_hip, "n_steps": 24, "tag": "bench"},
    "bench_cross_axis_stress": {"fn": _scope_bench_cross_axis, "n_steps": 48, "tag": "bench"},
    "cave_slam_corridor": {"fn": _scope_cave_slam, "n_steps": 24, "tag": "cave"},
    "lunar_slow_joint": {"fn": _scope_lunar_slow, "n_steps": 48, "tag": "lunar"},
    "lunar_fast_vibe": {"fn": _scope_lunar_vibe, "n_steps": 32, "tag": "lunar"},
}


def evaluate_scope(scope_id: str) -> dict[str, Any]:
    spec = SCOPES[scope_id]
    c0, c1 = spec["fn"]()
    n = spec["n_steps"]
    rows: list[dict[str, Any]] = []
    max_err: dict[str, float] = {k: 0.0 for k in CANDIDATES}

    for i in range(n + 1):
        t = i / n if n else 0.0
        gold = lerp_quat_slerp_trans(c0, c1, t)
        row: dict[str, Any] = {"t": t, "gold_hex": _oracle().motor_hex(gold)}
        for cid, fn in CANDIDATES.items():
            got = fn(c0, c1, t)
            err = _angular_error_rad(got, gold)
            max_err[cid] = max(max_err[cid], err)
            row[f"{cid}_err_rad"] = err
        rows.append(row)

    winner = min(max_err, key=max_err.get)
    return {
        "scope_id": scope_id,
        "tag": spec["tag"],
        "n_steps": n,
        "max_angular_err_rad": max_err,
        "winner": winner,
        "samples": rows[:: max(1, n // 4)],
    }


def build_study_doc() -> dict[str, Any]:
    from datetime import datetime, timezone

    scopes = {sid: evaluate_scope(sid) for sid in SCOPES}
    per_candidate: dict[str, list[float]] = {k: [] for k in CANDIDATES}
    for s in scopes.values():
        for cid, err in s["max_angular_err_rad"].items():
            per_candidate[cid].append(err)

    overall_winner = min(
        CANDIDATES,
        key=lambda cid: max(per_candidate[cid]) if per_candidate[cid] else 1e9,
    )

    lunar_scopes = [s for s in scopes.values() if s["tag"] == "lunar"]
    bench_scopes = [s for s in scopes.values() if s["tag"] == "bench"]
    lunar_winner = min(
        CANDIDATES,
        key=lambda cid: max(s["max_angular_err_rad"][cid] for s in lunar_scopes),
    )
    bench_winner = min(
        CANDIDATES,
        key=lambda cid: max(s["max_angular_err_rad"][cid] for s in bench_scopes),
    )

    promote_opcode = overall_winner == "screw_linear_norm" and max(per_candidate[overall_winner]) < 0.05
    verdict_hint = "PROMOTE_OPCODE" if promote_opcode else "RUNTIME_ONLY"

    return {
        "study_id": "clifford_motor_lerp_study_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "candidates": list(CANDIDATES.keys()),
        "gold_reference": "quat_slerp_trans",
        "scopes": scopes,
        "overall_winner": overall_winner,
        "lunar_winner": lunar_winner,
        "bench_winner": bench_winner,
        "iron_op_estimate": IRON_OP_ESTIMATE,
        "triple_layer": {
            "opcode": "V_MOTOR_LERP optional — norm macro if promoted",
            "runtime": "quat_slerp_trans host path for SlamPose trajectories",
            "power_cache": "coeff_lerp cheapest but worst geodesic — HUD only",
        },
        "verdict_hint": verdict_hint,
        "honesty": {
            "nl_geodesic": "REJECTED — no lunar doc formula",
            "scope_split": lunar_winner != bench_winner,
            "falsifier": "coeff_lerp_norm diverges on bench_cross_axis_stress >0.03 rad",
        },
    }
