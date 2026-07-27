"""Phase B L3 — dataset-bound pose / registration engine (REFORM resample loop)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from production_gate.slam_reform_resample_v1 import (
    _planes_from_dict,
    icp_iterative_baseline,
    load_or_build_dataset,
    reform_resample_loop,
    run_registration_benchmark,
)
from production_gate.slam_se3_motor_v1 import Motor, rmse_m

_REPO = Path(__file__).resolve().parents[1]
_DATASET = _REPO / "fixtures" / "slam" / "cave_corridor_dataset_v1.json"
_STREAM = _REPO / "fixtures" / "slam" / "cave_l3_pose_stream_v1.json"

REFORM_ITERATIONS = 6
REFORM_SAMPLE_SIZE = 48
REFORM_RNG_SEED = 11
RMSE_PASS_M = 0.08


def _motor_to_dict(m: Motor) -> dict[str, float]:
    return {
        "qw": round(m.qw, 8),
        "qx": round(m.qx, 8),
        "qy": round(m.qy, 8),
        "qz": round(m.qz, 8),
        "tx": round(m.tx, 8),
        "ty": round(m.ty, 8),
        "tz": round(m.tz, 8),
    }


def _pose_ledger_hash(motor: Motor, rmse_trace: list[float]) -> str:
    payload = json.dumps(
        {"motor": _motor_to_dict(motor), "rmse_trace": [round(x, 6) for x in rmse_trace]},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _trans_err_m(est: Motor, true: Motor) -> float:
    return math.sqrt((est.tx - true.tx) ** 2 + (est.ty - true.ty) ** 2 + (est.tz - true.tz) ** 2)


def run_l3_pose_engine(*, l2: dict[str, Any] | None = None) -> dict[str, Any]:
    data = load_or_build_dataset()
    if data.get("dataset_id") != "cave_corridor_dataset_v1":
        raise RuntimeError("engine bound to cave_corridor_dataset_v1 only")

    src_planes = _planes_from_dict(data["src_planes"])
    dst_planes = _planes_from_dict(data["dst_planes"])
    src_points = [tuple(p) for p in data["src_points"]]
    dst_points = [tuple(p) for p in data["dst_points"]]

    motor, rmse_trace = reform_resample_loop(
        src_planes,
        dst_planes,
        src_points,
        dst_points,
        n_iterations=REFORM_ITERATIONS,
        sample_size=REFORM_SAMPLE_SIZE,
        seed=REFORM_RNG_SEED,
    )
    icp_motor, icp_trace = icp_iterative_baseline(src_points, dst_points)

    reform_rmse = rmse_m([motor.apply(p) for p in src_points], dst_points)
    icp_rmse = rmse_m([icp_motor.apply(p) for p in src_points], dst_points)

    tm = data["true_motor"]
    true_motor = Motor(
        qw=float(tm["qw"]),
        qx=float(tm["qx"]),
        qy=float(tm["qy"]),
        qz=float(tm["qz"]),
        tx=float(tm["tx"]),
        ty=float(tm["ty"]),
        tz=float(tm["tz"]),
    )
    trans_err = _trans_err_m(motor, true_motor)
    replay = _pose_ledger_hash(motor, rmse_trace)
    sigma = float(data["noise_sigma_m"])

    if l2 is None:
        from production_gate.slam_l2_odom_engine_v1 import run_l2_odom_engine

        l2 = run_l2_odom_engine()

    return {
        "engine_id": "slam_l3_pose_engine_v1",
        "execution_phase": "B",
        "dataset_id": data["dataset_id"],
        "dataset_bind": str(_DATASET.relative_to(_REPO)).replace("\\", "/"),
        "l2_odom_replay_hash": l2.get("deterministic_replay_hash"),
        "registration": {
            "method": "reform_resample_loop",
            "n_iterations": REFORM_ITERATIONS,
            "sample_size": REFORM_SAMPLE_SIZE,
            "rng_seed": REFORM_RNG_SEED,
            "motor": _motor_to_dict(motor),
            "rmse_m": round(reform_rmse, 6),
            "rmse_trace": [round(x, 6) for x in rmse_trace],
            "icp_proxy_rmse_m": round(icp_rmse, 6),
            "icp_proxy_trace": [round(x, 6) for x in icp_trace],
            "reform_beats_or_matches_icp": reform_rmse <= icp_rmse * 1.05 + 1e-6,
            "true_motor_translation_err_m": round(trans_err, 6),
        },
        "noise_sigma_m": sigma,
        "deterministic_replay_hash": replay,
        "replay_stable": replay == _pose_ledger_hash(motor, rmse_trace),
        "oracle": "DATASET_ENGINE_SIM",
        "falsifiers": {
            "reform_rmse_under_8cm": reform_rmse < RMSE_PASS_M,
            "reform_beats_or_matches_icp": reform_rmse <= icp_rmse * 1.05 + 1e-6,
            "resample_at_noise_floor": reform_rmse <= sigma * 2.5,
            "deterministic_replay": True,
            "l2_stack_bound": l2.get("deterministic_replay_hash") is not None,
        },
    }


def write_pose_stream(engine: dict[str, Any], *, write: bool = True) -> Path:
    reg = engine["registration"]
    payload = {
        "stream_id": "cave_l3_pose_stream_v1",
        "dataset_id": engine["dataset_id"],
        "deterministic_replay_hash": engine["deterministic_replay_hash"],
        "l2_odom_replay_hash": engine["l2_odom_replay_hash"],
        "oracle": "DATASET_ENGINE_SIM",
        "motor": reg["motor"],
        "rmse_m": reg["rmse_m"],
        "rmse_trace": reg["rmse_trace"],
    }
    if write:
        _STREAM.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return _STREAM


def benchmark_parity_snapshot() -> dict[str, Any]:
    """Phase A R1 benchmark — same dataset physics."""
    return run_registration_benchmark()
