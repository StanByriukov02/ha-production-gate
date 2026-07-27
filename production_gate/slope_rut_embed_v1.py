"""E4 slope+rut embed — Mohr FS + multipass rut → Dual traverse/risk.

Teaching: Safe mild slope + firm multipass keeps traverse; Hostile steep slope
(FS<1) and soft multi-pass rut flips traverse_feasible / sinkage_risk Dual.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]

# Catalog dual anchors (mohr_coulomb_slope_on_v1 / multipass_rut_on_v1).
THETA_SAFE_DEG = 15.0
THETA_HOSTILE_DEG = 45.0
RUT_SAFE_SOIL = "firm_lab"
RUT_HOSTILE_SOIL = "soft_hostile"
N_PASSES_DUAL = 10.0
# Teaching: multipass z_n above this (mm) raises sinkage_risk Dual.
RUT_SINKAGE_RISK_MM = 40.0


def evaluate_slope_rut(*, condition: ConditionId) -> dict[str, Any]:
    """Evaluate Mohr slope + multipass rut from Rust for Dual condition."""
    from production_gate.mohr_coulomb_slope_on_v1 import evaluate_mohr_slope
    from production_gate.multipass_rut_on_v1 import evaluate_multipass_rut

    if condition == "hostile":
        theta = THETA_HOSTILE_DEG
        soil_id = RUT_HOSTILE_SOIL
    else:
        theta = THETA_SAFE_DEG
        soil_id = RUT_SAFE_SOIL

    slope = evaluate_mohr_slope(theta_deg=theta)
    rut = evaluate_multipass_rut(soil_id=soil_id, n_passes=N_PASSES_DUAL)
    fs = float(slope["fs"])
    stable = bool(slope.get("stable"))
    z_n_m = float(rut["z_n_m"])
    z_n_mm = z_n_m * 1000.0
    growth = float(rut.get("rut_growth_ratio") or 1.0)
    rut_risk = z_n_mm >= RUT_SINKAGE_RISK_MM or growth >= 2.0
    slope_ok = stable and fs >= 1.0
    # Dual consequence: Hostile steep + soft rut refuses traverse.
    traverse_ok = slope_ok and not rut_risk
    return {
        "schema": "ha_slope_rut_embed_v1",
        "condition": condition,
        "theta_deg": theta,
        "fs": fs,
        "slope_stable": stable,
        "slope_ok": slope_ok,
        "rut_soil_id": soil_id,
        "n_passes": N_PASSES_DUAL,
        "z_n_m": z_n_m,
        "z_n_mm": z_n_mm,
        "rut_growth_ratio": growth,
        "rc_n_n": float(rut.get("rc_n_n") or 0.0),
        "rut_risk": rut_risk,
        "traverse_ok": traverse_ok,
        "slope_oracle": slope.get("oracle"),
        "multipass_oracle": rut.get("oracle"),
        "honesty": {
            "slope_rut_from_rust": True,
            "mohr_slope_from_rust": True,
            "multipass_from_rust": True,
            "not_measured": True,
            "not_3d_fem": True,
            "not_densification_fem": True,
        },
    }


def attach_slope_rut_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
) -> dict[str, Any]:
    """Attach slope+rut embed; may flip traverse_feasible / sinkage_risk Dual."""
    out = dict(physics)
    block = evaluate_slope_rut(condition=condition)
    out["slope_rut"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "slope_rut_from_rust": True,
            "mohr_slope_from_rust": True,
            "multipass_from_rust": True,
        }
    )
    out["honesty"] = honesty
    out["slope_fs"] = float(block["fs"])
    out["slope_stable"] = bool(block["slope_stable"])
    out["rut_z_n_mm"] = float(block["z_n_mm"])
    out["rut_growth_ratio"] = float(block["rut_growth_ratio"])
    out["slope_rut_traverse_ok"] = bool(block["traverse_ok"])
    if not block["traverse_ok"]:
        out["traverse_feasible"] = False
        out["sinkage_risk"] = True
    elif block["rut_risk"] or not block["slope_ok"]:
        out["sinkage_risk"] = True
    return out
