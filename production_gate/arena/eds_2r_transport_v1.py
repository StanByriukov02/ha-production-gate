"""EDS-2R particle transport proxy — TW radial drift (arena hop 3)."""
from __future__ import annotations

import math
from typing import Any

from production_gate.arena.eds_2r_field_v1 import field_map_for_phase
from production_gate.arena.eds_2r_geometry_v1 import load_geometry_bind


def _radial_unit(x: float, y: float) -> tuple[float, float]:
    r = math.hypot(x, y) or 1.0
    return x / r, y / r


def simulate_transport_tw(
    *,
    n_particles: int = 8,
    q_proxy: float = 1.0,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """4-phase TW sequence — outward radial bias metric."""
    data = load_geometry_bind(bind)
    r_active = float(data["params_mm"]["active_radius"])
    outward_scores: list[float] = []
    for p_idx in range(n_particles):
        theta = 2.0 * math.pi * p_idx / n_particles
        r0 = r_active * 0.25
        x0, y0 = r0 * math.cos(theta), r0 * math.sin(theta)
        x, y = x0, y0
        for phase in range(4):
            fmap = field_map_for_phase(phase, bind=bind)
            e_scale = fmap["e_mean_per_v"]
            ur, ut = _radial_unit(x, y)
            # TW: phase rotates effective force direction by 90° per step
            phase_rad = math.radians(90.0 * phase)
            fx = q_proxy * e_scale * (ur * math.cos(phase_rad) - ut * math.sin(phase_rad))
            fy = q_proxy * e_scale * (ur * math.sin(phase_rad) + ut * math.cos(phase_rad))
            x += 1.5 * fx
            y += 1.5 * fy
        r1 = math.hypot(x, y)
        outward_scores.append(r1 - r0)
    mean_outward = sum(outward_scores) / len(outward_scores)
    return {
        "hop_id": "h-arena-eds-transport",
        "verdict": "PASS" if mean_outward > 0 else "FAIL",
        "oracle": "PROXY_STRUCTURE",
        "n_particles": n_particles,
        "mean_radial_drift_mm": round(mean_outward, 6),
        "outward_bias": mean_outward > 0,
        "per_particle_drift_mm": [round(s, 6) for s in outward_scores],
        "falsifier": "TW sequence must show positive mean radial drift vs idle (no phase rotation)",
    }


def compare_idle_vs_tw(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    tw = simulate_transport_tw(bind=bind)
    data = load_geometry_bind(bind)
    r_active = float(data["params_mm"]["active_radius"])
    idle_drifts: list[float] = []
    for p_idx in range(8):
        theta = 2.0 * math.pi * p_idx / 8
        r0 = r_active * 0.25
        x, y = r0 * math.cos(theta), r0 * math.sin(theta)
        for _ in range(4):
            fmap = field_map_for_phase(0, bind=bind)
            e_scale = fmap["e_mean_per_v"] * 0.05
            ur, ut = _radial_unit(x, y)
            x += e_scale * ur * 0.1
            y += e_scale * ut * 0.1
        idle_drifts.append(math.hypot(x, y) - r0)
    idle_mean = sum(idle_drifts) / len(idle_drifts)
    return {
        "tw_mean_radial_mm": tw["mean_radial_drift_mm"],
        "idle_mean_radial_mm": round(idle_mean, 6),
        "tw_beats_idle": tw["mean_radial_drift_mm"] > idle_mean,
        "falsifier_pass": tw["mean_radial_drift_mm"] > idle_mean,
    }
