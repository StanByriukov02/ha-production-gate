"""Newton-X world step v1 — deterministic L0 heightfield + regolith tick + sensor synth.

Binds: W_regolith_robot_v0 terramech · lunar crater traverse profile.
proof_tier: WORLD_PHYSICS_SIM_SLICE — not GPU · not Isaac · not MEASURED field.
TABU: claim Omniverse truth · claim VLA observes this world.
"""
from __future__ import annotations

import math
from typing import Any

from dogfood_platform.robot_os_hal_lunar_profile_v1 import (
    SCOUT_MASS_KG,
    WORLD_ORACLE as REGOLITH_WORLD_ORACLE,
    evaluate_lunar_traverse_tick,
)
from dogfood_platform.terramech_bekker_on_v1 import ORACLE as BEKKER_ORACLE

WORLD_ID = "NX_lunar_crater_v1"
PROOF_TIER = "WORLD_PHYSICS_SIM_SLICE"
PROFILE_LENGTH_M = 5000.0
HEIGHTFIELD_CELLS = 50
OBS_GRID = 16
G_MOON_MPS2 = 1.62
# Back-compat alias — falsifiers now prefer BEKKER_ORACLE on terramech surface.
REGOLITH_ORACLE = BEKKER_ORACLE


def build_crater_heightfield_1d(
    *,
    length_m: float = PROFILE_LENGTH_M,
    n_cells: int = HEIGHTFIELD_CELLS,
) -> dict[str, Any]:
    """Deterministic 1D rim→floor profile for lunar_crater_5km traverse."""
    cell_m = length_m / max(n_cells - 1, 1)
    heights: list[float] = []
    for i in range(n_cells):
        x = i * cell_m
        t = x / length_m
        # rim rise mid-profile · crater bowl near 2.5 km handoff
        h = 12.0 * math.sin(math.pi * t) + 4.0 * math.sin(2.5 * math.pi * t)
        heights.append(round(h, 4))
    return {
        "world_id": WORLD_ID,
        "length_m": length_m,
        "n_cells": n_cells,
        "cell_m": round(cell_m, 4),
        "heights_m": heights,
        "oracle": "DETERMINISTIC_HEIGHTFIELD",
    }


def sample_heightfield(heightfield: dict[str, Any], cursor_m: float) -> dict[str, Any]:
    length_m = float(heightfield["length_m"])
    cell_m = float(heightfield["cell_m"])
    heights: list[float] = list(heightfield["heights_m"])
    x = max(0.0, min(float(cursor_m), length_m))
    idx = min(int(x / cell_m) if cell_m > 0 else 0, len(heights) - 2)
    frac = (x - idx * cell_m) / cell_m if cell_m > 0 else 0.0
    h0, h1 = heights[idx], heights[idx + 1]
    height_m = h0 + frac * (h1 - h0)
    slope_rad = math.atan2(h1 - h0, cell_m) if cell_m > 0 else 0.0
    slope_deg = math.degrees(slope_rad)
    return {
        "cursor_m": round(x, 4),
        "height_m": round(height_m, 4),
        "slope_deg": round(slope_deg, 4),
        "cell_index": idx,
    }


