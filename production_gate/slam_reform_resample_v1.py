"""REFORM resample/match loop — fixed cave dataset + iterative ICP falsifier (stdlib)."""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

from production_gate.slam_pga_primitives_v1 import (
    Plane,
    register_planes_primitive,
    register_points_kabsch,
    register_reform_r0_two_stage,
    synthetic_cave_corridor,
)
from production_gate.slam_se3_motor_v1 import Motor, compose_motors, motor_from_axis_angle, rmse_m

_REPO = Path(__file__).resolve().parents[1]
_DATASET = _REPO / "fixtures" / "slam" / "cave_corridor_dataset_v1.json"


def _motor_identity() -> Motor:
    return motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))


def _add_noise(points: list[tuple[float, float, float]], sigma: float, rng: random.Random):
    return [
        (
            p[0] + rng.gauss(0, sigma),
            p[1] + rng.gauss(0, sigma),
            p[2] + rng.gauss(0, sigma),
        )
        for p in points
    ]


def build_fixed_dataset(*, seed: int = 7, noise_sigma_m: float = 0.015) -> dict[str, Any]:
    rng = random.Random(seed)
    scene = synthetic_cave_corridor(rng=rng)
    true_motor = motor_from_axis_angle(
        (0.1, 0.05, 1.0),
        math.radians(18.0),
        (1.2, 0.4, 0.15),
    )

    def xform_planes(motor: Motor, planes: list[Plane]) -> list[Plane]:
        out: list[Plane] = []
        m = motor.as_matrix4()
        for pl in planes:
            p0 = (-pl.d * pl.nx, -pl.d * pl.ny, -pl.d * pl.nz)
            p0t = motor.apply(p0)
            x, y, z = pl.nx, pl.ny, pl.nz
            rx = m[0][0] * x + m[0][1] * y + m[0][2] * z
            ry = m[1][0] * x + m[1][1] * y + m[1][2] * z
            rz = m[2][0] * x + m[2][1] * y + m[2][2] * z
            ln = math.sqrt(rx * rx + ry * ry + rz * rz)
            nx, ny, nz = rx / ln, ry / ln, rz / ln
            d = -(nx * p0t[0] + ny * p0t[1] + nz * p0t[2])
            out.append(Plane(nx, ny, nz, d, pl.label))
        return out

    src_planes = scene["planes"]
    src_points = scene["points"]
    dst_planes = xform_planes(true_motor, src_planes)
    dst_points_clean = [true_motor.apply(p) for p in src_points]
    dst_points = _add_noise(dst_points_clean, noise_sigma_m, rng)

    return {
        "dataset_id": "cave_corridor_dataset_v1",
        "seed": seed,
        "noise_sigma_m": noise_sigma_m,
        "scene_id": scene["scene_id"],
        "true_motor": {
            "qw": true_motor.qw,
            "qx": true_motor.qx,
            "qy": true_motor.qy,
            "qz": true_motor.qz,
            "tx": true_motor.tx,
            "ty": true_motor.ty,
            "tz": true_motor.tz,
        },
        "src_planes": [
            {"nx": p.nx, "ny": p.ny, "nz": p.nz, "d": p.d, "label": p.label} for p in src_planes
        ],
        "dst_planes": [
            {"nx": p.nx, "ny": p.ny, "nz": p.nz, "d": p.d, "label": p.label} for p in dst_planes
        ],
        "src_points": src_points,
        "dst_points": dst_points,
        "point_count": len(src_points),
    }


def load_or_build_dataset(*, write_fixture: bool = False) -> dict[str, Any]:
    if _DATASET.is_file():
        return json.loads(_DATASET.read_text(encoding="utf-8"))
    data = build_fixed_dataset()
    if write_fixture:
        _DATASET.parent.mkdir(parents=True, exist_ok=True)
        _DATASET.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def _planes_from_dict(rows: list[dict[str, Any]]) -> list[Plane]:
    return [Plane(r["nx"], r["ny"], r["nz"], r["d"], r["label"]) for r in rows]


def reform_resample_loop(
    src_planes: list[Plane],
    dst_planes: list[Plane],
    src_points: list[tuple[float, float, float]],
    dst_points: list[tuple[float, float, float]],
    *,
    n_iterations: int = 6,
    sample_size: int = 48,
    seed: int = 11,
) -> tuple[Motor, list[float]]:
    """Resample subsets → plane-first coarse → point refine; compose deltas."""
    rng = random.Random(seed)
    motor = _motor_identity()
    warped = list(src_points)
    rmse_trace: list[float] = []

    for it in range(n_iterations):
        idx = rng.sample(range(len(warped)), min(sample_size, len(warped)))
        sub_src = [warped[i] for i in idx]
        sub_dst = [dst_points[i] for i in idx]
        if it == 0:
            _, delta, _ = register_reform_r0_two_stage(
                src_planes, dst_planes, sub_src, sub_dst
            )
        else:
            delta = register_points_kabsch(sub_src, sub_dst)
        motor = compose_motors(delta, motor)
        warped = [motor.apply(p) for p in src_points]
        rmse_trace.append(rmse_m(warped, dst_points))

    return motor, rmse_trace


def icp_iterative_baseline(
    src_points: list[tuple[float, float, float]],
    dst_points: list[tuple[float, float, float]],
    *,
    n_iterations: int = 8,
) -> tuple[Motor, list[float]]:
    """OpenCV-class iterative point ICP proxy (Kabsch iterations)."""
    motor = _motor_identity()
    warped = list(src_points)
    rmse_trace: list[float] = []
    for _ in range(n_iterations):
        delta = register_points_kabsch(warped, dst_points)
        motor = compose_motors(delta, motor)
        warped = [motor.apply(p) for p in src_points]
        rmse_trace.append(rmse_m(warped, dst_points))
    return motor, rmse_trace


