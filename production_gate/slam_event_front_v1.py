"""L0–L1 event front sim — change events from cave motion (not RGB frames).

Traverse/warp uses SlamPose (P7.2 engine path) or opt-in DqPose (tier-D).
motor7 remains step delta + parity oracle.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Literal

from production_gate.slam_pga8_motion_v1 import SlamPose
from production_gate.slam_se3_motor_v1 import Motor, motor_from_axis_angle, rmse_m

ComposeTier = Literal["tier_c", "tier_d", "tier_d_cga32"]
DEFAULT_COMPOSE_TIER: ComposeTier = "tier_c"

CPU_HZ = 48_000_000
CYCLES_PER_PERCEPT_EVENT = 96  # TIER-J front teaching budget @ 48 MHz — ADAPT
CYCLES_PER_FEATURE_TICK = 320  # local feature / IMU merge — ADAPT
EVENT_THRESHOLD_M = 0.002
EVENT_RATE_FRAC = 0.08  # teaching: ~8% pixels fire per tick on motion — ADAPT
MIN_EVENTS_PER_TICK = 8
RGB_BYTES_PER_FRAME = 1920 * 1080 * 3  # 1080p RGB falsifier


@dataclass(frozen=True)
class PerceptEvent:
    point_idx: int
    delta_m: float
    tick: int


@dataclass(frozen=True)
class FeatureTick:
    tick: int
    event_count: int
    centroid: tuple[float, float, float]


def _step_motor(*, axis: tuple[float, float, float], angle_deg: float, t_m: tuple[float, float, float]) -> Motor:
    return motor_from_axis_angle(axis, math.radians(angle_deg), t_m)


def _traverse_frames_slam_pose(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int,
    step_m: float,
    yaw_deg: float = 0.2,
    reverse: bool = False,
) -> list[list[tuple[float, float, float]]]:
    """Accumulated SlamPose applied to landmark cloud (P7.2 engine semantics)."""
    sign = -1.0 if reverse else 1.0
    pose = SlamPose.identity()
    frames: list[list[tuple[float, float, float]]] = [pose.apply_points(points)]
    for _ in range(1, n_ticks):
        step = _step_motor(
            axis=(0.0, 1.0, 0.0),
            angle_deg=sign * yaw_deg,
            t_m=(sign * step_m, 0.0, 0.0),
        )
        pose = SlamPose.compose(step, pose)
        frames.append(pose.apply_points(points))
    return frames


def _traverse_frames_motor7(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int,
    step_m: float,
    yaw_deg: float = 0.2,
    reverse: bool = False,
) -> list[list[tuple[float, float, float]]]:
    """Legacy motor7 path — parity reference only."""
    sign = -1.0 if reverse else 1.0
    motor = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))
    frames: list[list[tuple[float, float, float]]] = [list(points)]
    for _ in range(1, n_ticks):
        step = _step_motor(
            axis=(0.0, 1.0, 0.0),
            angle_deg=sign * yaw_deg,
            t_m=(sign * step_m, 0.0, 0.0),
        )
        motor = _compose_motor7(step, motor)
        frames.append([motor.apply(p) for p in points])
    return frames


def _traverse_frames_dq_pose(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int,
    step_m: float,
    yaw_deg: float = 0.2,
    reverse: bool = False,
) -> list[list[tuple[float, float, float]]]:
    """Tier-D: DqPose single-motor compose (T5 phase-1 oracle path)."""
    from production_gate.slam_pose_dq_v1 import DqPose

    sign = -1.0 if reverse else 1.0
    pose = DqPose.identity()
    frames: list[list[tuple[float, float, float]]] = [pose.apply_points(points)]
    for _ in range(1, n_ticks):
        step = _step_motor(
            axis=(0.0, 1.0, 0.0),
            angle_deg=sign * yaw_deg,
            t_m=(sign * step_m, 0.0, 0.0),
        )
        pose = DqPose.compose(step, pose)
        frames.append(pose.apply_points(points))
    return frames


def _traverse_frames_cga32_pose(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int,
    step_m: float,
    yaw_deg: float = 0.2,
    reverse: bool = False,
) -> list[list[tuple[float, float, float]]]:
    """Tier-D CGA32: host cxx geo_prod on motor512 (phase-2 hot loop)."""
    from production_gate.slam_pose_cga32_v1 import Cga32Pose

    sign = -1.0 if reverse else 1.0
    pose = Cga32Pose.identity()
    frames: list[list[tuple[float, float, float]]] = [pose.apply_points(points)]
    for _ in range(1, n_ticks):
        step = _step_motor(
            axis=(0.0, 1.0, 0.0),
            angle_deg=sign * yaw_deg,
            t_m=(sign * step_m, 0.0, 0.0),
        )
        pose = Cga32Pose.compose(step, pose)
        frames.append(pose.apply_points(points))
    return frames


def _traverse_frames(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int,
    step_m: float,
    yaw_deg: float = 0.2,
    reverse: bool = False,
    compose_tier: ComposeTier = DEFAULT_COMPOSE_TIER,
) -> list[list[tuple[float, float, float]]]:
    if compose_tier == "tier_d_cga32":
        return _traverse_frames_cga32_pose(
            points, n_ticks=n_ticks, step_m=step_m, yaw_deg=yaw_deg, reverse=reverse
        )
    if compose_tier == "tier_d":
        return _traverse_frames_dq_pose(
            points, n_ticks=n_ticks, step_m=step_m, yaw_deg=yaw_deg, reverse=reverse
        )
    return _traverse_frames_slam_pose(
        points, n_ticks=n_ticks, step_m=step_m, yaw_deg=yaw_deg, reverse=reverse
    )


def traverse_tier_d_parity_rmse_m(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int = 24,
    step_m: float = 0.04,
) -> float:
    """Max per-frame RMSE: tier-D DqPose vs tier-C+ SlamPose on same steps."""
    a = _traverse_frames_dq_pose(points, n_ticks=n_ticks, step_m=step_m)
    b = _traverse_frames_slam_pose(points, n_ticks=n_ticks, step_m=step_m)
    worst = 0.0
    for fa, fb in zip(a, b):
        worst = max(worst, rmse_m(fa, fb))
    return worst


def traverse_engine_parity_rmse_m(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int = 24,
    step_m: float = 0.04,
) -> float:
    """Max per-frame RMSE: SlamPose traverse vs motor7 reference."""
    a = _traverse_frames_slam_pose(points, n_ticks=n_ticks, step_m=step_m)
    b = _traverse_frames_motor7(points, n_ticks=n_ticks, step_m=step_m)
    worst = 0.0
    for fa, fb in zip(a, b):
        worst = max(worst, rmse_m(fa, fb))
    return worst


def simulate_traverse_ticks(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int = 24,
    step_m: float = 0.04,
    compose_tier: ComposeTier = DEFAULT_COMPOSE_TIER,
) -> list[list[tuple[float, float, float]]]:
    """Rover corridor snapshots — default tier_c (SlamPose); opt-in tier_d."""
    return _traverse_frames(points, n_ticks=n_ticks, step_m=step_m, compose_tier=compose_tier)

def _compose_motor7(delta: Motor, acc: Motor) -> Motor:
    m4d = delta.as_matrix4()
    m4a = acc.as_matrix4()
    out = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            out[i][j] = sum(m4d[i][k] * m4a[k][j] for k in range(4))
    from production_gate.slam_se3_motor_v1 import motor_from_matrix4

    return motor_from_matrix4(out)


def traverse_loop_tier_d_parity_rmse_m(
    points: list[tuple[float, float, float]],
    *,
    n_forward: int = 14,
    step_m: float = 0.04,
) -> float:
    """L5 loop: tier-D DqPose vs tier-C SlamPose per-frame max RMSE."""
    a = simulate_loop_traverse_ticks(points, n_forward=n_forward, step_m=step_m, compose_tier="tier_d")
    b = simulate_loop_traverse_ticks(points, n_forward=n_forward, step_m=step_m, compose_tier="tier_c")
    worst = 0.0
    for fa, fb in zip(a, b):
        worst = max(worst, rmse_m(fa, fb))
    return worst


def simulate_loop_traverse_ticks(
    points: list[tuple[float, float, float]],
    *,
    n_forward: int = 14,
    step_m: float = 0.04,
    compose_tier: ComposeTier = DEFAULT_COMPOSE_TIER,
) -> list[list[tuple[float, float, float]]]:
    """Forward corridor traverse then return — L5 loop closure needs revisit."""
    if compose_tier == "tier_d_cga32":
        from production_gate.slam_pose_cga32_v1 import Cga32Pose

        pose = Cga32Pose.identity()
        frames: list[list[tuple[float, float, float]]] = [pose.apply_points(points)]
        for _ in range(1, n_forward):
            step = _step_motor(axis=(0.0, 1.0, 0.0), angle_deg=0.2, t_m=(step_m, 0.0, 0.0))
            pose = Cga32Pose.compose(step, pose)
            frames.append(pose.apply_points(points))
        for _ in range(n_forward - 1):
            step = _step_motor(axis=(0.0, 1.0, 0.0), angle_deg=-0.2, t_m=(-step_m, 0.0, 0.0))
            pose = Cga32Pose.compose(step, pose)
            frames.append(pose.apply_points(points))
        return frames

    if compose_tier == "tier_d":
        from production_gate.slam_pose_dq_v1 import DqPose

        pose = DqPose.identity()
        frames: list[list[tuple[float, float, float]]] = [pose.apply_points(points)]
        for _ in range(1, n_forward):
            step = _step_motor(axis=(0.0, 1.0, 0.0), angle_deg=0.2, t_m=(step_m, 0.0, 0.0))
            pose = DqPose.compose(step, pose)
            frames.append(pose.apply_points(points))
        for _ in range(n_forward - 1):
            step = _step_motor(axis=(0.0, 1.0, 0.0), angle_deg=-0.2, t_m=(-step_m, 0.0, 0.0))
            pose = DqPose.compose(step, pose)
            frames.append(pose.apply_points(points))
        return frames

    pose = SlamPose.identity()
    frames: list[list[tuple[float, float, float]]] = [pose.apply_points(points)]
    for _ in range(1, n_forward):
        step = _step_motor(axis=(0.0, 1.0, 0.0), angle_deg=0.2, t_m=(step_m, 0.0, 0.0))
        pose = SlamPose.compose(step, pose)
        frames.append(pose.apply_points(points))
    for _ in range(n_forward - 1):
        step = _step_motor(axis=(0.0, 1.0, 0.0), angle_deg=-0.2, t_m=(-step_m, 0.0, 0.0))
        pose = SlamPose.compose(step, pose)
        frames.append(pose.apply_points(points))
    return frames


def detect_percept_events(
    prev: list[tuple[float, float, float]],
    cur: list[tuple[float, float, float]],
    *,
    tick: int,
    threshold_m: float = EVENT_THRESHOLD_M,
    event_rate_frac: float = EVENT_RATE_FRAC,
) -> list[PerceptEvent]:
    """Motion change events — capped per tick to model event-camera sparsity."""
    candidates: list[PerceptEvent] = []
    for i, (a, b) in enumerate(zip(prev, cur)):
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d >= threshold_m:
            candidates.append(PerceptEvent(point_idx=i, delta_m=round(d, 6), tick=tick))
    if not candidates:
        return []
    cap = max(MIN_EVENTS_PER_TICK, int(len(prev) * event_rate_frac))
    candidates.sort(key=lambda e: (-e.delta_m, e.point_idx))
    return candidates[:cap]


def feature_tick_from_events(events: list[PerceptEvent], points: list[tuple[float, float, float]], tick: int) -> FeatureTick | None:
    if not events:
        return None
    xs = [points[e.point_idx][0] for e in events]
    ys = [points[e.point_idx][1] for e in events]
    zs = [points[e.point_idx][2] for e in events]
    n = float(len(xs))
    return FeatureTick(
        tick=tick,
        event_count=len(events),
        centroid=(sum(xs) / n, sum(ys) / n, sum(zs) / n),
    )


def latency_us_from_cycles(cycles: int, *, cpu_hz: int = CPU_HZ) -> float:
    return cycles / cpu_hz * 1e6


def run_event_front_pipeline(
    points: list[tuple[float, float, float]],
    *,
    n_ticks: int = 24,
    compose_tier: ComposeTier = DEFAULT_COMPOSE_TIER,
) -> dict[str, Any]:
    frames = simulate_traverse_ticks(points, n_ticks=n_ticks, compose_tier=compose_tier)
    all_events: list[PerceptEvent] = []
    feature_ticks: list[FeatureTick] = []
    percept_latencies_us: list[float] = []
    feature_latencies_us: list[float] = []

    for tick in range(1, len(frames)):
        events = detect_percept_events(frames[tick - 1], frames[tick], tick=tick)
        all_events.extend(events)
        for _ in events:
            percept_latencies_us.append(latency_us_from_cycles(CYCLES_PER_PERCEPT_EVENT))
        ft = feature_tick_from_events(events, frames[tick], tick)
        if ft is not None:
            feature_ticks.append(ft)
            feature_latencies_us.append(latency_us_from_cycles(CYCLES_PER_FEATURE_TICK))

    n_points = len(points)
    total_point_observations = n_points * (len(frames) - 1)
    event_count = len(all_events)
    sparsity_fraction = 1.0 - (event_count / total_point_observations if total_point_observations else 1.0)
    bytes_per_rgb_frame = RGB_BYTES_PER_FRAME
    event_bytes_per_tick = 8  # compact event packet teaching
    avg_events_per_tick = event_count / max(len(frames) - 1, 1)
    bytes_event_stream = int(avg_events_per_tick * event_bytes_per_tick)

    def p95(vals: list[float]) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        return s[int(0.95 * (len(s) - 1))]

    return {
        "n_ticks": len(frames) - 1,
        "n_points": n_points,
        "event_count": event_count,
        "sparsity_fraction": round(sparsity_fraction, 6),
        "event_rate_frac_model": EVENT_RATE_FRAC,
        "avg_events_per_tick": round(avg_events_per_tick, 4),
        "percept_latency_us_p95": round(p95(percept_latencies_us), 4),
        "feature_latency_us_p95": round(p95(feature_latencies_us), 4),
        "percept_budget_us": 10.0,
        "feature_budget_us": 50.0,
        "comm_reduction": {
            "rgb_bytes_per_frame": bytes_per_rgb_frame,
            "event_bytes_per_tick_avg": bytes_event_stream,
            "reduction_factor": round(bytes_per_rgb_frame / max(bytes_event_stream, 1), 1),
        },
        "latency_model": {
            "cpu_hz": CPU_HZ,
            "cycles_per_percept": CYCLES_PER_PERCEPT_EVENT,
            "cycles_per_feature": CYCLES_PER_FEATURE_TICK,
            "oracle": "ENVELOPE_CYCLES",
        },
        "compose_tier": compose_tier,
    }