"""L5 loop closure — cave revisit detect + pose-graph correction (envelope sim)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from dogfood_platform.slam_se3_motor_v1 import Motor, Vec3, compose_motors, motor_from_axis_angle, rmse_m

CPU_HZ = 48_000_000
CYCLES_PER_POSE_COMPARE = 2_400
CYCLES_PER_CLOSURE_OPTIMIZE = 180_000
LOOP_DETECT_RADIUS_M = 0.35
MIN_LOOP_INDEX_GAP = 12
ANCHOR_FRACTION = 0.25
DRIFT_FALSIFIER_M = 0.5
CLOSURE_BUDGET_MS = 2000.0


@dataclass(frozen=True)
class PoseNode:
    index: int
    motor: Motor
    position: Vec3


def _motor_position(m: Motor) -> Vec3:
    return m.tx, m.ty, m.tz


def _dist(a: Vec3, b: Vec3) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def simulate_loop_trajectory(
    points: list[Vec3],
    *,
    n_forward: int = 28,
    step_m: float = 0.05,
    noise_sigma_m: float = 0.028,
    seed: int = 13,
) -> dict[str, Any]:
    """Forward along corridor then return — ground-truth revisit for loop closure."""
    rng = random.Random(seed)
    true_motors: list[Motor] = []
    est_motors: list[Motor] = []
    identity = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))
    true_acc = identity
    est_acc = identity
    true_motors.append(true_acc)
    est_motors.append(est_acc)

    def step_motor(acc: Motor, dx: float) -> Motor:
        delta = motor_from_axis_angle((0.0, 1.0, 0.0), 0.0, (dx, 0.0, 0.0))
        return compose_motors(delta, acc)

    for i in range(1, n_forward):
        true_acc = step_motor(true_acc, step_m)
        true_motors.append(true_acc)
        noisy_dx = step_m + rng.gauss(0.0, noise_sigma_m)
        est_acc = step_motor(est_acc, noisy_dx)
        est_motors.append(est_acc)

    for i in range(n_forward - 2, -1, -1):
        true_acc = step_motor(true_acc, -step_m)
        true_motors.append(true_acc)
        noisy_dx = -step_m + rng.gauss(0.0, noise_sigma_m)
        est_acc = step_motor(est_acc, noisy_dx)
        est_motors.append(est_acc)

    true_positions = [_motor_position(m) for m in true_motors]
    est_positions = [_motor_position(m) for m in est_motors]
    return {
        "true_motors": true_motors,
        "est_motors": est_motors,
        "true_positions": true_positions,
        "est_positions": est_positions,
        "points": points,
        "n_poses": len(true_motors),
    }


def detect_loop_candidate(positions: list[Vec3], *, current_idx: int) -> int | None:
    """Revisit: current pose in second half matches anchor in first quarter."""
    n = len(positions)
    if current_idx < n // 2:
        return None
    anchor_limit = max(int(n * ANCHOR_FRACTION), MIN_LOOP_INDEX_GAP)
    cur = positions[current_idx]
    best_i: int | None = None
    best_d = float("inf")
    for i in range(anchor_limit):
        if current_idx - i < MIN_LOOP_INDEX_GAP:
            continue
        d = _dist(cur, positions[i])
        if d < LOOP_DETECT_RADIUS_M and d < best_d:
            best_d = d
            best_i = i
    return best_i


def apply_loop_closure_positions(
    est_positions: list[Vec3],
    *,
    loop_from: int,
    loop_to: int,
) -> list[Vec3]:
    """Distribute loop constraint on positions (Phase A envelope — not full pose graph)."""
    close_err = (
        est_positions[loop_from][0] - est_positions[loop_to][0],
        est_positions[loop_from][1] - est_positions[loop_to][1],
        est_positions[loop_from][2] - est_positions[loop_to][2],
    )
    corrected = list(est_positions)
    span = max(loop_to - loop_from, 1)
    for j in range(loop_from, len(corrected)):
        alpha = (j - loop_from) / span
        x, y, z = corrected[j]
        corrected[j] = (
            x + close_err[0] * alpha,
            y + close_err[1] * alpha,
            z + close_err[2] * alpha,
        )
    return corrected


def trajectory_rmse(true_pos: list[Vec3], est_pos: list[Vec3]) -> float:
    return rmse_m(true_pos, est_pos)


def latency_ms_from_cycles(cycles: int, *, cpu_hz: int = CPU_HZ) -> float:
    return cycles / cpu_hz * 1000.0


def run_loop_closure_pipeline(
    points: list[Vec3],
    *,
    seed: int = 13,
) -> dict[str, Any]:
    traj = simulate_loop_trajectory(points, seed=seed)
    est_positions = list(traj["est_positions"])
    true_positions = traj["true_positions"]
    est_motors = list(traj["est_motors"])

    drift_before_m = trajectory_rmse(true_positions, est_positions)
    loop_gap_before_m = 0.0
    loop_gap_after_m = 0.0

    loop_to = len(est_positions) - 1
    loop_from = detect_loop_candidate(est_positions, current_idx=loop_to)

    closure_ms = 0.0
    loop_detected = loop_from is not None
    if loop_detected and loop_from is not None:
        loop_gap_before_m = _dist(est_positions[loop_to], est_positions[loop_from])
        search_cycles = (loop_to - loop_from) * CYCLES_PER_POSE_COMPARE
        closure_cycles = CYCLES_PER_CLOSURE_OPTIMIZE
        closure_ms = latency_ms_from_cycles(search_cycles + closure_cycles)
        est_positions = apply_loop_closure_positions(
            est_positions,
            loop_from=loop_from,
            loop_to=loop_to,
        )
        loop_gap_after_m = _dist(est_positions[loop_to], est_positions[loop_from])

    drift_after_m = trajectory_rmse(true_positions, est_positions)

    return {
        "n_poses": traj["n_poses"],
        "loop_detected": loop_detected,
        "loop_from_index": loop_from,
        "loop_to_index": loop_to if loop_detected else None,
        "loop_detect_radius_m": LOOP_DETECT_RADIUS_M,
        "loop_gap_before_m": round(loop_gap_before_m, 4),
        "loop_gap_after_m": round(loop_gap_after_m, 4),
        "drift_before_m": round(drift_before_m, 4),
        "drift_after_m": round(drift_after_m, 4),
        "drift_reduction_m": round(drift_before_m - drift_after_m, 4),
        "drift_falsifier_m": DRIFT_FALSIFIER_M,
        "closure_latency_ms": round(closure_ms, 4),
        "closure_budget_ms": CLOSURE_BUDGET_MS,
        "latency_model": {
            "cpu_hz": CPU_HZ,
            "cycles_per_pose_compare": CYCLES_PER_POSE_COMPARE,
            "cycles_per_closure_opt": CYCLES_PER_CLOSURE_OPTIMIZE,
            "oracle": "ENVELOPE_CYCLES",
            "tier": "L5 heavy async — not O(1) claim",
        },
    }