def reform_resample_loop_pga8(
    src_planes: list[Plane],
    dst_planes: list[Plane],
    src_points: list[tuple[float, float, float]],
    dst_points: list[tuple[float, float, float]],
    *,
    n_iterations: int = 6,
    sample_size: int = 48,
    seed: int = 11,
) -> tuple[Motor, list[float], list[float]]:
    """Same algorithm as reform_resample_loop — warp/compose via SlamPose (PGA8 engine)."""
    from production_gate.slam_pga8_motion_v1 import SlamPose

    rng = random.Random(seed)
    pose = SlamPose.identity()
    warped = list(src_points)
    rmse_trace: list[float] = []
    apply_parity_trace: list[float] = []

    for it in range(n_iterations):
        idx = rng.sample(range(len(warped)), min(sample_size, len(warped)))
        sub_src = [warped[i] for i in idx]
        sub_dst = [dst_points[i] for i in idx]
        if it == 0:
            _, delta, _ = register_reform_r0_two_stage(
                src_planes, dst_planes, sub_src, sub_dst
            )
        else:
            delta = register_points_kabsch(sub_src, sub_dst)
        pose = SlamPose.compose(delta, pose)
        apply_parity_trace.append(pose.rmse_vs_motor7(src_points[: min(32, len(src_points))]))
        warped = pose.apply_points(src_points)
        rmse_trace.append(rmse_m(warped, dst_points))

    return pose.to_motor7(), rmse_trace, apply_parity_trace


def run_registration_benchmark_pga8(dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    """Matrix motor7 vs PGA8 SlamPose paths on the same fixed dataset."""
    data = dataset or load_or_build_dataset(write_fixture=True)
    src_planes = _planes_from_dict(data["src_planes"])
    dst_planes = _planes_from_dict(data["dst_planes"])
    src_points = [tuple(p) for p in data["src_points"]]
    dst_points = [tuple(p) for p in data["dst_points"]]

    reform_motor, reform_trace = reform_resample_loop(
        src_planes, dst_planes, src_points, dst_points
    )
    pga_motor, pga_trace, parity_trace = reform_resample_loop_pga8(
        src_planes, dst_planes, src_points, dst_points
    )

    reform_rmse = rmse_m([reform_motor.apply(p) for p in src_points], dst_points)
    pga_rmse = rmse_m([pga_motor.apply(p) for p in src_points], dst_points)
    path_delta = abs(reform_rmse - pga_rmse)
    max_parity = max(parity_trace) if parity_trace else 0.0

    icp_motor, icp_trace = icp_iterative_baseline(src_points, dst_points)
    icp_rmse = rmse_m([icp_motor.apply(p) for p in src_points], dst_points)

    return {
        "dataset_id": data["dataset_id"],
        "noise_sigma_m": data["noise_sigma_m"],
        "matrix_path": {
            "rmse_m": round(reform_rmse, 6),
            "rmse_trace": [round(x, 6) for x in reform_trace],
        },
        "pga8_engine_path": {
            "rmse_m": round(pga_rmse, 6),
            "rmse_trace": [round(x, 6) for x in pga_trace],
            "apply_parity_rmse_max_m": round(max_parity, 6),
            "path_delta_vs_matrix_m": round(path_delta, 6),
        },
        "icp_iterative_proxy": {
            "rmse_m": round(icp_rmse, 6),
            "rmse_trace": [round(x, 6) for x in icp_trace],
        },
        "pga8_matches_matrix": path_delta < 0.005,
        "pga8_reform_beats_or_matches_icp": pga_rmse <= icp_rmse * 1.05 + 1e-6,
        "matrix_reform_beats_or_matches_icp": reform_rmse <= icp_rmse * 1.05 + 1e-6,
    }


def run_registration_benchmark(dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dataset or load_or_build_dataset(write_fixture=True)
    src_planes = _planes_from_dict(data["src_planes"])
    dst_planes = _planes_from_dict(data["dst_planes"])
    src_points = [tuple(p) for p in data["src_points"]]
    dst_points = [tuple(p) for p in data["dst_points"]]

    reform_motor, reform_trace = reform_resample_loop(
        src_planes, dst_planes, src_points, dst_points
    )
    icp_motor, icp_trace = icp_iterative_baseline(src_points, dst_points)

    reform_rmse = rmse_m([reform_motor.apply(p) for p in src_points], dst_points)
    icp_rmse = rmse_m([icp_motor.apply(p) for p in src_points], dst_points)

    return {
        "dataset_id": data["dataset_id"],
        "noise_sigma_m": data["noise_sigma_m"],
        "reform_resample": {
            "rmse_m": round(reform_rmse, 6),
            "rmse_trace": [round(x, 6) for x in reform_trace],
            "final_iter_rmse": round(reform_trace[-1], 6) if reform_trace else None,
        },
        "icp_iterative_proxy": {
            "rmse_m": round(icp_rmse, 6),
            "rmse_trace": [round(x, 6) for x in icp_trace],
            "opencv_falsifier_label": "iterative point Kabsch — OpenCV ICP class proxy",
        },
        "reform_beats_or_matches_icp": reform_rmse <= icp_rmse * 1.05 + 1e-6,
        "monotonic_last_step": len(reform_trace) >= 2 and reform_trace[-1] <= reform_trace[0],
    }
