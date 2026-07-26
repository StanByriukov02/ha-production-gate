"""GAP-MR-08/09 L5 — vacuum radiative BC + lumped transient vs L1 R-series falsifier."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

from dogfood_platform.lunar_package_thermal_path_v1 import package_thermal_path_dict
from dogfood_platform.lunar_regolith_thermal_v1 import effective_k_w_mk

_REPO = Path(__file__).resolve().parents[1]
_VAC_BIND = _REPO / "results" / "platform_bpass" / "moon" / "VACUUM_RADIATIVE_BC_BIND_v1.json"
_TRANSIENT_BIND = _REPO / "results" / "platform_bpass" / "moon" / "THERMAL_TRANSIENT_BIND_v1.json"

ZoneClass = Literal["rim_sun", "psr_floor"]


def load_vacuum_bc_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _VAC_BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def load_transient_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _TRANSIENT_BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def radiative_net_flux_w_m2(
    t_surf_k: float,
    *,
    zone: ZoneClass = "rim_sun",
    bind: dict[str, Any] | None = None,
    illum_frac: float | None = None,
) -> dict[str, Any]:
    """Vacuum radiative BC — ON catalog equation (mirror of Rust; Dual proves match)."""
    del bind  # constants owned by ON catalog
    from dogfood_platform.vacuum_radiative_bc_on_v1 import ORACLE as RAD_ORACLE
    from dogfood_platform.vacuum_radiative_bc_on_v1 import flux_from_catalog

    rust = flux_from_catalog(zone=zone, t_k=t_surf_k, illum=illum_frac)
    return {
        "zone": zone,
        "t_surf_k": round(t_surf_k, 4),
        "t_sky_rad_k": float(rust["t_sky_rad_k"]),
        "t_sky_ambient_k": float(rust["t_sky_ambient_k"]),
        "q_rad_w_m2": round(float(rust["q_rad_w_m2"]), 4),
        "q_solar_w_m2": round(float(rust["q_solar_w_m2"]), 4),
        "q_net_w_m2": round(float(rust["q_net_w_m2"]), 4),
        "q_in_surface_w_m2": round(float(rust["q_in_surface_w_m2"]), 4),
        "illum_frac": round(float(rust["illum_frac"]), 6),
        "emissivity": float(rust["emissivity"]),
        "oracle": RAD_ORACLE,
        "l0_cites": ["SK-12", "SK-10", "HEIKEN-L0-05"],
        "honesty": {
            "radiative_from_on_catalog": True,
            "catalog_mirror_of_rust": True,
            "python_not_independent_oracle": True,
            "not_measured": True,
        },
    }


def thermal_time_constant_s(
    *,
    thickness_m: float,
    k_w_mk: float = 0.022,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = bind or load_transient_bind()
    tm = data.get("regolith_thermal_mass") or {}
    rho = float(tm.get("rho_kg_m3") or 1600.0)
    cp = float(tm.get("cp_j_kg_k") or 800.0)
    k = max(k_w_mk, 1e-9)
    tau = rho * cp * thickness_m / k
    return {
        "thickness_m": thickness_m,
        "rho_kg_m3": rho,
        "cp_j_kg_k": cp,
        "k_w_mk": k,
        "tau_s": round(tau, 2),
        "oracle": str(data.get("oracle") or "CITED_BIND"),
    }


def transient_junction_swing_k(
    delta_steady_k: float,
    *,
    thickness_m: float,
    k_w_mk: float = 0.022,
    period_h: float | None = None,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """L5 lumped first-order attenuation vs L1 steady swing."""
    data = bind or load_transient_bind()
    half_period_h = float(period_h if period_h is not None else data.get("lunar_half_period_h") or 354.0)
    tau_row = thermal_time_constant_s(thickness_m=thickness_m, k_w_mk=k_w_mk, bind=data)
    tau = float(tau_row["tau_s"])
    omega = 2.0 * math.pi / max(half_period_h * 3600.0, 1.0)
    denom = math.sqrt(1.0 + (omega * tau) ** 2)
    a_transient = delta_steady_k / denom
    phase_rad = math.atan(omega * tau)
    return {
        "delta_steady_k": round(delta_steady_k, 6),
        "delta_transient_k": round(a_transient, 6),
        "attenuation_ratio": round(a_transient / max(delta_steady_k, 1e-12), 6),
        "phase_lag_rad": round(phase_rad, 6),
        "period_h": half_period_h,
        "tau_s": tau,
        "thickness_m": thickness_m,
        "oracle": "CITED_BIND",
        "l0_cites": ["SK-16", "HEIKEN-L0-05", "GAP-MR-13"],
    }


def evaluate_l5_thermal_path(
    *,
    embed_class: str = "lc2_micro",
    fgm_branch: str = "A",
    regolith_rho_branch: str = "A",
) -> dict[str, Any]:
    l1 = package_thermal_path_dict(fgm_branch=fgm_branch, regolith_rho_branch=regolith_rho_branch)  # type: ignore[arg-type]
    delta_steady = float(l1["delta_junction_k"])
    t_bind = load_transient_bind()
    stacks = t_bind.get("stack_thickness_classes_m") or {}
    thickness = float(stacks.get(embed_class) or stacks.get("lc2_micro") or 0.052)
    mat = str(l1.get("outer_shell_material_id") or "highland_regolith_loose")
    if embed_class == "lc2_micro":
        k = 0.8  # inner FGM shell lane — junction swing dominated by package not burial
        thickness = 0.052
    elif embed_class == "habitat_shield":
        k = float(effective_k_w_mk(mat, t_k=220.0)["k_w_mk"])
        thickness = float(stacks.get("habitat_shield") or 2.55)
    else:
        k_row = effective_k_w_mk(mat, t_k=float(l1.get("t_die_mean_k") or 220.0))
        k = float(k_row["k_w_mk"])
    l5 = transient_junction_swing_k(delta_steady, thickness_m=thickness, k_w_mk=k)
    rim_rad = radiative_net_flux_w_m2(220.0, zone="rim_sun")
    psr_rad = radiative_net_flux_w_m2(70.0, zone="psr_floor")
    return {
        "embed_class": embed_class,
        "l1_delta_junction_k": delta_steady,
        "l5_delta_junction_k": l5["delta_transient_k"],
        "l5_attenuation_ratio": l5["attenuation_ratio"],
        "stack_thickness_m": thickness,
        "radiative_rim": rim_rad,
        "radiative_psr": psr_rad,
        "rim_higher_radiative_loss": rim_rad["q_rad_w_m2"] > psr_rad["q_rad_w_m2"],
        "oracle": "CITED_BIND",
        "l0_cites": list(dict.fromkeys(list(l1.get("l0_cites") or []) + list(l5.get("l0_cites") or []))),
    }


def compare_l1_vs_l5_thermal_paths() -> dict[str, Any]:
    thin = evaluate_l5_thermal_path(embed_class="lc2_micro")
    thick = evaluate_l5_thermal_path(embed_class="habitat_shield")
    thin_ratio = float(thin["l5_attenuation_ratio"])
    thick_ratio = float(thick["l5_attenuation_ratio"])
    thin_agree = abs(1.0 - thin_ratio) <= 0.10
    thick_atten = thick_ratio <= 0.85
    return {
        "compare_id": "L1_L5_THERMAL_FALSIFIER_COMPARE_v1",
        "thin_lc2_micro": thin,
        "thick_habitat_shield": thick,
        "thin_l1_l5_agree_within_10pct": thin_agree,
        "thick_l5_attenuates_ge_15pct": thick_atten,
        "variants_diverge": thin_ratio != thick_ratio,
        "falsifier_pass": thin_agree and thick_atten and thin["rim_higher_radiative_loss"],
        "oracle": "CITED_BIND",
        "binds": [
            "results/platform_bpass/moon/THERMAL_TRANSIENT_BIND_v1.json",
            "results/platform_bpass/moon/VACUUM_RADIATIVE_BC_BIND_v1.json",
        ],
        "note": "L5 lumped harness — not Maxwell FEM; shows when 1D steady over-estimates junction swing",
    }
