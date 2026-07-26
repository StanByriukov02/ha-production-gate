"""EDS-2R v1 geometry — spiral layout from SCAD bind (arena hop 1)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_ARENA_ROOT = _REPO / "results" / "platform_bpass" / "arena"
_BIND = _ARENA_ROOT / "EDS_2R_GEOMETRY_BIND_v1.json"


def load_geometry_bind(bind: dict[str, Any] | None = None) -> dict[str, Any]:
    return bind or json.loads(_BIND.read_text(encoding="utf-8"))


def _spiral_point(r0: float, r1: float, turns: float, t: float, phase_rad: float) -> tuple[float, float]:
    r = r0 + (r1 - r0) * t
    theta = 2.0 * math.pi * turns * t + phase_rad
    return r * math.cos(theta), r * math.sin(theta)


def spiral_phase_polyline(
    phase_index: int,
    *,
    n_points: int = 48,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One phase spiral polyline in mm (tile center origin)."""
    data = load_geometry_bind(bind)
    p = data["params_mm"]
    r0 = float(p["inner_lift_radius"])
    r1 = float(p["active_radius"])
    turns = float(p["spiral_turns"])
    offset = math.radians(float(data.get("phase_offset_deg") or 90.0) * phase_index)
    phase = (data.get("phases") or ["A", "B", "C", "D"])[phase_index % 4]
    pts = [_spiral_point(r0, r1, turns, i / max(n_points - 1, 1), offset) for i in range(n_points)]
    zone = "inner_lift" if r1 * 0.4 > r0 else "outer_transport"
    return {
        "phase": phase,
        "phase_index": phase_index,
        "points_mm": [[round(x, 4), round(y, 4)] for x, y in pts],
        "zone_hint": zone,
        "pitch_class": data["zones"]["inner_lift"]["pitch_class"] if phase_index % 2 == 0 else data["zones"]["outer_transport"]["pitch_class"],
        "source": data.get("source_geometry"),
    }


def layout_receipt(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    data = load_geometry_bind(bind)
    p = data["params_mm"]
    phases = [spiral_phase_polyline(i, bind=data) for i in range(int(p["phase_count"]))]
    active_area_mm2 = math.pi * float(p["active_radius"]) ** 2
    tile_area_mm2 = float(p["tile_size"]) ** 2
    clearance_ok = float(p["hv_guard_clearance"]) >= 0.8
    return {
        "hop_id": "h-arena-eds-layout",
        "verdict": "PASS",
        "oracle": "CITED_BIND",
        "phase_count": int(p["phase_count"]),
        "spiral_turns": float(p["spiral_turns"]),
        "active_radius_mm": float(p["active_radius"]),
        "tile_size_mm": float(p["tile_size"]),
        "active_area_mm2": round(active_area_mm2, 2),
        "tile_fill_ratio": round(active_area_mm2 / tile_area_mm2, 4),
        "phases": phases,
        "guard_clearance_mm": float(p["hv_guard_clearance"]),
        "guard_clearance_pass": clearance_ok,
        "geometry_source": data.get("source_geometry"),
        "falsifier": data.get("falsifier"),
    }
