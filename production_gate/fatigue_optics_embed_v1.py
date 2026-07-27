"""E5 fatigue+optics embed — Basquin N_f + Beer-Lambert τ → closed_loop KPI Dual.

Teaching: Safe Al life + clean optics keep life/sense OK; Hostile brittle + dusty
optics shrinks N_f and transmittance on Dual run KPI — not catalog Dual alone.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]

MAT_SAFE = "al6061_safe"
MAT_HOSTILE = "brittle_hostile"
SIGMA_A_MPA = 150.0
MASS_SAFE_G_M2 = 0.0
MASS_HOSTILE_G_M2 = 2.0
# Teaching floors for Dual KPI.
N_F_LIFE_OK = 1.0e4
T_OPTICS_OK = 0.50


def evaluate_fatigue_optics(*, condition: ConditionId) -> dict[str, Any]:
    """Evaluate Basquin + optics τ from Rust for Dual condition."""
    from production_gate.fatigue_sn_on_v1 import evaluate_fatigue_sn
    from production_gate.optics_dust_tau_on_v1 import evaluate_optics_tau

    if condition == "hostile":
        mat_id = MAT_HOSTILE
        mass = MASS_HOSTILE_G_M2
    else:
        mat_id = MAT_SAFE
        mass = MASS_SAFE_G_M2

    fat = evaluate_fatigue_sn(mat_id=mat_id, sigma_a_mpa=SIGMA_A_MPA)
    opt = evaluate_optics_tau(mass_g_m2=mass)
    n_f = float(fat["n_f_cycles"])
    t = float(opt["transmittance"])
    tau = float(opt["tau"])
    life_ok = n_f >= N_F_LIFE_OK
    optics_ok = t >= T_OPTICS_OK
    sense_life_ok = life_ok and optics_ok
    return {
        "schema": "ha_fatigue_optics_embed_v1",
        "condition": condition,
        "mat_id": mat_id,
        "sigma_a_mpa": SIGMA_A_MPA,
        "n_f_cycles": n_f,
        "life_ok": life_ok,
        "mass_g_m2": mass,
        "tau": tau,
        "transmittance": t,
        "optics_ok": optics_ok,
        "sense_life_ok": sense_life_ok,
        "fatigue_oracle": fat.get("oracle"),
        "optics_oracle": opt.get("oracle"),
        "honesty": {
            "fatigue_optics_from_rust": True,
            "fatigue_from_rust": True,
            "optics_tau_from_rust": True,
            "not_measured": True,
            "not_paris_law": True,
            "not_mie_brdf": True,
        },
    }


def attach_fatigue_optics_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
) -> dict[str, Any]:
    """Attach fatigue+optics embed block for closed_loop KPI Dual."""
    out = dict(physics)
    block = evaluate_fatigue_optics(condition=condition)
    out["fatigue_optics"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "fatigue_optics_from_rust": True,
            "fatigue_from_rust": True,
            "optics_tau_from_rust": True,
        }
    )
    out["honesty"] = honesty
    out["n_f_cycles"] = float(block["n_f_cycles"])
    out["optics_transmittance"] = float(block["transmittance"])
    out["sense_life_ok"] = bool(block["sense_life_ok"])
    return out


def fold_fatigue_optics_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    """Surface Rust fatigue/optics on closed_loop KPI Dual (teaching, not floor life)."""
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("fatigue_optics")
        if isinstance(physics, dict) and isinstance(physics.get("fatigue_optics"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["fatigue_optics_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "n_f_cycles": block.get("n_f_cycles"),
            "life_ok": block.get("life_ok"),
            "optics_transmittance": block.get("transmittance"),
            "optics_tau": block.get("tau"),
            "optics_ok": block.get("optics_ok"),
            "sense_life_ok": block.get("sense_life_ok"),
            "fatigue_mat_id": block.get("mat_id"),
            "optics_mass_g_m2": block.get("mass_g_m2"),
            "fatigue_optics_from_rust": True,
            "fatigue_from_rust": True,
            "optics_tau_from_rust": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "fatigue_optics_from_rust": True,
            "fatigue_from_rust": True,
            "optics_tau_from_rust": True,
            "not_floor_life_claim": True,
        }
    )
    out["honesty"] = honesty
    return out
