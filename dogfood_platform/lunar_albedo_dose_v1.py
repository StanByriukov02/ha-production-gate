"""SELINE-surrogate albedo dose — incident + albedo split with Matthia shield paradox.

Oracle: Rust `ha-physics-gate albedo-dose` (ON catalog). Hot path = catalog mirror.
Couples Zheng orbit dose classes with polar D_anchor from lunar_radiation_proxy_v1.
Not CREME FEM. Not MEASURED.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from dogfood_platform.albedo_dose_on_v1 import ORACLE as ALBEDO_ORACLE
from dogfood_platform.albedo_dose_on_v1 import albedo_from_catalog, load_albedo_dose_catalog
from dogfood_platform.lunar_radiation_proxy_v1 import RadiationProxyResult, evaluate_radiation_proxy
from dogfood_platform.open_seed_paths_v1 import albedo_dose_fraction_bind_path

_REPO = Path(__file__).resolve().parents[1]

SiteClass = Literal["highland_regolith", "mare_regolith", "magnetic_anomaly"]


@dataclass(frozen=True)
class CoupledSurfaceDoseResult:
    mission_years: float
    shield_g_cm2: float
    site_class: str
    dose_anchor_gy: float
    incident_dose_gy: float
    albedo_dose_gy: float
    total_dose_gy: float
    albedo_fraction: float
    albedo_fraction_base: float
    shield_paradox_multiplier: float
    see_rate_per_year: float
    tier: str
    oracle: str
    l0_cites: tuple[str, ...]
    note: str


def load_albedo_dose_bind(path: Path | None = None) -> dict[str, Any]:
    """Legacy evidence bind — coefficients for Dual owned by ON catalog."""
    p = path or albedo_dose_fraction_bind_path(_REPO)
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def shield_albedo_fraction_multiplier(shield_g_cm2: float, *, bind: dict[str, Any] | None = None) -> float:
    del bind
    row = albedo_from_catalog(
        site_class="highland_regolith", shield_g_cm2=shield_g_cm2, dose_anchor_gy=1.0
    )
    return float(row["fraction_paradox_multiplier"])


def shield_total_dose_multiplier(shield_g_cm2: float, *, bind: dict[str, Any] | None = None) -> float:
    del bind
    row = albedo_from_catalog(
        site_class="highland_regolith", shield_g_cm2=shield_g_cm2, dose_anchor_gy=1.0
    )
    return float(row["shield_paradox_multiplier"])


def effective_albedo_fraction(
    shield_g_cm2: float,
    *,
    site_class: SiteClass = "highland_regolith",
    bind: dict[str, Any] | None = None,
) -> float:
    del bind
    row = albedo_from_catalog(site_class=site_class, shield_g_cm2=shield_g_cm2, dose_anchor_gy=1.0)
    return float(row["albedo_fraction"])


def evaluate_coupled_surface_dose(
    *,
    mission_years: float = 1.0,
    shield_g_cm2: float = 0.0,
    site_class: SiteClass = "highland_regolith",
    rad: RadiationProxyResult | None = None,
    bind: dict[str, Any] | None = None,
) -> CoupledSurfaceDoseResult:
    del bind
    if rad is None:
        rad = evaluate_radiation_proxy(mission_years=mission_years)
    dose_anchor = rad.mission_dose_gy
    row = albedo_from_catalog(
        site_class=site_class,
        shield_g_cm2=shield_g_cm2,
        dose_anchor_gy=dose_anchor,
        see_base=float(rad.see_rate_per_year),
    )
    l0 = list(rad.l0_cites) + ["L0-SEL-01", "L0-SEL-08", "L0-ZHENG-05"]
    if shield_g_cm2 > 0:
        l0.append("MATTHIA-2024-L0-01")
    return CoupledSurfaceDoseResult(
        mission_years=mission_years,
        shield_g_cm2=shield_g_cm2,
        site_class=site_class,
        dose_anchor_gy=round(dose_anchor, 6),
        incident_dose_gy=round(float(row["incident_dose_gy"]), 6),
        albedo_dose_gy=round(float(row["albedo_dose_gy"]), 6),
        total_dose_gy=round(float(row["total_dose_gy"]), 6),
        albedo_fraction=round(float(row["albedo_fraction"]), 4),
        albedo_fraction_base=round(float(row["albedo_fraction_base"]), 4),
        shield_paradox_multiplier=round(float(row["shield_paradox_multiplier"]), 4),
        see_rate_per_year=round(float(row["see_rate_per_year"]), 4),
        tier="PROXY_CHAT",
        oracle=ALBEDO_ORACLE,
        l0_cites=tuple(dict.fromkeys(l0)),
        note="SELINE-surrogate · incident+albedo split · Matthia shield paradox PROXY · Rust oracle",
    )


def albedo_dose_dict(
    *,
    mission_years: float = 1.0,
    shield_g_cm2: float = 0.0,
    site_class: SiteClass = "highland_regolith",
    rad: RadiationProxyResult | dict[str, Any] | None = None,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del bind
    rad_obj: RadiationProxyResult | None
    if isinstance(rad, dict):
        rad_obj = None
        mission_years = float(rad.get("mission_years") or mission_years)
    else:
        rad_obj = rad
    r = evaluate_coupled_surface_dose(
        mission_years=mission_years,
        shield_g_cm2=shield_g_cm2,
        site_class=site_class,
        rad=rad_obj,
    )
    return {
        "bind_id": "albedo_dose_on_v1",
        "bind": "fixtures/open_registry/env/albedo_dose_on_v1.json",
        "mission_years": r.mission_years,
        "shield_g_cm2": r.shield_g_cm2,
        "site_class": r.site_class,
        "dose_anchor_gy": r.dose_anchor_gy,
        "incident_dose_gy": r.incident_dose_gy,
        "albedo_dose_gy": r.albedo_dose_gy,
        "total_dose_gy": r.total_dose_gy,
        "albedo_fraction": r.albedo_fraction,
        "albedo_fraction_base": r.albedo_fraction_base,
        "shield_paradox_multiplier": r.shield_paradox_multiplier,
        "see_rate_per_year": r.see_rate_per_year,
        "tier": r.tier,
        "oracle": r.oracle,
        "l0_cites": list(r.l0_cites),
        "note": r.note,
        "honesty": {
            "catalog_mirror_of_rust": True,
            "python_not_independent_oracle": True,
            "not_creme_fem": True,
            "not_measured": True,
        },
    }


def compare_shield_paradox(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    """S5 falsifier — peak shield areal density vs thin regolith."""
    del bind
    cat = load_albedo_dose_catalog()
    thin = albedo_dose_dict(shield_g_cm2=10.0)
    peak = albedo_dose_dict(shield_g_cm2=90.0)
    thick = albedo_dose_dict(shield_g_cm2=180.0)
    unshielded = albedo_dose_dict(shield_g_cm2=0.0)
    lo, hi = cat.get("l0_band") or [0.25, 0.35]
    return {
        "compare_id": "ALBEDO_SHIELD_PARADOX_COMPARE_v1",
        "unshielded": unshielded,
        "thin_10g_cm2": thin,
        "peak_90g_cm2": peak,
        "thick_180g_cm2": thick,
        "paradox_peak_exceeds_thin": peak["total_dose_gy"] > thin["total_dose_gy"],
        "unshielded_fraction_in_l0_band": lo <= unshielded["albedo_fraction"] <= hi,
        "falsifier_pass": (
            peak["total_dose_gy"] > thin["total_dose_gy"]
            and lo <= unshielded["albedo_fraction"] <= hi
        ),
        "oracle": ALBEDO_ORACLE,
        "bind": "fixtures/open_registry/env/albedo_dose_on_v1.json",
    }