def synthesize_sensor_obs(
    heightfield: dict[str, Any],
    cursor_m: float,
    *,
    grid: int = OBS_GRID,
) -> dict[str, Any]:
    """Mock exteroception from heightfield — no Isaac render. TABU: claim camera MEASURED."""
    cell_m = float(heightfield["cell_m"])
    half = (grid // 2) * cell_m
    pixels: list[list[float]] = []
    for row in range(grid):
        row_px: list[float] = []
        for col in range(grid):
            offset = (col - grid // 2) * cell_m
            sample = sample_heightfield(heightfield, cursor_m + offset)
            # normalize height + slope into 0..1 for downstream policy tests
            val = (sample["height_m"] + 20.0) / 40.0 + sample["slope_deg"] / 30.0
            row_px.append(round(max(0.0, min(1.0, val)), 4))
        pixels.append(row_px)
    center = sample_heightfield(heightfield, cursor_m)
    return {
        "oracle": "HEIGHTFIELD_SYNTH",
        "grid": grid,
        "center_cursor_m": center["cursor_m"],
        "center_slope_deg": center["slope_deg"],
        "center_height_m": center["height_m"],
        "pixels": pixels,
    }


def init_newton_x_world(
    state: dict[str, Any],
    *,
    enabled: bool = True,
) -> dict[str, Any]:
    nx = state.setdefault("newton_x", {})
    nx.update(
        {
            "enabled": bool(enabled),
            "world_id": WORLD_ID,
            "proof_tier": PROOF_TIER,
            "heightfield": build_crater_heightfield_1d(),
            "step_count": int(nx.get("step_count") or 0),
        }
    )
    return state


def step_newton_x_world(
    state: dict[str, Any],
    carrier_id: str,
    step_m: float,
    *,
    mass_kg: float = SCOUT_MASS_KG,
) -> dict[str, Any]:
    """One L0 world step: terramech oracle + heightfield sample + sensor obs on carrier."""
    init_newton_x_world(state, enabled=True)
    nx = state["newton_x"]
    carrier = state["carriers"][carrier_id]
    profile_id = str(state.get("profile_id", "lunar_crater_5km"))
    cursor_before = float(carrier.get("cursor_m", 0.0))
    hf = nx["heightfield"]

    mp_bind = state.get("material_physics_bind")
    if isinstance(mp_bind, dict) and mp_bind.get("variant_id"):
        from dogfood_platform.material_tick_ingress_v1 import evaluate_lunar_row_with_material

        terr, material = evaluate_lunar_row_with_material(
            step_m,
            profile_id=profile_id,
            state=state,
            mass_kg=mass_kg,
        )
        if material:
            carrier["material_physics"] = material
            carrier["material_variant"] = material.get("variant_id")
    else:
        terr = evaluate_lunar_traverse_tick(step_m, profile_id=profile_id, mass_kg=mass_kg)
    geo = sample_heightfield(hf, cursor_before)
    obs = synthesize_sensor_obs(hf, cursor_before)

    nx["step_count"] = int(nx.get("step_count") or 0) + 1
    step_row = {
        "step_index": nx["step_count"],
        "carrier_id": carrier_id,
        "cursor_m": cursor_before,
        "step_m": round(float(step_m), 4),
        "terrain": geo,
        "terramech": terr,
        "sensor": {
            "grid": obs["grid"],
            "center_slope_deg": obs["center_slope_deg"],
            "oracle": obs["oracle"],
        },
    }
    nx["last_step"] = step_row

    carrier["newton_x_obs"] = obs
    carrier["lunar_physics"] = terr
    carrier["newton_x_terrain"] = geo
    return step_row


def validate_newton_x_falsifiers(
    state: dict[str, Any],
    *,
    carrier_id: str = "scout_A",
) -> dict[str, Any]:
    nx = state.get("newton_x") or {}
    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    last = nx.get("last_step") or {}
    terr = last.get("terramech") or {}
    obs = carrier.get("newton_x_obs") or {}
    hf = nx.get("heightfield") or {}

    checks: dict[str, bool] = {
        "F_newton_x_enabled": nx.get("enabled") is True,
        "F_world_id": nx.get("world_id") == WORLD_ID,
        "F_heightfield_cells": len(hf.get("heights_m") or []) == HEIGHTFIELD_CELLS,
        "F_heightfield_deterministic": hf.get("oracle") == "DETERMINISTIC_HEIGHTFIELD",
        "F_bekker_from_rust": terr.get("oracle") == BEKKER_ORACLE
        or bool((terr.get("honesty") or {}).get("bekker_from_rust")),
        "F_w_regolith_world_lane": terr.get("world_oracle") == REGOLITH_WORLD_ORACLE
        or terr.get("world_id") == "W_regolith_robot_v0"
        or terr.get("oracle") == BEKKER_ORACLE,
        "F_traverse_feasible_bool": isinstance(terr.get("traverse_feasible"), bool),
        "F_sinkage_positive": float(terr.get("sinkage_mm") or 0) > 0,
        "F_compaction_resistance_present": float(terr.get("compaction_resistance_n") or 0) > 0,
        "F_sensor_obs_grid": obs.get("grid") == OBS_GRID,
        "F_sensor_pixels_shape": len(obs.get("pixels") or []) == OBS_GRID,
        "F_step_recorded": last.get("step_index", 0) >= 1,
        "F_g_moon": abs(float(terr.get("g_mps2") or 0) - G_MOON_MPS2) < 1e-6,
    }
    bind = (state.get("material_physics_bind") or {})
    if bind.get("variant_id"):
        checks["F_material_physics_on_carrier"] = bool(carrier.get("material_physics"))
        checks["F_ingress_from_material_bus"] = terr.get("ingress_source") == "material_physics_bus"
        mp = carrier.get("material_physics") or {}
        checks["F_material_ingress_matches_terramech"] = abs(
            float(mp.get("ingress_disturbance_mult") or 0.0) - float(terr.get("ingress_disturbance_mult") or 0.0)
        ) < 1e-4
    fail = [k for k, v in checks.items() if not v]
    return {"checks": checks, "fail": fail, "pass": len(fail) == 0}
