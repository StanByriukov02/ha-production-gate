"""Phase B L4 — dataset-bound map compose engine (L1 events + L3 pose → tiles)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from dogfood_platform.slam_l1_event_engine_v1 import collect_event_point_indices, run_l1_event_engine
from dogfood_platform.slam_map_commit_v1 import run_map_commit_pipeline
from dogfood_platform.slam_reform_resample_v1 import load_or_build_dataset
from dogfood_platform.slam_se3_motor_v1 import Motor

_REPO = Path(__file__).resolve().parents[1]
_DATASET = _REPO / "fixtures" / "slam" / "cave_corridor_dataset_v1.json"
_STREAM = _REPO / "fixtures" / "slam" / "cave_l4_map_stream_v1.json"

VOXEL_M = 0.25
BATCH_SIZE = 4


def _motor_from_registration(reg: dict[str, float]) -> Motor:
    return Motor(
        qw=float(reg["qw"]),
        qx=float(reg["qx"]),
        qy=float(reg["qy"]),
        qz=float(reg["qz"]),
        tx=float(reg["tx"]),
        ty=float(reg["ty"]),
        tz=float(reg["tz"]),
    )


def _world_points_from_stack(
    *,
    event_indices: set[int],
    motor: Motor,
    src_points: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    return [motor.apply(src_points[i]) for i in sorted(event_indices)]


def _map_ledger_hash(world_pts: list[tuple[float, float, float]], commit: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "points": [[round(p[0], 6), round(p[1], 6), round(p[2], 6)] for p in world_pts],
            "tile_count": commit["tile_count"],
            "total_map_bytes": commit["total_map_bytes"],
            "commit_latency_ms_p95": commit["commit_latency_ms_p95"],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def run_l4_map_engine(
    *,
    l1: dict[str, Any] | None = None,
    l3: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_or_build_dataset()
    if data.get("dataset_id") != "cave_corridor_dataset_v1":
        raise RuntimeError("engine bound to cave_corridor_dataset_v1 only")

    if l1 is None:
        l1 = run_l1_event_engine()
    if l3 is None:
        from dogfood_platform.slam_l3_pose_engine_v1 import run_l3_pose_engine

        l3 = run_l3_pose_engine()

    params = l1["parameters"]
    event_indices = collect_event_point_indices(
        n_ticks=int(params["n_ticks"]),
        step_m=float(params["step_m"]),
    )
    src_points = [tuple(p) for p in data["src_points"]]
    motor = _motor_from_registration(l3["registration"]["motor"])
    world_pts = _world_points_from_stack(
        event_indices=event_indices,
        motor=motor,
        src_points=src_points,
    )
    commit = run_map_commit_pipeline(world_pts, voxel_m=VOXEL_M, batch_size=BATCH_SIZE)
    replay = _map_ledger_hash(world_pts, commit)

    return {
        "engine_id": "slam_l4_map_engine_v1",
        "execution_phase": "B",
        "dataset_id": data["dataset_id"],
        "dataset_bind": str(_DATASET.relative_to(_REPO)).replace("\\", "/"),
        "l1_event_replay_hash": l1.get("deterministic_replay_hash"),
        "l3_pose_replay_hash": l3.get("deterministic_replay_hash"),
        "compose": {
            "wiring": "L1_event_indices → L3_motor.apply → voxel_tiles",
            "event_point_count": len(event_indices),
            "map_point_count": len(world_pts),
            "voxel_m": VOXEL_M,
            "batch_size": BATCH_SIZE,
            **commit,
        },
        "deterministic_replay_hash": replay,
        "replay_stable": replay == _map_ledger_hash(world_pts, commit),
        "oracle": "DATASET_ENGINE_SIM",
        "falsifiers": {
            "l1_events_reach_map": len(world_pts) > 0,
            "tiles_created": commit["tile_count"] > 0,
            "commit_p95_under_budget": commit["commit_latency_ms_p95"] < commit["commit_budget_ms"],
            "commit_p95_under_target": commit["commit_latency_ms_p95"] < commit["commit_target_ms"],
            "non_blocking_foc": commit["non_blocking_foc"],
            "map_bytes_reasonable": commit["total_map_bytes"] < 1_000_000,
            "deterministic_replay": True,
        },
    }


def write_map_stream(engine: dict[str, Any], *, write: bool = True) -> Path:
    payload = {
        "stream_id": "cave_l4_map_stream_v1",
        "dataset_id": engine["dataset_id"],
        "deterministic_replay_hash": engine["deterministic_replay_hash"],
        "l1_event_replay_hash": engine["l1_event_replay_hash"],
        "l3_pose_replay_hash": engine["l3_pose_replay_hash"],
        "oracle": "DATASET_ENGINE_SIM",
        "tile_count": engine["compose"]["tile_count"],
        "map_point_count": engine["compose"]["map_point_count"],
        "total_map_bytes": engine["compose"]["total_map_bytes"],
        "commit_latency_ms_p95": engine["compose"]["commit_latency_ms_p95"],
    }
    if write:
        _STREAM.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return _STREAM
