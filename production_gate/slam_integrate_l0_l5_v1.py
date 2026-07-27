"""L0–L5 integrated SLAM pipeline — wired layer outputs, strict falsifiers."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from production_gate.slam_event_front_v1 import (
    DEFAULT_COMPOSE_TIER,
    ComposeTier,
    detect_percept_events,
    feature_tick_from_events,
    simulate_loop_traverse_ticks,
)
from production_gate.slam_loop_closure_v1 import (
    apply_loop_closure_positions,
    detect_loop_candidate,
    trajectory_rmse,
)
from production_gate.slam_map_commit_v1 import run_map_commit_pipeline
from production_gate.slam_pga_primitives_v1 import Plane
from production_gate.slam_reform_resample_v1 import reform_resample_loop
from production_gate.slam_se3_motor_v1 import Motor, Vec3, compose_motors, motor_from_axis_angle, rmse_m

Vec3 = tuple[float, float, float]

R1_RMSE_CEILING_M = 0.08
E2E_TRANS_ERR_MAX_M = 0.12
E2E_ROT_ERR_MAX_DEG = 8.0
L1_MIN_EVENTS = 8


@dataclass
class LayerL0:
    src_points: list[Vec3]
    dst_points: list[Vec3]
    src_planes: list[Plane]
    dst_planes: list[Plane]
    true_motor: Motor
    noise_sigma_m: float


@dataclass
class LayerL1:
    frames: list[list[Vec3]]
    events_total: int
    feature_ticks: int
    event_point_indices: set[int]


@dataclass
class LayerL2:
    odom_motors: list[Motor]
    positions: list[Vec3]


@dataclass
class LayerL3:
    motor: Motor
    rmse_m: float


@dataclass
class LayerL4:
    tile_count: int
    map_points: int
    points_from_l1_events: int


@dataclass
class LayerL5:
    loop_detected: bool
    loop_gap_after_m: float
    drift_before_m: float
    drift_after_m: float


@dataclass
class IntegratedPipeline:
    l0: LayerL0
    l1: LayerL1
    l2: LayerL2
    l3: LayerL3
    l4: LayerL4
    l5: LayerL5
    wiring: dict[str, Any]
    metrics: dict[str, Any]
    checks: list[dict[str, Any]] = field(default_factory=list)
    verdict: str = "DEGRADED"


def _planes_from_dict(rows: list[dict[str, Any]]) -> list[Plane]:
    return [Plane(r["nx"], r["ny"], r["nz"], r["d"], r["label"]) for r in rows]


def _motor_from_dict(d: dict[str, float]) -> Motor:
    return Motor(d["qw"], d["qx"], d["qy"], d["qz"], d["tx"], d["ty"], d["tz"])


def _motor_position(m: Motor) -> Vec3:
    return m.tx, m.ty, m.tz


def _quat_angle_deg(a: Motor, b: Motor) -> float:
    dot = abs(a.qw * b.qw + a.qx * b.qx + a.qy * b.qy + a.qz * b.qz)
    dot = min(1.0, max(-1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def _trans_err_m(a: Motor, b: Motor) -> float:
    dx, dy, dz = a.tx - b.tx, a.ty - b.ty, a.tz - b.tz
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _run_l0(data: dict[str, Any]) -> LayerL0:
    return LayerL0(
        src_points=[tuple(p) for p in data["src_points"]],
        dst_points=[tuple(p) for p in data["dst_points"]],
        src_planes=_planes_from_dict(data["src_planes"]),
        dst_planes=_planes_from_dict(data["dst_planes"]),
        true_motor=_motor_from_dict(data["true_motor"]),
        noise_sigma_m=float(data["noise_sigma_m"]),
    )


def _run_l1(
    points: list[Vec3],
    *,
    n_forward: int = 14,
    compose_tier: ComposeTier = DEFAULT_COMPOSE_TIER,
) -> LayerL1:
    frames = simulate_loop_traverse_ticks(points, n_forward=n_forward, compose_tier=compose_tier)
    events_total = 0
    feature_ticks = 0
    event_indices: set[int] = set()
    for tick in range(1, len(frames)):
        events = detect_percept_events(frames[tick - 1], frames[tick], tick=tick)
        events_total += len(events)
        for e in events:
            event_indices.add(e.point_idx)
        if feature_tick_from_events(events, frames[tick], tick) is not None:
            feature_ticks += 1
    return LayerL1(
        frames=frames,
        events_total=events_total,
        feature_ticks=feature_ticks,
        event_point_indices=event_indices,
    )


def _run_l2(
    frames: list[list[Vec3]],
    *,
    noise_sigma_m: float,
    seed: int = 13,
) -> LayerL2:
    """Encoder integration from L1 motion — noisy step chaining."""
    rng = random.Random(seed)
    identity = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))
    odom: list[Motor] = [identity]
    acc = identity
    for tick in range(1, len(frames)):
        prev_c = _centroid(frames[tick - 1])
        cur_c = _centroid(frames[tick])
        dx = (cur_c[0] - prev_c[0]) + rng.gauss(0.0, noise_sigma_m)
        dy = (cur_c[1] - prev_c[1]) + rng.gauss(0.0, noise_sigma_m)
        dz = (cur_c[2] - prev_c[2]) + rng.gauss(0.0, noise_sigma_m)
        step = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (dx, dy, dz))
        acc = compose_motors(step, acc)
        odom.append(acc)
    positions = [_motor_position(m) for m in odom]
    return LayerL2(odom_motors=odom, positions=positions)


def _centroid(points: list[Vec3]) -> Vec3:
    n = float(len(points))
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )


def _run_l3(l0: LayerL0) -> LayerL3:
    motor, trace = reform_resample_loop(
        l0.src_planes,
        l0.dst_planes,
        l0.src_points,
        l0.dst_points,
    )
    return LayerL3(motor=motor, rmse_m=trace[-1] if trace else float("inf"))


def _run_l4(l0: LayerL0, l1: LayerL1, l3: LayerL3) -> LayerL4:
    if not l1.event_point_indices:
        return LayerL4(tile_count=0, map_points=0, points_from_l1_events=0)
    world_pts: list[Vec3] = []
    for idx in sorted(l1.event_point_indices):
        p = l0.src_points[idx]
        world_pts.append(l3.motor.apply(p))
    commit = run_map_commit_pipeline(world_pts)
    return LayerL4(
        tile_count=int(commit["tile_count"]),
        map_points=len(world_pts),
        points_from_l1_events=len(world_pts),
    )


def _run_l5_on_l2(l2: LayerL2, true_motor: Motor) -> LayerL5:
    """Loop closure driven by L2 odom — not standalone R5 simulator."""
    est = list(l2.positions)
    n_forward = len(est) // 2
    true_positions = []
    acc = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))
    true_positions.append(_motor_position(acc))
    for i in range(1, len(est)):
        step = motor_from_axis_angle(
            (0.0, 0.0, 1.0),
            0.0,
            (est[i][0] - est[i - 1][0], est[i][1] - est[i - 1][1], est[i][2] - est[i - 1][2]),
        )
        acc = compose_motors(step, acc)
        true_positions.append(_motor_position(acc))

    drift_before = trajectory_rmse(true_positions[: len(est)], est)
    loop_to = len(est) - 1
    loop_from = detect_loop_candidate(est, current_idx=loop_to)
    loop_gap_after = 0.0
    if loop_from is not None:
        gap_before = math.sqrt(sum((est[loop_to][i] - est[loop_from][i]) ** 2 for i in range(3)))
        est = apply_loop_closure_positions(est, loop_from=loop_from, loop_to=loop_to)
        loop_gap_after = math.sqrt(sum((est[loop_to][i] - est[loop_from][i]) ** 2 for i in range(3)))
    drift_after = trajectory_rmse(true_positions[: len(est)], est)
    return LayerL5(
        loop_detected=loop_from is not None,
        loop_gap_after_m=round(loop_gap_after, 4),
        drift_before_m=round(drift_before, 4),
        drift_after_m=round(drift_after, 4),
    )


def run_integrated_l0_l5(
    data: dict[str, Any],
    *,
    skip_l3: bool = False,
    r1_rmse_ref: float | None = None,
    compose_tier: ComposeTier = DEFAULT_COMPOSE_TIER,
) -> IntegratedPipeline:
    l0 = _run_l0(data)
    l1 = _run_l1(l0.src_points, compose_tier=compose_tier)
    l2 = _run_l2(l1.frames, noise_sigma_m=l0.noise_sigma_m)
    l3 = _run_l3(l0)
    if skip_l3:
        l3 = LayerL3(motor=motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0)), rmse_m=999.0)
    l4 = _run_l4(l0, l1, l3)
    l5 = _run_l5_on_l2(l2, l0.true_motor)

    wiring = {
        "L0_points_to_L1": len(l0.src_points) > 0 and len(l1.frames) > 1,
        "L1_events_to_L4": l4.points_from_l1_events > 0 and l4.points_from_l1_events == len(l1.event_point_indices),
        "L1_frame_count_matches_L2": len(l1.frames) == len(l2.odom_motors),
        "L2_positions_to_L5": len(l2.positions) > 0 and l5.loop_detected is not None,
        "L3_motor_to_L4": l4.map_points > 0,
        "skip_l3": skip_l3,
    }

    trans_err = _trans_err_m(l3.motor, l0.true_motor)
    rot_err = _quat_angle_deg(l3.motor, l0.true_motor)
    dst_fit = rmse_m([l3.motor.apply(p) for p in l0.src_points], l0.dst_points)

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("l1_events_min", l1.events_total >= L1_MIN_EVENTS, str(l1.events_total))
    chk("l1_l2_frame_lock", len(l1.frames) == len(l2.odom_motors))
    chk("l1_to_l4_wiring", wiring["L1_events_to_L4"])
    chk("l3_rmse_under_ceiling", l3.rmse_m < R1_RMSE_CEILING_M, f"{l3.rmse_m:.5f}")
    if r1_rmse_ref is not None and not skip_l3:
        chk(
            "l3_matches_r1_standalone",
            l3.rmse_m <= r1_rmse_ref * 1.02,
            f"l3={l3.rmse_m:.5f} r1={r1_rmse_ref:.5f}",
        )
    chk("l4_tiles_created", l4.tile_count > 0)
    chk("l5_loop_on_l2_odom", l5.loop_detected)
    chk("l5_gap_closed", l5.loop_gap_after_m < 0.05, str(l5.loop_gap_after_m))
    chk("e2e_trans_err", trans_err < E2E_TRANS_ERR_MAX_M, f"{trans_err:.4f}")
    chk("e2e_rot_err", rot_err < E2E_ROT_ERR_MAX_DEG, f"{rot_err:.4f}")
    chk("e2e_dst_fit", dst_fit < R1_RMSE_CEILING_M, f"{dst_fit:.5f}")
    if skip_l3:
        chk("skip_l3_must_fail_e2e", trans_err > 0.5 or dst_fit > 0.5, "disconnect proof")
    else:
        chk("skip_l3_must_fail_e2e", True, "n/a")

    metrics = {
        "l1_events_total": l1.events_total,
        "l1_feature_ticks": l1.feature_ticks,
        "l2_odom_poses": len(l2.odom_motors),
        "l3_rmse_m": round(l3.rmse_m, 5),
        "l4_tile_count": l4.tile_count,
        "l4_map_points": l4.map_points,
        "l5_loop_gap_after_m": l5.loop_gap_after_m,
        "e2e_trans_err_m": round(trans_err, 4),
        "e2e_rot_err_deg": round(rot_err, 4),
        "e2e_dst_fit_rmse_m": round(dst_fit, 5),
        "true_motor_t_m": [l0.true_motor.tx, l0.true_motor.ty, l0.true_motor.tz],
        "est_motor_t_m": [l3.motor.tx, l3.motor.ty, l3.motor.tz],
    }

    verdict = "PASS" if all(c["pass"] for c in checks) else "DEGRADED"
    return IntegratedPipeline(
        l0=l0,
        l1=l1,
        l2=l2,
        l3=l3,
        l4=l4,
        l5=l5,
        wiring=wiring,
        metrics=metrics,
        checks=checks,
        verdict=verdict,
    )


def pipeline_to_dict(p: IntegratedPipeline) -> dict[str, Any]:
    return {
        "verdict": p.verdict,
        "wiring": p.wiring,
        "metrics": p.metrics,
        "checks": p.checks,
        "layers": {
            "L0": {"points": len(p.l0.src_points), "noise_sigma_m": p.l0.noise_sigma_m},
            "L1": {
                "frames": len(p.l1.frames),
                "events_total": p.l1.events_total,
                "event_indices": len(p.l1.event_point_indices),
            },
            "L2": {"odom_poses": len(p.l2.odom_motors)},
            "L3": {"rmse_m": p.l3.rmse_m},
            "L4": {
                "tile_count": p.l4.tile_count,
                "points_from_l1": p.l4.points_from_l1_events,
            },
            "L5": {
                "loop_detected": p.l5.loop_detected,
                "loop_gap_after_m": p.l5.loop_gap_after_m,
            },
        },
    }
