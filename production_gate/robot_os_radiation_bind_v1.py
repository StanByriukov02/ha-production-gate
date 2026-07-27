"""Radiation → OS bind v1 — FET/SEE wear drives kernel RECOVER.

Source: lunar_radiation_fet_v1 · RADIATION_FET_COEFF_BIND_v1.json
proof_tier: RADIATION_SIM_BIND — not MEASURED in-flight.
TABU: hardcoded delta_vth_mv · fake SEE without inject flag.
"""
from __future__ import annotations

from typing import Any

PROOF_TIER = "RADIATION_SIM_BIND"
ORACLE = "CITED_BIND"
DEFAULT_MISSION_YEARS = 1.0
DEFAULT_SHIELD_G_CM2 = 10.0
DEFAULT_SITE_CLASS = "highland_regolith"


def _profile_traverse_m(profile_id: str) -> float:
    from production_gate.chip_mission_situation_inherit_v1 import PROFILES

    return float(PROFILES[profile_id]["traverse_m"])


def wear_at_traverse_fraction(
    fraction: float,
    *,
    mission_years: float = DEFAULT_MISSION_YEARS,
    shield_g_cm2: float = DEFAULT_SHIELD_G_CM2,
    site_class: str = DEFAULT_SITE_CLASS,
) -> dict[str, Any]:
    from production_gate.lunar_radiation_fet_v1 import radiation_fet_wear_dict

    frac = max(0.0, min(1.0, float(fraction)))
    return radiation_fet_wear_dict(
        mission_years=mission_years * frac,
        shield_g_cm2=shield_g_cm2,
        site_class=site_class,
    )


def init_radiation_bind(
    state: dict[str, Any],
    *,
    mission_years: float = DEFAULT_MISSION_YEARS,
    shield_g_cm2: float = DEFAULT_SHIELD_G_CM2,
    site_class: str = DEFAULT_SITE_CLASS,
    enabled: bool = True,
) -> dict[str, Any]:
    state["radiation_bind"] = {
        "enabled": enabled,
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
        "mission_years": mission_years,
        "shield_g_cm2": shield_g_cm2,
        "site_class": site_class,
        "accum_delta_vth_mv": 0.0,
        "see_events": 0,
    }
    state["radiation_inject"] = {}
    return state


def inject_see_event(state: dict[str, Any], *, see_mv_spike: float = 15.0) -> dict[str, Any]:
    """Test-only SEE spike — consumed on first radiation tick."""
    state["radiation_inject"] = {
        "see_event": True,
        "see_mv_spike": float(see_mv_spike),
        "consumed": False,
    }
    return state


def apply_radiation_tick(state: dict[str, Any], carrier_id: str) -> dict[str, Any]:
    """Update radiation accumulator; return tick row. May set carrier recover."""
    bind = state.get("radiation_bind") or {}
    if not bind.get("enabled"):
        return {"wired_to_kernel": False, "skipped": True}

    profile_id = str(state.get("profile_id", "lunar_crater_5km"))
    carrier = state["carriers"][carrier_id]
    traverse_m = _profile_traverse_m(profile_id)
    cursor_m = float(carrier.get("cursor_m", 0.0))
    fraction = cursor_m / traverse_m if traverse_m > 0 else 0.0

    row = wear_at_traverse_fraction(
        fraction,
        mission_years=float(bind.get("mission_years") or DEFAULT_MISSION_YEARS),
        shield_g_cm2=float(bind.get("shield_g_cm2") or DEFAULT_SHIELD_G_CM2),
        site_class=str(bind.get("site_class") or DEFAULT_SITE_CLASS),
    )
    budget_mv = float(row.get("radiation_wear_budget_mv") or 12.0)
    delta_mv = float(row.get("radiation_delta_vth_mv") or 0.0)

    inj = state.get("radiation_inject") or {}
    see_spike = 0.0
    if inj.get("see_event") and not inj.get("consumed"):
        see_spike = float(inj.get("see_mv_spike") or 0.0)
        inj["consumed"] = True
        bind["see_events"] = int(bind.get("see_events") or 0) + 1
        state["radiation_inject"] = inj

    total_mv = round(delta_mv + see_spike, 4)
    bind["accum_delta_vth_mv"] = total_mv
    state["radiation_bind"] = bind

    over_budget = total_mv > budget_mv
    tick_row: dict[str, Any] = {
        "wired_to_kernel": True,
        "proof_tier": PROOF_TIER,
        "oracle": row.get("oracle"),
        "traverse_fraction": round(fraction, 4),
        "radiation_delta_vth_mv": total_mv,
        "radiation_wear_budget_mv": budget_mv,
        "within_budget": not over_budget,
        "see_spike_mv": see_spike,
        "see_events_total": bind.get("see_events"),
        "trigger_recover": over_budget,
        "recover_reason": "radiation_see_budget" if over_budget else None,
    }
    carrier["radiation_tick"] = tick_row

    if over_budget:
        carrier["command"] = "recover"
        carrier["phase"] = "recover"
        carrier["recover_reason"] = "radiation_see_budget"

    return tick_row


def radiation_summary(state: dict[str, Any]) -> dict[str, Any]:
    bind = state.get("radiation_bind") or {}
    if not bind.get("enabled"):
        return {
            "wired_to_kernel": False,
            "wired_to_hal": False,
            "wired_to_coordinator": False,
        }
    fleet_degrade = state.get("fleet_degrade") or {}
    return {
        "wired_to_kernel": True,
        "wired_to_hal": True,
        "wired_to_coordinator": bool(fleet_degrade.get("active")),
        "proof_tier": PROOF_TIER,
        "oracle": bind.get("oracle"),
        "accum_delta_vth_mv": bind.get("accum_delta_vth_mv"),
        "see_events": bind.get("see_events"),
        "mission_years": bind.get("mission_years"),
    }
