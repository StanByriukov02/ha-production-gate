"""Radiation dose + SEE (incident + albedo neutron) → FET ΔVth — cited coeff bind."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dogfood_platform.lunar_radiation_proxy_v1 import RadiationProxyResult, evaluate_coupled_radiation_proxy

from dogfood_platform.open_seed_paths_v1 import radiation_fet_coeff_bind_path

_REPO = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RadiationFetWearResult:
    mission_dose_gy: float
    incident_dose_gy: float
    albedo_dose_gy: float
    albedo_fraction: float
    see_events_total: float
    see_incident_events: float
    see_albedo_events: float
    dose_component_mv: float
    see_incident_mv: float
    see_albedo_mv: float
    see_component_mv: float
    radiation_delta_vth_mv: float
    within_budget: bool
    oracle: str
    l0_cites: tuple[str, ...]
    note: str
    coeff_bind_id: str


def load_radiation_fet_coeff_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or radiation_fet_coeff_bind_path(_REPO)
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def _coupled_rad(
    rad: RadiationProxyResult | dict[str, Any] | None,
    *,
    mission_years: float,
    shield_g_cm2: float,
    site_class: str,
) -> dict[str, Any]:
    if isinstance(rad, dict) and "albedo_fraction" in rad:
        if "mission_dose_gy" not in rad and "total_dose_gy" in rad:
            out = dict(rad)
            out["mission_dose_gy"] = out["total_dose_gy"]
            if "see_rate_per_year" not in out:
                from dogfood_platform.lunar_albedo_dose_v1 import evaluate_coupled_surface_dose

                row = evaluate_coupled_surface_dose(
                    mission_years=mission_years,
                    shield_g_cm2=shield_g_cm2,
                    site_class=site_class,  # type: ignore[arg-type]
                )
                out["see_rate_per_year"] = row.see_rate_per_year
            return out
        return rad
    if isinstance(rad, RadiationProxyResult):
        mission_years = rad.mission_dose_gy / max(rad.annual_dose_gy, 1e-9)
    return evaluate_coupled_radiation_proxy(
        mission_years=mission_years,
        shield_g_cm2=shield_g_cm2,
        site_class=site_class,
    )


def _base_see_rate() -> float:
    """SEE floor from radiation_rate ON catalog — not airborne 0.12."""
    from dogfood_platform.lunar_albedo_dose_v1 import load_albedo_dose_bind
    from dogfood_platform.radiation_rate_on_v1 import load_radiation_rate_catalog

    cfg = load_albedo_dose_bind().get("see_albedo_coupling") or {}
    if "base_see_per_yr" in cfg:
        return float(cfg["base_see_per_yr"])
    cat = load_radiation_rate_catalog()
    polar = (cat.get("sites") or {}).get("polar_surface") or {}
    if "annual_see_per_year" not in polar:
        raise KeyError("radiation_rate_on_v1 polar_surface missing annual_see_per_year")
    return float(polar["annual_see_per_year"])


def compute_radiation_fet_wear(
    rad: RadiationProxyResult | dict[str, Any] | None = None,
    *,
    mission_years: float = 1.0,
    shield_g_cm2: float = 0.0,
    site_class: str = "highland_regolith",
    coeff_bind: dict[str, Any] | None = None,
) -> RadiationFetWearResult:
    bind = coeff_bind or load_radiation_fet_coeff_bind()
    coeffs = bind.get("coeffs") or {}
    dose_per_gy = float((coeffs.get("dose_mv_per_gy") or {}).get("value") or 0.0)
    see_per_event = float((coeffs.get("see_mv_per_event") or {}).get("value") or 0.0)
    see_albedo_per_gy = float((coeffs.get("see_albedo_mv_per_gy") or {}).get("value") or 0.0)
    see_albedo_per_event = float((coeffs.get("see_albedo_mv_per_event") or {}).get("value") or 0.0)
    budget = float(bind.get("radiation_wear_budget_mv") or 12.0)

    coupled = _coupled_rad(rad, mission_years=mission_years, shield_g_cm2=shield_g_cm2, site_class=site_class)
    dose = float(coupled["mission_dose_gy"])
    incident = float(coupled.get("incident_dose_gy") or dose)
    albedo = float(coupled.get("albedo_dose_gy") or 0.0)
    f_alb = float(coupled.get("albedo_fraction") or 0.0)
    see_rate = float(coupled.get("see_rate_per_year") or 0.0)
    cites = list(coupled.get("l0_cites") or [])

    base_see = _base_see_rate()
    see_total = see_rate * mission_years
    see_incident_events = base_see * mission_years
    see_albedo_events = max(0.0, see_total - see_incident_events)

    for key in ("dose_mv_per_gy", "see_mv_per_event", "see_albedo_mv_per_gy", "see_albedo_mv_per_event"):
        row = coeffs.get(key) or {}
        cite = row.get("cite") or {}
        if cite.get("formula_id"):
            cites.append(str(cite["formula_id"]))

    dose_mv = round(dose_per_gy * dose, 4)
    see_incident_mv = round(see_per_event * see_incident_events, 4)
    see_albedo_mv = round(see_albedo_per_gy * albedo + see_albedo_per_event * see_albedo_events, 4)
    see_mv = round(see_incident_mv + see_albedo_mv, 4)
    total = round(dose_mv + see_mv, 4)
    return RadiationFetWearResult(
        mission_dose_gy=dose,
        incident_dose_gy=round(incident, 6),
        albedo_dose_gy=round(albedo, 6),
        albedo_fraction=f_alb,
        see_events_total=round(see_total, 4),
        see_incident_events=round(see_incident_events, 4),
        see_albedo_events=round(see_albedo_events, 4),
        dose_component_mv=dose_mv,
        see_incident_mv=see_incident_mv,
        see_albedo_mv=see_albedo_mv,
        see_component_mv=see_mv,
        radiation_delta_vth_mv=total,
        within_budget=total <= budget,
        oracle=str(bind.get("oracle") or "CITED_BIND"),
        l0_cites=tuple(dict.fromkeys(cites + ["EXP-M4-01-FET-CLASS", "L0-SEL-01"])),
        note="TID + incident SEE + albedo neutron row via RADIATION_FET_COEFF_BIND_v1",
        coeff_bind_id=str(bind.get("bind_id") or "radiation_fet_coeff_bind_v1"),
    )


def radiation_fet_wear_dict(
    rad: RadiationProxyResult | dict[str, Any] | None = None,
    *,
    mission_years: float = 1.0,
    shield_g_cm2: float = 0.0,
    site_class: str = "highland_regolith",
    coeff_bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bind = coeff_bind or load_radiation_fet_coeff_bind()
    r = compute_radiation_fet_wear(
        rad,
        mission_years=mission_years,
        shield_g_cm2=shield_g_cm2,
        site_class=site_class,
        coeff_bind=bind,
    )
    budget = float(bind.get("radiation_wear_budget_mv") or 12.0)
    return {
        "mission_dose_gy": r.mission_dose_gy,
        "incident_dose_gy": r.incident_dose_gy,
        "albedo_dose_gy": r.albedo_dose_gy,
        "albedo_fraction": r.albedo_fraction,
        "see_events_total": r.see_events_total,
        "see_incident_events": r.see_incident_events,
        "see_albedo_events": r.see_albedo_events,
        "dose_component_mv": r.dose_component_mv,
        "see_incident_mv": r.see_incident_mv,
        "see_albedo_mv": r.see_albedo_mv,
        "see_component_mv": r.see_component_mv,
        "radiation_delta_vth_mv": r.radiation_delta_vth_mv,
        "radiation_wear_budget_mv": budget,
        "within_budget": r.within_budget,
        "oracle": r.oracle,
        "coeff_bind_id": r.coeff_bind_id,
        "coeff_bind": "results/platform_bpass/moon/RADIATION_FET_COEFF_BIND_v1.json",
        "albedo_row_active": r.see_albedo_mv > 0.0,
        "l0_cites": list(r.l0_cites),
        "note": r.note,
    }
