"""U4 radiation env_state adapter — coupled albedo + fet wear for all worlds."""
from __future__ import annotations

from typing import Any

from production_gate.lunar_radiation_fet_v1 import load_radiation_fet_coeff_bind, radiation_fet_wear_dict
from production_gate.lunar_radiation_proxy_v1 import evaluate_coupled_radiation_proxy


def _require_catalog_see() -> float:
    from production_gate.radiation_rate_on_v1 import load_radiation_rate_catalog

    polar = (load_radiation_rate_catalog().get("sites") or {}).get("polar_surface") or {}
    if "annual_see_per_year" not in polar:
        raise KeyError("radiation_rate_on_v1 polar_surface missing annual_see_per_year")
    return float(polar["annual_see_per_year"])


def radiation_env_defaults(
    *,
    mission_years: float = 1.0,
    shield_g_cm2: float = 0.0,
    site_class: str = "highland_regolith",
) -> dict[str, float | str]:
    coupled = evaluate_coupled_radiation_proxy(
        mission_years=mission_years,
        shield_g_cm2=shield_g_cm2,
        site_class=site_class,
    )
    return {
        "dose_gy": float(coupled["mission_dose_gy"]),
        "incident_dose_gy": float(coupled["incident_dose_gy"]),
        "albedo_dose_gy": float(coupled["albedo_dose_gy"]),
        "albedo_fraction": float(coupled["albedo_fraction"]),
        "see_rate_1_per_yr": float(coupled["see_rate_per_year"]),
        "shield_areal_g_cm2": float(shield_g_cm2),
        "tier": str(coupled.get("tier") or "PROXY_CHAT"),
    }


def radiation_fet_from_env(
    env_radiation: dict[str, Any] | None = None,
    *,
    mission_years: float = 1.0,
    shield_g_cm2: float | None = None,
    site_class: str = "highland_regolith",
) -> dict[str, Any]:
    if env_radiation:
        shield = float(
            shield_g_cm2 if shield_g_cm2 is not None else env_radiation.get("shield_areal_g_cm2") or 0.0
        )
        coupled = {
            "mission_dose_gy": float(env_radiation.get("dose_gy") or 0.0),
            "incident_dose_gy": float(env_radiation.get("incident_dose_gy") or 0.0),
            "albedo_dose_gy": float(env_radiation.get("albedo_dose_gy") or 0.0),
            "albedo_fraction": float(env_radiation.get("albedo_fraction") or 0.0),
            "see_rate_per_year": float(
                env_radiation["see_rate_1_per_yr"]
                if "see_rate_1_per_yr" in env_radiation
                else (_require_catalog_see())
            ),
            "l0_cites": list(env_radiation.get("l0_cites") or []),
        }
        return radiation_fet_wear_dict(
            coupled,
            mission_years=mission_years,
            shield_g_cm2=shield,
            site_class=site_class,
        )
    shield_val = 0.0 if shield_g_cm2 is None else shield_g_cm2
    coupled = evaluate_coupled_radiation_proxy(
        mission_years=mission_years,
        shield_g_cm2=shield_val,
        site_class=site_class,
    )
    return radiation_fet_wear_dict(
        coupled,
        mission_years=mission_years,
        shield_g_cm2=shield_val,
        site_class=site_class,
    )


def radiation_state_delta(
    *,
    mission_years: float = 1.0,
    shield_g_cm2: float = 0.0,
    site_class: str = "highland_regolith",
    annual_dose_gy: float | None = None,
    see_rate_per_year: float | None = None,
) -> dict[str, Any]:
    if annual_dose_gy is not None:
        base = evaluate_coupled_radiation_proxy(
            mission_years=mission_years,
            shield_g_cm2=shield_g_cm2,
            site_class=site_class,
        )
        scale = annual_dose_gy / max(float(base["annual_dose_gy"]), 1e-9)
        coupled = dict(base)
        coupled["mission_dose_gy"] = float(base["mission_dose_gy"]) * scale
        coupled["incident_dose_gy"] = float(base["incident_dose_gy"]) * scale
        coupled["albedo_dose_gy"] = float(base["albedo_dose_gy"]) * scale
        if see_rate_per_year is not None:
            coupled["see_rate_per_year"] = see_rate_per_year
        fet = radiation_fet_wear_dict(
            coupled,
            mission_years=mission_years,
            shield_g_cm2=shield_g_cm2,
            site_class=site_class,
        )
    else:
        fet = radiation_fet_from_env(
            None,
            mission_years=mission_years,
            shield_g_cm2=shield_g_cm2,
            site_class=site_class,
        )
        coupled = evaluate_coupled_radiation_proxy(
            mission_years=mission_years,
            shield_g_cm2=shield_g_cm2,
            site_class=site_class,
        )
    return {
        "radiation": {
            "dose_gy_accum": float(fet["mission_dose_gy"]),
            "dose_gy": float(fet["mission_dose_gy"]),
            "incident_dose_gy": float(coupled["incident_dose_gy"]),
            "albedo_dose_gy": float(coupled["albedo_dose_gy"]),
            "albedo_fraction": float(coupled["albedo_fraction"]),
            "see_rate_1_per_yr": float(coupled["see_rate_per_year"]),
            "see_events": float(fet["see_events_total"]),
            "shield_areal_g_cm2": float(shield_g_cm2),
            "see_albedo_mv": float(fet["see_albedo_mv"]),
        }
    }


def moon_chip_env_radiation_bridge(
    *,
    shield_g_cm2: float = 4.0,
    site_class: str = "highland_regolith",
    mission_years: float = 1.0,
) -> dict[str, Any]:
    """Moon M3 axis → chip u-hop-radiation — shared env_state, not duplicate physics."""
    env = radiation_env_defaults(
        mission_years=mission_years,
        shield_g_cm2=shield_g_cm2,
        site_class=site_class,
    )
    fet = radiation_fet_from_env(env, mission_years=mission_years, site_class=site_class)
    return {
        "bridge_id": "moon_chip_env_radiation_bridge_v1",
        "source_world": "W_moon_shackleton_v0",
        "target_world": "W_chip",
        "env_radiation": env,
        "radiation_fet": fet,
        "hop_id": "u-hop-radiation",
        "bind_stack": [
            "ALBEDO_DOSE_FRACTION_BIND_v1.json",
            "RADIATION_FET_COEFF_BIND_v1.json",
        ],
        "oracle": fet.get("oracle"),
    }
