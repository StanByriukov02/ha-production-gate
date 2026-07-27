"""ENVELOPE_REFUSE — published GCR/SPE envelopes refuse Dual current.

Proof tier: ENVELOPE_REFUSE (PROOF_TIER_LADDER_V1).
Not CREME FEM · not MEASURED · ε_envelope_not_transport.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
PROOF_TIER = "ENVELOPE_REFUSE"


def evaluate_envelope_refuse(*, condition: ConditionId) -> dict[str, Any]:
    from production_gate.radiation_rate_on_v1 import (
        evaluate_radiation_rate,
        load_radiation_rate_catalog,
    )

    cat = load_radiation_rate_catalog()
    anchors = cat["dual_anchors"]
    envs = cat.get("published_envelopes") or {}
    gcr = envs.get("gcr_polar_annual_class") or {}
    spe = envs.get("spe_flare_window_24h_class") or {}
    sites = cat.get("sites") or {}

    if condition == "hostile":
        site_id = str(anchors["hostile_site"])
        flare = float(anchors.get("hostile_flare_scale") or 12.0)
    else:
        site_id = str(anchors["safe_site"])
        flare = float(anchors.get("safe_flare_scale") or 1.0)

    dt_h = float(spe.get("dt_h") or anchors.get("dt_h") or 24.0)
    row = evaluate_radiation_rate(dt_h=dt_h, flare_scale=flare, site_id=site_id)
    window = float(row.get("window_dose_gy") or 0.0)
    annual = float((sites.get(site_id) or {}).get("annual_dose_gy") or 0.0)
    mission_budget = float((sites.get(site_id) or {}).get("mission_budget_gy") or 1.0)

    max_annual = float(gcr.get("max_annual_gy") or 0.40)
    max_window = float(spe.get("max_window_gy") or 0.010)

    inside_gcr = annual <= max_annual
    inside_spe = window <= max_window
    inside = inside_gcr and inside_spe

    return {
        "schema": "ha_envelope_refuse_v1",
        "proof_tier": PROOF_TIER,
        "envelope_id": "gcr_polar_annual+spe_flare_window_24h",
        "condition": condition,
        "site_id": site_id,
        "flare_scale": flare,
        "dt_h": dt_h,
        "annual_dose_gy": annual,
        "window_dose_gy": window,
        "mission_budget_gy": mission_budget,
        "max_annual_gy": max_annual,
        "max_window_gy": max_window,
        "inside_gcr_envelope": inside_gcr,
        "inside_spe_envelope": inside_spe,
        "inside_envelope": inside,
        "envelope_ok": inside,
        "radiation_oracle": row.get("oracle"),
        "on_cite": {
            "gcr": gcr.get("on_cite"),
            "spe": spe.get("on_cite"),
        },
        "honesty": {
            "proof_tier": PROOF_TIER,
            "not_creme_fem": True,
            "not_measured": True,
            "epsilon": ["ε_envelope_not_transport", "ε_desk_not_world"],
            "tabu_claim_creme": True,
        },
    }


def attach_envelope_refuse_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_envelope_refuse(condition=condition)
    out["envelope_refuse"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "envelope_refuse": True,
            "inside_envelope": bool(block["inside_envelope"]),
            "proof_tier_envelope_refuse": True,
            "not_creme_fem": True,
        }
    )
    out["honesty"] = honesty
    out["inside_envelope"] = bool(block["inside_envelope"])
    if not block["inside_envelope"]:
        out["traverse_feasible"] = False
        out["sinkage_risk"] = True
    return out
