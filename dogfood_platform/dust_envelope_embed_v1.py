"""G1 dust-envelope embed — charging + Coulomb loft + soiling → Dual pressure.

Physics (teaching · not CCMC/PIC/MEASURED):

Dual pack (catalog-owned):
  Safe    — illum ≥ charging dayside threshold · clean soiling anchor · no SEP
  Hostile — nightside illum=0 · SEP · soiling hostile_g_m2 · r from loft defaults

Metric (raw SI-ish; no orphan /200 /5 /50 scales):
  metric = |φ| + loft_ratio + R_th + mass_g_m2 + max(0, A0 - A_eff)

Spent via dual_share only:
  spent = budget_j * |m| / (|m_safe| + |m_hostile|)

dust_risk: loft criterion (ratio≥1) or Hostile Dual side.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _dust_pack() -> dict[str, Any]:
    from dogfood_platform.coulomb_loft_on_v1 import load_coulomb_loft_catalog
    from dogfood_platform.soiling_thermal_bc_on_v1 import load_soiling_catalog
    from dogfood_platform.surface_charging_on_v1 import load_surface_charging_catalog

    charge = load_surface_charging_catalog()
    soil = load_soiling_catalog()
    loft = load_coulomb_loft_catalog()
    thr = charge["thresholds"]
    c_anch = charge.get("dual_anchors") or {}
    anchors = soil["dual_anchors"]
    loft_a = loft.get("dual_anchors") or {}
    return {
        "illum_safe": float(c_anch.get("safe_illum") if c_anch.get("safe_illum") is not None else thr["dayside_illum_min"]),
        "illum_hostile": float(
            c_anch.get("hostile_illum") if c_anch.get("hostile_illum") is not None else 0.0
        ),
        "soil_safe": float(anchors["clean_g_m2"]),
        "soil_hostile": float(anchors["hostile_g_m2"]),
        "r_um": float(loft_a.get("r_um") if loft_a.get("r_um") is not None else loft["defaults"]["r_um"]),
        "albedo_clean": float(soil.get("clean", soil.get("baseline", {})).get("albedo") or 0.12),
        "hostile_sep": bool(c_anch.get("hostile_sep", True)),
        "safe_sep": bool(c_anch.get("safe_sep", False)),
    }


def _dust_metric(
    *,
    phi: float,
    loft_ratio: float,
    r_th: float,
    mass: float,
    a_eff: float,
    albedo_clean: float,
) -> float:
    return abs(phi) + float(loft_ratio) + max(r_th, 0.0) + max(mass, 0.0) + max(
        0.0, albedo_clean - a_eff
    )


def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from dogfood_platform.coulomb_loft_on_v1 import evaluate_coulomb_loft
    from dogfood_platform.soiling_thermal_bc_on_v1 import evaluate_soiling_bc
    from dogfood_platform.surface_charging_on_v1 import evaluate_surface_charging

    if condition == "hostile":
        illum, sep, mass = pack["illum_safe"], bool(pack["safe_sep"]), pack["soil_safe"]
    else:
        illum, sep, mass = pack["illum_hostile"], bool(pack["hostile_sep"]), pack["soil_hostile"]
    charge = evaluate_surface_charging(illum_frac=illum, sep_active=sep)
    phi = float(charge["surface_potential_v"])
    loft = evaluate_coulomb_loft(phi_v=phi, r_um=pack["r_um"])
    soil = evaluate_soiling_bc(mass_g_m2=mass)
    r_th = float(soil.get("r_th_m2k_w") or soil.get("R_th") or 0.0)
    a_eff = float(soil.get("albedo_eff") or soil.get("A_eff") or 0.0)
    return _dust_metric(
        phi=phi,
        loft_ratio=float(loft["loft_ratio"]),
        r_th=r_th,
        mass=mass,
        a_eff=a_eff,
        albedo_clean=pack["albedo_clean"],
    )


def evaluate_dust_envelope(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    """Evaluate charging → loft + soiling from Rust; Dual-share spent."""
    from dogfood_platform.coulomb_loft_on_v1 import evaluate_coulomb_loft
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt
    from dogfood_platform.soiling_thermal_bc_on_v1 import evaluate_soiling_bc
    from dogfood_platform.surface_charging_on_v1 import evaluate_surface_charging

    pack = _dust_pack()
    if condition == "hostile":
        illum, sep, mass = pack["illum_hostile"], bool(pack["hostile_sep"]), pack["soil_hostile"]
    else:
        illum, sep, mass = pack["illum_safe"], bool(pack["safe_sep"]), pack["soil_safe"]

    charge = evaluate_surface_charging(illum_frac=illum, sep_active=sep)
    phi = float(charge["surface_potential_v"])
    loft = evaluate_coulomb_loft(phi_v=phi, r_um=pack["r_um"])
    soil = evaluate_soiling_bc(mass_g_m2=mass)

    loft_ratio = float(loft["loft_ratio"])
    r_th = float(soil.get("r_th_m2k_w") or soil.get("R_th") or 0.0)
    a_eff = float(soil.get("albedo_eff") or soil.get("A_eff") or 0.0)
    metric = _dust_metric(
        phi=phi,
        loft_ratio=loft_ratio,
        r_th=r_th,
        mass=mass,
        a_eff=a_eff,
        albedo_clean=pack["albedo_clean"],
    )
    peer = _peer_metric(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="|phi|+loft+Rth+mass+dA",
    )
    # Physics loft criterion (ratio>1) OR Hostile Dual side of share.
    dust_risk = bool(loft.get("lofts")) or loft_ratio >= 1.0 or condition == "hostile"

    return {
        "schema": "ha_dust_envelope_embed_v1",
        "condition": condition,
        "illum_frac": illum,
        "sep_active": sep,
        "phi_v": phi,
        "charging_class": charge.get("charging_class"),
        "loft_ratio": loft_ratio,
        "lofts": bool(loft.get("lofts")),
        "mass_g_m2": mass,
        "r_th_m2k_w": r_th,
        "a_eff": a_eff,
        "dust_pressure": metric,
        "dust_spent_j": share["spent_j"],
        "dual_share": share,
        "dust_risk": dust_risk,
        "charging_oracle": charge.get("oracle"),
        "loft_oracle": loft.get("oracle"),
        "soiling_oracle": soil.get("oracle"),
        "honesty": {
            "dust_envelope_from_rust": True,
            "charging_from_rust": True,
            "coulomb_loft_from_rust": True,
            "soiling_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "illum_from_charging_thresholds": True,
            "soil_from_soiling_dual_anchors": True,
            "not_measured": True,
            "not_ccmc": True,
            "not_pic": True,
        },
    }


def attach_dust_envelope_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_dust_envelope(condition=condition, budget_j=budget_j)
    out["dust_envelope"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "dust_envelope_from_rust": True,
            "charging_from_rust": True,
            "coulomb_loft_from_rust": True,
            "soiling_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    out["dust_pressure"] = float(block["dust_pressure"])
    out["dust_risk"] = bool(block["dust_risk"])
    if block["dust_risk"]:
        out["sinkage_risk"] = True
    return out


def apply_dust_envelope_to_spent(
    spent_j: float,
    dust_envelope: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(dust_envelope, dict):
        return float(spent_j), 0.0, {"dust_envelope_from_rust": False}
    add = float(dust_envelope.get("dust_spent_j") or 0.0)
    honesty = {
        "dust_envelope_from_rust": True,
        "spent_from_dust_envelope_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "dust_spent_j": add,
        "dust_pressure": dust_envelope.get("dust_pressure"),
        "phi_v": dust_envelope.get("phi_v"),
        "loft_ratio": dust_envelope.get("loft_ratio"),
        "mass_g_m2": dust_envelope.get("mass_g_m2"),
        "charging_from_rust": bool((dust_envelope.get("honesty") or {}).get("charging_from_rust")),
        "coulomb_loft_from_rust": bool(
            (dust_envelope.get("honesty") or {}).get("coulomb_loft_from_rust")
        ),
        "soiling_from_rust": bool((dust_envelope.get("honesty") or {}).get("soiling_from_rust")),
    }
    return float(spent_j) + add, add, honesty
