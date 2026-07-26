"""L4 map tile commit — octree insert + async commit latency envelope."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

CPU_HZ = 48_000_000
CYCLES_PER_POINT_INSERT = 48
CYCLES_PER_TILE_MERGE = 12_800
FOC_PERIOD_US = 50.0
COMMIT_BUDGET_MS = 2000.0
COMMIT_TARGET_MS = 500.0
TILE_BYTES_PER_POINT = 12
MAX_TILE_POINTS = 512


@dataclass
class MapTile:
    key: tuple[int, int, int]
    points: list[tuple[float, float, float]] = field(default_factory=list)

    def byte_size(self) -> int:
        return len(self.points) * TILE_BYTES_PER_POINT + 64


def _voxel_key(p: tuple[float, float, float], *, voxel_m: float) -> tuple[int, int, int]:
    return (
        int(math.floor(p[0] / voxel_m)),
        int(math.floor(p[1] / voxel_m)),
        int(math.floor(p[2] / voxel_m)),
    )


def build_tiles_from_points(
    points: list[tuple[float, float, float]],
    *,
    voxel_m: float = 0.25,
) -> dict[tuple[int, int, int], MapTile]:
    tiles: dict[tuple[int, int, int], MapTile] = {}
    for p in points:
        key = _voxel_key(p, voxel_m=voxel_m)
        if key not in tiles:
            tiles[key] = MapTile(key=key)
        tile = tiles[key]
        if len(tile.points) < MAX_TILE_POINTS:
            tile.points.append(p)
    return tiles


def latency_ms_from_cycles(cycles: int, *, cpu_hz: int = CPU_HZ) -> float:
    return cycles / cpu_hz * 1000.0


def commit_tile_batch(
    tiles: dict[tuple[int, int, int], MapTile],
    *,
    batch_size: int = 4,
) -> dict[str, Any]:
    """Simulate TIER-C async map commit — must not block FOC ISR (50 µs)."""
    keys = sorted(tiles.keys())
    commit_latencies_ms: list[float] = []
    total_bytes = 0
    batches = 0

    for i in range(0, len(keys), batch_size):
        batch_keys = keys[i : i + batch_size]
        cycles = CYCLES_PER_TILE_MERGE
        for k in batch_keys:
            n = len(tiles[k].points)
            cycles += n * CYCLES_PER_POINT_INSERT
            total_bytes += tiles[k].byte_size()
        commit_latencies_ms.append(latency_ms_from_cycles(cycles))
        batches += 1

    def p95(vals: list[float]) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        return s[int(0.95 * (len(s) - 1))]

    p95_ms = p95(commit_latencies_ms)
    max_ms = max(commit_latencies_ms) if commit_latencies_ms else 0.0

    return {
        "tile_count": len(tiles),
        "batch_count": batches,
        "total_map_bytes": total_bytes,
        "commit_latency_ms_p95": round(p95_ms, 4),
        "commit_latency_ms_max": round(max_ms, 4),
        "commit_budget_ms": COMMIT_BUDGET_MS,
        "commit_target_ms": COMMIT_TARGET_MS,
        "foc_period_us": FOC_PERIOD_US,
        "non_blocking_foc": p95_ms * 1000.0 > FOC_PERIOD_US,
        "latency_model": {
            "cpu_hz": CPU_HZ,
            "cycles_per_insert": CYCLES_PER_POINT_INSERT,
            "cycles_per_merge": CYCLES_PER_TILE_MERGE,
            "oracle": "ENVELOPE_CYCLES",
            "tier": "TIER-C async",
        },
    }


def run_map_commit_pipeline(
    points: list[tuple[float, float, float]],
    *,
    voxel_m: float = 0.25,
    batch_size: int = 4,
) -> dict[str, Any]:
    tiles = build_tiles_from_points(points, voxel_m=voxel_m)
    commit = commit_tile_batch(tiles, batch_size=batch_size)
    avg_points_per_tile = sum(len(t.points) for t in tiles.values()) / max(len(tiles), 1)
    return {
        "voxel_m": voxel_m,
        "point_count": len(points),
        "avg_points_per_tile": round(avg_points_per_tile, 2),
        **commit,
    }
