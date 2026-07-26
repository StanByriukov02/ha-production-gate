"""G10 albedo-dose embed — Matthia/SELINE albedo → Dual KPI / spent.

Physics (PROXY teaching · not CREME FEM · not MEASURED):
  f_alb = min(ceiling, f0*site*(1+(mf-1)*gauss(g)))
  total = anchor * (1+(mt-1)*gauss(g))
  albedo = total * f_alb

Dual from catalog dual_anchors:
  Safe    = highland @ shield away from peak
  Hostile = magnetic_anomaly @ Matthia peak ~90 g/cm2

Metric = albedo_dose_gy + see_rate_per_year
Spent via dual_share only.
dose_ok = spent < half budget.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _albedo_pack() -> dict[str, Any]:
    from dogfood_platform.albedo_dose_on_v1 import load_albedo_dose_catalog

    cat = load_albedo_dose_catalog()
    a = cat["dual_anchors"]
    return {
        "safe_site": str(a["safe_site"]),
        "hostile_site": str(a["hostile_site"]),
        "safe_shield": float(a["safe_shield_g_cm2"]),
        "hostile_shield": float(a["hostile_shield_g_cm2"]),
        "anchor_gy": float(a["anchor_gy"]),
    }


def _metric(*, albedo_gy: float, see_rate: float) -> float:
    return abs(float(albedo_gy)) + abs(float(see_rate))


def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from dogfood_platform.albedo_dose_on_v1 import evaluate_albedo_dose

    if condition == "hostile":
        site, shield = pack["safe_site"], pack["safe_shield"]
    else:
        site, shield = pack["hostile_site"], pack["hostile_shield"]
    row = evaluate_albedo_dose(
        site_class=site, shield_g_cm2=shield, dose_anchor_gy=pack["anchor_gy"]
    )
    return _metric(
        albedo_gy=float(row["albedo_dose_gy"]),
        see_rate=float(row.get("see_rate_per_year") or 0.0),
    )


def evaluate_albedo_dose_embed(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    from dogfood_platform.albedo_dose_on_v1 import evaluate_albedo_dose
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt

    pack = _albedo_pack()
    if condition == "hostile":
        site, shield = pack["hostile_site"], pack["hostile_shield"]
    else:
        site, shield = pack["safe_site"], pack["safe_shield"]
    row = evaluate_albedo_dose(
        site_class=site, shield_g_cm2=shield, dose_anchor_gy=pack["anchor_gy"]
    )
    albedo_gy = float(row["albedo_dose_gy"])
    see_rate = float(row.get("see_rate_per_year") or 0.0)
    f_alb = float(row["albedo_fraction"])
    metric = _metric(albedo_gy=albedo_gy, see_rate=see_rate)
    peer = _peer_metric(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="albedo_gy+see_rate",
    )
    dose_ok = float(share["spent_j"]) < 0.5 * float(budget_j)
    return {
        "schema": "ha_albedo_dose_embed_v1",
        "condition": condition,
        "site_class": site,
        "shield_g_cm2": shield,
        "dose_anchor_gy": pack["anchor_gy"],
        "albedo_fraction": f_alb,
        "albedo_dose_gy": albedo_gy,
        "incident_dose_gy": float(row.get("incident_dose_gy") or 0.0),
        "total_dose_gy": float(row.get("total_dose_gy") or 0.0),
        "see_rate_per_year": see_rate,
        "albedo_metric": metric,
        "albedo_spent_j": share["spent_j"],
        "dual_share": share,
        "dose_ok": dose_ok,
        "albedo_oracle": row.get("oracle"),
        "honesty": {
            "albedo_dose_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_creme_fem": True,
            "proxy_seline_matthia": True,
        },
    }


def attach_albedo_dose_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_albedo_dose_embed(condition=condition, budget_j=budget_j)
    out["albedo_dose"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update({"albedo_dose_from_rust": True, "spent_dual_share_only": True})
    out["honesty"] = honesty
    out["albedo_dose_gy"] = float(block["albedo_dose_gy"])
    out["dose_ok"] = bool(block["dose_ok"])
    return out


def apply_albedo_dose_to_spent(
    spent_j: float,
    albedo_dose: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(albedo_dose, dict):
        return float(spent_j), 0.0, {"albedo_dose_from_rust": False}
    add = float(albedo_dose.get("albedo_spent_j") or 0.0)
    honesty = {
        "albedo_dose_from_rust": True,
        "spent_from_albedo_dose_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "albedo_spent_j": add,
        "albedo_dose_gy": albedo_dose.get("albedo_dose_gy"),
        "see_rate_per_year": albedo_dose.get("see_rate_per_year"),
        "dose_ok": albedo_dose.get("dose_ok"),
        "site_class": albedo_dose.get("site_class"),
    }
    return float(spent_j) + add, add, honesty


def fold_albedo_dose_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("albedo_dose")
        if isinstance(physics, dict) and isinstance(physics.get("albedo_dose"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["albedo_dose_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "albedo_dose_gy": block.get("albedo_dose_gy"),
            "albedo_fraction": block.get("albedo_fraction"),
            "see_rate_per_year": block.get("see_rate_per_year"),
            "dose_ok": block.get("dose_ok"),
            "albedo_site_class": block.get("site_class"),
            "albedo_dose_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update({"albedo_dose_from_rust": True, "not_creme_fem": True})
    out["honesty"] = honesty
    return out
