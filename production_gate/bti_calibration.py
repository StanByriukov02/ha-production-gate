"""Cited ΔVth calibration — anchor scale, not synthetic PASS.

Uses HCI measured anchor (radiation-effects corpus) scaled by D4 exponents (study-oracle-sec-d4).
TABU: numbers without source_slug + formula_id on output.
"""
from __future__ import annotations

from typing import Any

from production_gate.corpus_params import (
    DVTH_NMP,
    GAMMA,
    HCI_ANCHOR_DVTH_MV,
    HCI_ANCHOR_T_S,
    HCI_ANCHOR_VGS_V,
    HCI_DVTH_ANCHOR,
    IEC62416_DVTH_CRITERION,
    NBTI_POWER_LAW_GAMMA,
    N_EXP,
)


def compute_delta_vth_cited_anchor(
    *,
    v_gs_v: float,
    t_stress_s: float,
    sp_i: float | None,
    workload: dict[str, Any],
) -> dict[str, Any]:
    """Scale HCI ΔVth anchor by D4 γ,n — ADAPT cross-mechanism to mod04 metric line."""
    cal_id = workload.get("calibration_id")
    if cal_id != "hci_d4_power_scale_v1":
        return {"oracle": "BLOCKED", "delta_vth_mv": None, "reason": "calibration_id not set"}

    if t_stress_s <= 0 or v_gs_v <= 0:
        return {"oracle": "INPUT_INVALID", "delta_vth_mv": None}

    v_scale = (v_gs_v / HCI_ANCHOR_VGS_V) ** GAMMA
    t_scale = (t_stress_s / HCI_ANCHOR_T_S) ** N_EXP
    sp_factor = float(sp_i) if sp_i is not None else 1.0
    delta_mv = HCI_ANCHOR_DVTH_MV * v_scale * t_scale * sp_factor

    return {
        "oracle": "CITED_ANCHOR_SCALE",
        "calibration_id": cal_id,
        "delta_vth_mv": round(delta_mv, 4),
        "formula": "ΔVth = ΔVth_anchor · (Vgs/V_anchor)^γ · (t/t_anchor)^n · SP_i",
        "anchor": {
            "source_slug": HCI_DVTH_ANCHOR.slug,
            "formula_id": HCI_DVTH_ANCHOR.formula_id,
            "delta_vth_mv": HCI_ANCHOR_DVTH_MV,
            "v_gs_v": HCI_ANCHOR_VGS_V,
            "t_s": HCI_ANCHOR_T_S,
            "oracle": HCI_DVTH_ANCHOR.oracle,
        },
        "exponents": {
            "source_slug": NBTI_POWER_LAW_GAMMA.slug,
            "formula_id": NBTI_POWER_LAW_GAMMA.formula_id,
            "gamma": GAMMA,
            "n": N_EXP,
            "oracle": "USE",
        },
        "nmp_path": {
            "source_slug": DVTH_NMP.slug,
            "formula_id": DVTH_NMP.formula_id,
            "oracle": DVTH_NMP.oracle,
            "note": "Full NMP Grasser path PARK — anchor scale is qual ref tier",
        },
        "guardband_cite": {
            "source_slug": IEC62416_DVTH_CRITERION.slug,
            "formula_id": IEC62416_DVTH_CRITERION.formula_id,
            "oracle": IEC62416_DVTH_CRITERION.oracle,
        },
        "cross_mechanism_note": (
            "Anchor is HCI measured ΔVth (radiation-effects study); scaled by D4 N_G exponents "
            "for mod04 BTI metric line — falsifier if Grasser/NMP disagrees at bind"
        ),
        "inputs": {
            "v_gs_v": v_gs_v,
            "t_stress_s": t_stress_s,
            "sp_i": sp_i,
        },
    }
