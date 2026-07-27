"""Rim → regolith burial → FGM shell → TIM → die — L1 R-series harness."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from production_gate.lunar_lc2_package_harness_v1 import (
    _FGM_BRANCH,
    _REGOLITH_RHO_BRANCH,
    harness_for_stack,
    resolve_stack_layers,
)
from production_gate.lunar_zone_table_v1 import ZONES, polar_delta_t_k, zone_snapshot
from production_gate.lunar_site_geometry_v1 import rim_duty_for_embed, shackleton_path_profile

_EQUATORIAL_DELTA_T_K = 287.0


@dataclass(frozen=True)
class PackageThermalPathResult:
    t_ambient_k: float
    t_die_mean_k: float
    t_die_min_k: float
    t_die_max_k: float
    delta_ambient_k: float
    delta_junction_k: float
    junction_swing_frac: float
    thermal_index: float
    r_total_k_per_m2: float
    fgm_branch: str
    regolith_rho_branch: str
    outer_shell_material_id: str
    fgm_shell_material_id: str
    oracle: str
    l0_cites: tuple[str, ...]


def _layer_resistance_k_m2(*, thickness_m: float, k_w_mk: float) -> float:
    return thickness_m / max(k_w_mk, 1e-9)


def _fgm_layer_index(layers: list[dict[str, Any]]) -> int:
    for i, layer in enumerate(layers):
        if str(layer.get("layer_id") or "").startswith("fgm"):
            return i
    return 1 if len(layers) > 1 else 0


def evaluate_package_thermal_path(
    *,
    fgm_branch: _FGM_BRANCH = "A",
    regolith_rho_branch: _REGOLITH_RHO_BRANCH = "A",
    include_outer_regolith: bool = True,
    rim_duty: float | None = None,
    footprint_m2: float | None = None,
) -> PackageThermalPathResult:
    """Mission-average ambient + junction swing attenuation through LC-2 stack."""
    harness = harness_for_stack(
        fgm_branch=fgm_branch,
        regolith_rho_branch=regolith_rho_branch,
        include_outer_regolith=include_outer_regolith,
    )
    layers = resolve_stack_layers(harness)
    outer_mat = str(layers[0]["material_id"])
    if include_outer_regolith:
        fgm_idx = _fgm_layer_index(layers)
        fgm_mat = str(layers[fgm_idx]["material_id"])
    else:
        fgm_mat = str(layers[0]["material_id"])
        outer_mat = "none"

    rim = zone_snapshot("rim_sun")
    floor_mean = float(ZONES["psr_floor"]["t_k_mean"])
    duty = rim_duty if rim_duty is not None else rim_duty_for_embed()
    t_ambient = duty * rim.t_k + (1.0 - duty) * floor_mean
    delta_ambient = polar_delta_t_k()

    fp = footprint_m2 or float(harness["footprint_m2"])
    _ = fp  # reserved for future area scaling
    r_layers = [
        _layer_resistance_k_m2(thickness_m=float(layer["thickness_m"]), k_w_mk=float(layer["k_w_mk"]))
        for layer in layers
    ]
    r_total = sum(r_layers)
    r_junction_path = sum(r_layers[-2:]) if len(r_layers) >= 2 else r_layers[-1]
    swing_frac = min(1.0, r_junction_path / max(r_total, 1e-12))
    delta_junction = delta_ambient * swing_frac
    t_die_mean = t_ambient
    t_die_min = t_die_mean - delta_junction / 2.0
    t_die_max = t_die_mean + delta_junction / 2.0
    thermal_index = delta_junction / _EQUATORIAL_DELTA_T_K
    cites: list[str] = ["SK-09", "SK-12", "HEIKEN-L0-03", "FGRM-L0-10", "LC2-qual-passport", "SITE-GEOMETRY-BIND"]
    for layer in layers:
        cites.extend(layer.get("l0_cites") or [])
    return PackageThermalPathResult(
        t_ambient_k=round(t_ambient, 4),
        t_die_mean_k=round(t_die_mean, 4),
        t_die_min_k=round(t_die_min, 4),
        t_die_max_k=round(t_die_max, 4),
        delta_ambient_k=round(delta_ambient, 4),
        delta_junction_k=round(delta_junction, 4),
        junction_swing_frac=round(swing_frac, 6),
        thermal_index=round(thermal_index, 6),
        r_total_k_per_m2=round(r_total, 8),
        fgm_branch=fgm_branch,
        regolith_rho_branch=regolith_rho_branch,
        outer_shell_material_id=outer_mat,
        fgm_shell_material_id=fgm_mat,
        oracle="L1_R_SERIES_HARNESS",
        l0_cites=tuple(dict.fromkeys(cites)),
    )


def package_thermal_path_dict(
    *,
    fgm_branch: _FGM_BRANCH = "A",
    regolith_rho_branch: _REGOLITH_RHO_BRANCH = "A",
    include_outer_regolith: bool = True,
) -> dict[str, Any]:
    r = evaluate_package_thermal_path(
        fgm_branch=fgm_branch,
        regolith_rho_branch=regolith_rho_branch,
        include_outer_regolith=include_outer_regolith,
    )
    harness = harness_for_stack(
        fgm_branch=fgm_branch,
        regolith_rho_branch=regolith_rho_branch,
        include_outer_regolith=include_outer_regolith,
    )
    return {
        "t_ambient_k": r.t_ambient_k,
        "t_die_mean_k": r.t_die_mean_k,
        "t_die_min_k": r.t_die_min_k,
        "t_die_max_k": r.t_die_max_k,
        "delta_ambient_k": r.delta_ambient_k,
        "delta_junction_k": r.delta_junction_k,
        "junction_swing_frac": r.junction_swing_frac,
        "thermal_index": r.thermal_index,
        "r_total_k_per_m2": r.r_total_k_per_m2,
        "fgm_branch": fgm_branch,
        "regolith_rho_branch": regolith_rho_branch,
        "include_outer_regolith": include_outer_regolith,
        "outer_shell_material_id": r.outer_shell_material_id,
        "fgm_shell_material_id": r.fgm_shell_material_id,
        "harness_id": harness["harness_id"],
        "oracle": r.oracle,
        "l0_cites": list(r.l0_cites),
    }


def compare_fgm_thermal_paths(*, regolith_rho_branch: _REGOLITH_RHO_BRANCH = "A") -> dict[str, Any]:
    """FGM A/B ΔT_junction — inner stack lane (outer regolith excluded; burial masks FGM k)."""
    path_a = package_thermal_path_dict(
        fgm_branch="A",
        regolith_rho_branch=regolith_rho_branch,
        include_outer_regolith=False,
    )
    path_b = package_thermal_path_dict(
        fgm_branch="B",
        regolith_rho_branch=regolith_rho_branch,
        include_outer_regolith=False,
    )
    delta_a = float(path_a["delta_junction_k"])
    delta_b = float(path_b["delta_junction_k"])
    return {
        "compare_id": "FGM_SHELL_THERMAL_COMPARE_v1",
        "lane": "inner_fgm_stack_only",
        "note": "outer regolith burial masks FGM k delta in full corridor stack",
        "regolith_rho_branch_fixed": regolith_rho_branch,
        "fgm_A": {
            "branch": "A",
            "material_id": path_a["fgm_shell_material_id"],
            "delta_junction_k": delta_a,
            "thermal_index": path_a["thermal_index"],
            "junction_swing_frac": path_a["junction_swing_frac"],
        },
        "fgm_B": {
            "branch": "B",
            "material_id": path_b["fgm_shell_material_id"],
            "delta_junction_k": delta_b,
            "thermal_index": path_b["thermal_index"],
            "junction_swing_frac": path_b["junction_swing_frac"],
        },
        "delta_junction_diff_k": round(abs(delta_a - delta_b), 6),
        "variants_diverge": delta_a != delta_b,
        "oracle": "L1_HARNESS_NOT_SOLVER",
    }


def compare_regolith_rho_thermal_paths(*, fgm_branch: _FGM_BRANCH = "A") -> dict[str, Any]:
    """Regolith ρ loose vs compact — falsifier on thermal_index."""
    path_a = package_thermal_path_dict(fgm_branch=fgm_branch, regolith_rho_branch="A")
    path_b = package_thermal_path_dict(fgm_branch=fgm_branch, regolith_rho_branch="B")
    delta_a = float(path_a["delta_junction_k"])
    delta_b = float(path_b["delta_junction_k"])
    idx_a = float(path_a["thermal_index"])
    idx_b = float(path_b["thermal_index"])
    return {
        "compare_id": "REGOLITH_RHO_THERMAL_COMPARE_v1",
        "lane": "full_stack_with_outer_burial",
        "fgm_branch_fixed": fgm_branch,
        "rho_A": {
            "branch": "A",
            "material_id": path_a["outer_shell_material_id"],
            "rho_class": "highland_surface_15cm_loose",
            "delta_junction_k": delta_a,
            "thermal_index": idx_a,
            "junction_swing_frac": path_a["junction_swing_frac"],
        },
        "rho_B": {
            "branch": "B",
            "material_id": path_b["outer_shell_material_id"],
            "rho_class": "highland_depth_60cm_compact",
            "delta_junction_k": delta_b,
            "thermal_index": idx_b,
            "junction_swing_frac": path_b["junction_swing_frac"],
        },
        "delta_junction_diff_k": round(abs(delta_a - delta_b), 6),
        "thermal_index_diff": round(abs(idx_a - idx_b), 8),
        "variants_diverge": idx_a != idx_b,
        "compact_higher_thermal_index": idx_b > idx_a,
        "oracle": "L1_HARNESS_NOT_SOLVER",
    }
