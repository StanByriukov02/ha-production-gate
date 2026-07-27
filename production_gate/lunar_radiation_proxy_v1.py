"""Lunar south-pole radiation dose proxy — Maxwell-class slot, not full FEM.

Annual class constants live in ON catalog (fixtures/.../radiation_rate_on_v1.json).
Timestep window math is Rust `ha-physics-gate radiation-rate` (Python glue only).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from production_gate.radiation_rate_on_v1 import (
    ORACLE as RATE_ORACLE,
    evaluate_radiation_rate,
    load_radiation_rate_catalog,
)

_DEFAULT_SITE = "polar_surface"


def _site_row(site_id: str = _DEFAULT_SITE) -> dict[str, Any]:
    cat = load_radiation_rate_catalog()
    sites = cat.get("sites") or {}
    row = sites.get(site_id) or sites.get(_DEFAULT_SITE) or {}
    if not row:
        raise KeyError(f"radiation rate catalog missing site={site_id}")
    return row


@dataclass(frozen=True)
class RadiationProxyResult:
    annual_dose_gy: float
    mission_dose_gy: float
    see_rate_per_year: float
    dose_within_budget: bool
    see_within_budget: bool
    l0_cites: tuple[str, ...]
    oracle: str = "PROXY_CREME_CLASS"
    note: str = "Maxwell FEM PARK — dose/SEE class proxy for PSE hop"
    rate_oracle: str = RATE_ORACLE
    site_id: str = _DEFAULT_SITE


def evaluate_radiation_proxy(
    *,
    mission_years: float = 1.0,
    site_id: str = _DEFAULT_SITE,
) -> RadiationProxyResult:
    row = _site_row(site_id)
    if "annual_dose_gy" not in row:
        raise KeyError(f"radiation site={site_id} missing annual_dose_gy")
    if "annual_see_per_year" not in row:
        raise KeyError(f"radiation site={site_id} missing annual_see_per_year (no airborne SEE)")
    annual = float(row["annual_dose_gy"])
    see = float(row["annual_see_per_year"])
    mission_dose = annual * mission_years
    # Budgets are catalog-owned; missing → fail closed (not within), never invent.
    budget = row.get("mission_budget_gy")
    see_budget = row.get("see_budget_per_year")
    dose_ok = budget is not None and mission_dose <= float(budget)
    see_ok = see_budget is not None and see <= float(see_budget)
    return RadiationProxyResult(
        annual_dose_gy=annual,
        mission_dose_gy=round(mission_dose, 4),
        see_rate_per_year=see,
        dose_within_budget=dose_ok,
        see_within_budget=see_ok,
        l0_cites=("SK-07", "E-01", "E-03"),
        site_id=site_id,
        note=str(row.get("note") or "Maxwell FEM PARK — dose/SEE class proxy for PSE hop"),
    )


def evaluate_coupled_radiation_proxy(
    *,
    mission_years: float = 1.0,
    shield_g_cm2: float = 0.0,
    site_class: str = "highland_regolith",
    rate_site_id: str = _DEFAULT_SITE,
) -> dict[str, object]:
    """Incident + albedo split via ALBEDO_DOSE_FRACTION_BIND_v1 (SELINE surrogate)."""
    from production_gate.lunar_albedo_dose_v1 import albedo_dose_dict

    rad = evaluate_radiation_proxy(mission_years=mission_years, site_id=rate_site_id)
    coupled = albedo_dose_dict(
        mission_years=mission_years,
        shield_g_cm2=shield_g_cm2,
        site_class=site_class,  # type: ignore[arg-type]
        rad=rad,
    )
    budget_row = _site_row(rate_site_id)
    mission_budget = budget_row.get("mission_budget_gy")
    see_budget = budget_row.get("see_budget_per_year")
    total = float(coupled["total_dose_gy"])
    see_rate = float(coupled["see_rate_per_year"])
    return {
        "annual_dose_gy": rad.annual_dose_gy,
        "mission_dose_gy": coupled["total_dose_gy"],
        "incident_dose_gy": coupled["incident_dose_gy"],
        "albedo_dose_gy": coupled["albedo_dose_gy"],
        "albedo_fraction": coupled["albedo_fraction"],
        "see_rate_per_year": coupled["see_rate_per_year"],
        "dose_within_budget": mission_budget is not None and total <= float(mission_budget),
        "see_within_budget": see_budget is not None and see_rate <= float(see_budget),
        "shield_g_cm2": shield_g_cm2,
        "site_class": site_class,
        "rate_site_id": rate_site_id,
        "oracle": coupled["oracle"],
        "rate_oracle": RATE_ORACLE,
        "tier": coupled["tier"],
        "l0_cites": coupled["l0_cites"],
        "albedo_bind": coupled["bind"],
        "note": coupled["note"],
    }


def rust_window_dose(
    *,
    annual_dose_gy: float,
    annual_see_per_year: float,
    dt_h: float,
    flare_scale: float,
    flare_lo: float = 1.0,
    flare_hi: float = 12.0,
) -> dict[str, Any]:
    """Timestep dose/SEE from Rust rate law — not Python arithmetic theater."""
    return evaluate_radiation_rate(
        dt_h=dt_h,
        flare_scale=flare_scale,
        annual_dose_gy=annual_dose_gy,
        annual_see_per_year=annual_see_per_year,
        flare_lo=flare_lo,
        flare_hi=flare_hi,
        site_id="coupled_window",
    )
