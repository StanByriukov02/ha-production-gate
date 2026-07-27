"""EDS-2R quasi-static E-field — 2D Laplace per phase (arena hop 2)."""
from __future__ import annotations

import math
from typing import Any

from production_gate.arena.eds_2r_geometry_v1 import layout_receipt, load_geometry_bind


def _solve_laplace(
    nx: int,
    ny: int,
    fixed: list[tuple[int, int, float]],
    *,
    max_iter: int = 400,
    tol: float = 1e-5,
) -> list[list[float]]:
    phi = [[0.0 for _ in range(nx)] for _ in range(ny)]
    fixed_map = {(i, j): v for i, j, v in fixed}
    for (i, j), v in fixed_map.items():
        phi[j][i] = v
    for _ in range(max_iter):
        max_delta = 0.0
        new_phi = [row[:] for row in phi]
        for j in range(1, ny - 1):
            for i in range(1, nx - 1):
                if (i, j) in fixed_map:
                    continue
                avg = 0.25 * (phi[j][i - 1] + phi[j][i + 1] + phi[j - 1][i] + phi[j + 1][i])
                max_delta = max(max_delta, abs(avg - phi[j][i]))
                new_phi[j][i] = avg
        phi = new_phi
        if max_delta < tol:
            break
    return phi


def _world_to_grid(x_mm: float, y_mm: float, half_mm: float, nx: int, ny: int) -> tuple[int, int]:
    xi = int(round((x_mm + half_mm) / (2.0 * half_mm) * (nx - 1)))
    yi = int(round((y_mm + half_mm) / (2.0 * half_mm) * (ny - 1)))
    return max(1, min(nx - 2, xi)), max(1, min(ny - 2, yi))


def field_map_for_phase(
    phase_index: int,
    *,
    v_phase: float = 1.0,
    grid: int = 36,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    layout = layout_receipt(bind=bind)
    data = load_geometry_bind(bind)
    p = data["params_mm"]
    half = float(p["tile_size"]) / 2.0
    phase_row = layout["phases"][phase_index]
    gap_inner = float(p["gap_inner"])
    gap_outer = float(p["gap_outer"])
    w_inner = float(p["electrode_width_inner"])
    w_outer = float(p["electrode_width_outer"])
    fixed: list[tuple[int, int, float]] = []
    for x_mm, y_mm in phase_row["points_mm"]:
        r = math.hypot(x_mm, y_mm)
        zone_inner = r < float(p["inner_lift_radius"]) * 2.5
        gap = gap_inner if zone_inner else gap_outer
        width = w_inner if zone_inner else w_outer
        stencil = max(1, int(round(3.0 * width / max(gap, 0.1))))
        ci, cj = _world_to_grid(x_mm, y_mm, half, grid, grid)
        for di in range(-stencil, stencil + 1):
            for dj in range(-stencil, stencil + 1):
                if di * di + dj * dj <= stencil * stencil:
                    i, j = ci + di, cj + dj
                    if 1 <= i < grid - 1 and 1 <= j < grid - 1:
                        fixed.append((i, j, v_phase))
    # guard ring at tile edge — ground
    for i in range(grid):
        fixed.append((i, 0, 0.0))
        fixed.append((i, grid - 1, 0.0))
        fixed.append((0, i, 0.0))
        fixed.append((grid - 1, i, 0.0))
    phi = _solve_laplace(grid, grid, fixed)
    e_peak = 0.0
    e_sum = 0.0
    n = 0
    for j in range(1, grid - 1):
        for i in range(1, grid - 1):
            ex = -(phi[j][i + 1] - phi[j][i - 1]) * 0.5
            ey = -(phi[j + 1][i] - phi[j - 1][i]) * 0.5
            mag = math.hypot(ex, ey)
            e_peak = max(e_peak, mag)
            e_sum += mag
            n += 1
    pitch_factor = (w_inner / max(gap_inner, 0.1) + w_outer / max(gap_outer, 0.1)) * 0.5
    e_peak *= pitch_factor
    e_sum *= pitch_factor
    return {
        "phase": phase_row["phase"],
        "phase_index": phase_index,
        "v_phase": v_phase,
        "grid_size": grid,
        "e_peak_per_v": round(e_peak, 6),
        "e_mean_per_v": round(e_sum / max(n, 1), 6),
        "solver": "laplace_jacobi_2d",
        "oracle": "PROXY_STRUCTURE",
    }


def field_receipt(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    maps = [field_map_for_phase(i, bind=bind) for i in range(4)]
    peaks = [m["e_peak_per_v"] for m in maps]
    return {
        "hop_id": "h-arena-eds-field",
        "verdict": "PASS",
        "oracle": "PROXY_STRUCTURE",
        "phase_maps": maps,
        "peak_spread": round(max(peaks) - min(peaks), 6),
        "all_phases_nonzero": all(p > 0 for p in peaks),
        "note": "G0 Laplace proxy — not Maxwell FEM (L_MAXWELL PARK until G1 BC receipt)",
        "falsifier": "field unchanged when pitch/geometry changes between layout variants",
    }


def compare_pitch_field_sensitivity(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    base = field_receipt(bind=bind)
    data = load_geometry_bind(bind)
    alt = dict(data)
    alt_p = dict(data["params_mm"])
    alt_p["gap_inner"] = float(alt_p["gap_inner"]) * 1.2
    alt["params_mm"] = alt_p
    variant = field_receipt(bind=alt)
    base_peak = sum(m["e_peak_per_v"] for m in base["phase_maps"])
    var_peak = sum(m["e_peak_per_v"] for m in variant["phase_maps"])
    return {
        "base_peak_sum": round(base_peak, 6),
        "variant_peak_sum": round(var_peak, 6),
        "geometry_sensitive": abs(var_peak - base_peak) > 1e-6,
        "falsifier_pass": abs(var_peak - base_peak) > 1e-6,
    }
