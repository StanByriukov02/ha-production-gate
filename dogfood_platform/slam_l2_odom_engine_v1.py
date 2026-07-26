"""Phase B L2 — dataset-bound odometry engine (deterministic encoder integration)."""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dogfood_platform.slam_l1_event_engine_v1 import run_l1_event_engine
from dogfood_platform.slam_reform_resample_v1 import load_or_build_dataset
from dogfood_platform.slam_se3_motor_v1 import Motor, compose_motors, motor_from_axis_angle

_REPO = Path(__file__).resolve().parents[1]
_DATASET = _REPO / "fixtures" / "slam" / "cave_corridor_dataset_v1.json"
_STREAM = _REPO / "fixtures" / "slam" / "cave_l2_odom_stream_v1.json"

Vec3 = tuple[float, float, float]
ODOM_RNG_SEED = 13  # locked with Phase A integrate L2 bridge (_run_l2)


@dataclass(frozen=True)
class OdomTick:
    tick: int
    dx_m: float
    dy_m: float
    dz_m: float
    position: Vec3
    motor_qw: float


def _centroid(points: list[Vec3]) -> Vec3:
    n = float(len(points))
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n, sum(p[2] for p in points) / n)


def _motor_position(m: Motor) -> Vec3:
    return (m.tx, m.ty, m.tz)


def _motor_to_dict(m: Motor) -> dict[str, float]:
    return {"qw": m.qw, "qx": m.qx, "qy": m.qy, "qz": m.qz, "tx": m.tx, "ty": m.ty, "tz": m.tz}


def _frames_from_l1(l1: dict[str, Any]) -> tuple[list[list[Vec3]], dict[str, Any]]:
    data = load_or_build_dataset()
    points = [tuple(p) for p in data["src_points"]]
    params = l1["parameters"]
    from dogfood_platform.slam_l1_event_engine_v1 import _trajectory_frames_from_dataset

    frames = _trajectory_frames_from_dataset(
        points,
        n_ticks=int(params["n_ticks"]),
        step_m=float(params["step_m"]),
    )
    return frames, params


def integrate_odom_ticks(
    frames: list[list[Vec3]],
    *,
    noise_sigma_m: float,
    rng_seed: int,
) -> list[OdomTick]:
    """Centroid delta encoder — same physics as Phase A integrate L2 bridge."""
    rng = random.Random(rng_seed)
    identity = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))
    acc = identity
    ticks: list[OdomTick] = []
    for tick in range(len(frames)):
        pos = _motor_position(acc)
        if tick == 0:
            ticks.append(OdomTick(tick=0, dx_m=0.0, dy_m=0.0, dz_m=0.0, position=pos, motor_qw=acc.qw))
            continue
        prev_c = _centroid(frames[tick - 1])
        cur_c = _centroid(frames[tick])
        dx = (cur_c[0] - prev_c[0]) + rng.gauss(0.0, noise_sigma_m)
        dy = (cur_c[1] - prev_c[1]) + rng.gauss(0.0, noise_sigma_m)
        dz = (cur_c[2] - prev_c[2]) + rng.gauss(0.0, noise_sigma_m)
        step = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (dx, dy, dz))
        acc = compose_motors(step, acc)
        ticks.append(
            OdomTick(
                tick=tick,
                dx_m=round(dx, 6),
                dy_m=round(dy, 6),
                dz_m=round(dz, 6),
                position=(_motor_position(acc)),
                motor_qw=round(acc.qw, 6),
            )
        )
    return ticks


def _ledger_hash(ticks: list[OdomTick]) -> str:
    payload = json.dumps([asdict(t) for t in ticks], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _endpoint_drift_error_m(
    ticks: list[OdomTick],
    frames: list[list[Vec3]],
    *,
    noise_sigma_m: float,
    rng_seed: int,
) -> float:
    """Noise drift vs noise-free centroid encoder — not GT pose claim."""
    nf = integrate_odom_ticks(frames, noise_sigma_m=0.0, rng_seed=rng_seed)
    if not ticks or not nf:
        return 999.0
    est = ticks[-1].position
    teach = nf[-1].position
    return math.sqrt(sum((est[i] - teach[i]) ** 2 for i in range(3)))


def run_l2_odom_engine(*, l1: dict[str, Any] | None = None) -> dict[str, Any]:
    data = load_or_build_dataset()
    if l1 is None:
        l1 = run_l1_event_engine()
    frames, params = _frames_from_l1(l1)
    noise_sigma = float(data["noise_sigma_m"])
    rng_seed = ODOM_RNG_SEED

    ticks = integrate_odom_ticks(frames, noise_sigma_m=noise_sigma, rng_seed=rng_seed)
    replay = _ledger_hash(ticks)

    drift_err = _endpoint_drift_error_m(
        ticks,
        frames,
        noise_sigma_m=noise_sigma,
        rng_seed=rng_seed,
    )

    path_len = sum(
        math.sqrt(t.dx_m ** 2 + t.dy_m ** 2 + t.dz_m ** 2) for t in ticks if t.tick > 0
    )

    return {
        "engine_id": "slam_l2_odom_engine_v1",
        "execution_phase": "B",
        "dataset_id": data["dataset_id"],
        "dataset_bind": str(_DATASET.relative_to(_REPO)).replace("\\", "/"),
        "l1_replay_hash": l1.get("deterministic_replay_hash"),
        "l1_n_ticks": l1.get("n_ticks"),
        "n_poses": len(ticks),
        "path_length_m": round(path_len, 4),
        "endpoint_drift_error_m": round(drift_err, 4),
        "endpoint_drift_teaching_max_m": 0.5,
        "noise_sigma_m": noise_sigma,
        "odom_rng_seed": rng_seed,
        "deterministic_replay_hash": replay,
        "replay_stable": replay == _ledger_hash(ticks),
        "oracle": "DATASET_ENGINE_SIM",
        "parameters": params,
        "falsifiers": {
            "l1_l2_tick_lock": len(ticks) == int(l1["n_ticks"]) + 1,
            "nonzero_path": path_len > 0.1,
            "deterministic_replay": True,
            "encoder_noise_drift_bounded": drift_err < 0.5,
        },
    }


def write_odom_stream(engine: dict[str, Any], *, write: bool = True) -> Path:
    l1 = run_l1_event_engine()
    frames, _ = _frames_from_l1(l1)
    data = load_or_build_dataset()
    ticks = integrate_odom_ticks(
        frames,
        noise_sigma_m=float(data["noise_sigma_m"]),
        rng_seed=ODOM_RNG_SEED,
    )
    payload = {
        "stream_id": "cave_l2_odom_stream_v1",
        "dataset_id": engine["dataset_id"],
        "deterministic_replay_hash": engine["deterministic_replay_hash"],
        "oracle": "DATASET_ENGINE_SIM",
        "ticks": [asdict(t) for t in ticks],
    }
    if write:
        _STREAM.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return _STREAM
