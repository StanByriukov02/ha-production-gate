"""F5 foundation fold — Dual closed_loop carries full rust/honesty stack.

Makes the closed_loop receipt a self-contained Dual thermometer:
  physics honesty + energy teaching-slice honesty → closed_loop kpi/honesty

Not MEASURED. No new laws.
"""
from __future__ import annotations

from typing import Any

# Minimum Dual rust stack that must be true on lunar_scout closed_loop.
REQUIRED_RUST_FLAGS: tuple[str, ...] = (
    "bekker_from_rust",
    "drive_chain_from_rust",
    "env_budget_from_rust",
    "env_storm_from_integrator",
    "traverse_mechanical_from_bekker",
    "slope_rut_from_rust",
    "dust_envelope_from_rust",
    "materials_thermal_from_rust",
    "orbit_residual_from_rust",
    "ballistics_kepler_from_rust",
    "thermal_world_from_rust",
    "thermal_column_from_rust",
    "isru_sinter_from_rust",
    "atm_drag_from_rust",
    "acoustic_from_rust",
    "li_qc_from_rust",
    "albedo_dose_from_rust",
    "dust_ingress_from_rust",
    "janosi_from_rust",
    "janosi_p_from_bekker_contact",
    "radiation_rate_from_rust",
    "regolith_thermal_from_rust",
    "fatigue_optics_from_rust",
    "spent_dual_share_only",
    "envelope_refuse",
)


def fold_foundation_into_closed_loop(
    closed_loop: dict[str, Any],
    *,
    physics: dict[str, Any] | None,
    energy_claim: dict[str, Any] | None,
) -> dict[str, Any]:
    """Promote physics+energy Dual honesty onto closed_loop thermometer."""
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    honesty = dict(out.get("honesty") or {})
    ph = (physics.get("honesty") if isinstance(physics, dict) else None) or {}
    eh = (energy_claim.get("honesty") if isinstance(energy_claim, dict) else None) or {}
    tw = (
        physics.get("thermal_world")
        if isinstance(physics, dict) and isinstance(physics.get("thermal_world"), dict)
        else {}
    )
    tw_h = (tw.get("honesty") if isinstance(tw, dict) else None) or {}

    # Promote missing Dual rust flags from physics honesty onto closed_loop.
    promote = (
        "bekker_from_rust",
        "drive_chain_from_rust",
        "env_budget_from_rust",
        "env_storm_from_integrator",
        "traverse_mechanical_from_bekker",
        "slope_rut_from_rust",
        "dust_envelope_from_rust",
        "orbit_residual_from_rust",
        "spent_dual_share_only",
        "janosi_p_from_bekker_contact",
    )
    for key in promote:
        if key not in kpi and key in ph:
            kpi[key] = bool(ph.get(key))
        if key not in honesty and key in ph:
            honesty[key] = bool(ph.get(key))

    # Energy conservation honesty (F3).
    honesty["teaching_slice_stack"] = bool(eh.get("teaching_slice_stack"))
    honesty["no_silent_spent_clamp"] = bool(eh.get("no_silent_spent_clamp"))
    honesty["si_joule_calorimeter"] = bool(eh.get("si_joule_calorimeter", False))
    honesty["budget_is_ledger_frame_not_si_sum_cap"] = bool(
        eh.get("budget_is_ledger_frame_not_si_sum_cap")
    )
    kpi["teaching_slice_stack"] = honesty["teaching_slice_stack"]
    kpi["no_silent_spent_clamp"] = honesty["no_silent_spent_clamp"]

    # Thermal column Dual: Rust only (F3).
    honesty["column_oracle_rust_only"] = bool(tw_h.get("column_oracle_rust_only"))
    honesty["python_picard_not_on_dual_path"] = bool(tw_h.get("python_picard_not_on_dual_path"))
    kpi["column_oracle_rust_only"] = honesty["column_oracle_rust_only"]
    kpi["python_picard_not_on_dual_path"] = honesty["python_picard_not_on_dual_path"]
    if tw.get("column_oracle") is not None:
        kpi["column_oracle"] = tw.get("column_oracle")
    if tw.get("column_material_id") is not None:
        kpi["column_material_id"] = tw.get("column_material_id")

    # Envelope refuse Dual (published GCR/SPE) — surface on thermometer.
    env = (
        physics.get("envelope_refuse")
        if isinstance(physics, dict) and isinstance(physics.get("envelope_refuse"), dict)
        else None
    )
    if isinstance(env, dict):
        kpi["envelope_refuse"] = True
        kpi["inside_envelope"] = bool(env.get("inside_envelope"))
        kpi["envelope_id"] = env.get("envelope_id")
        honesty["envelope_refuse"] = True
        honesty["inside_envelope"] = bool(env.get("inside_envelope"))
        honesty["not_creme_fem"] = True

    bag = {**kpi, **honesty, **ph}
    if isinstance(env, dict):
        bag["envelope_refuse"] = True
    missing = [k for k in REQUIRED_RUST_FLAGS if not bag.get(k)]
    complete = len(missing) == 0
    honesty["foundation_rust_stack_complete"] = complete
    honesty["foundation_rust_stack_missing"] = missing
    honesty["python_theater_off_dual"] = bool(
        honesty.get("python_picard_not_on_dual_path")
    ) and bool(honesty.get("spent_dual_share_only") or kpi.get("spent_dual_share_only"))
    honesty["foundation_f5"] = True
    kpi["foundation_rust_stack_complete"] = complete

    out["kpi"] = kpi
    out["honesty"] = honesty
    return out
