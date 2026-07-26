"""G11 dust-ingress embed — Stubbs zone + seal → Dual KPI / spent.

Physics (ADAPT teaching · not Shackleton flux meter · not MEASURED):
  rate = base(zone)*seal*gap*ES*(1-mit)
  acc = min(sat, prev + rate*n_sols)

Dual from catalog dual_anchors:
  Safe    = psr_floor + B1 + mitigation + tight gap
  Hostile = massif_traverse + B5 + no mit + open gap

Metric = effective_rate + accumulation
Spent via dual_share only.
ingress_ok = spent < half budget (and hazard not SEVERE).
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _ingress_pack() -> dict[str, Any]:
    from dogfood_platform.dust_ingress_on_v1 import load_dust_ingress_catalog

    cat = load_dust_ingress_catalog()
    a = cat["dual_anchors"]
    return {
        "safe_zone": str(a["safe_zone"]),
        "hostile_zone": str(a["hostile_zone"]),
        "safe_seal": str(a["safe_seal"]),
        "hostile_seal": str(a["hostile_seal"]),
        "n_sols": float(a["n_sols"]),
        "safe_mit": float(a["safe_mitigation"]),
        "hostile_mit": float(a["hostile_mitigation"]),
        "gap_safe": float(a["gap_mm_safe"]),
        "gap_hostile": float(a["gap_mm_hostile"]),
    }


def _metric(*, rate: float, acc: float) -> float:
    return abs(float(rate)) + abs(float(acc))


def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from dogfood_platform.dust_ingress_on_v1 import evaluate_dust_ingress

    if condition == "hostile":
        zone, seal, mit, gap = (
            pack["safe_zone"],
            pack["safe_seal"],
            pack["safe_mit"],
            pack["gap_safe"],
        )
    else:
        zone, seal, mit, gap = (
            pack["hostile_zone"],
            pack["hostile_seal"],
            pack["hostile_mit"],
            pack["gap_hostile"],
        )
    row = evaluate_dust_ingress(
        zone=zone,
        seal=seal,
        n_sols=pack["n_sols"],
        mitigation_duty=mit,
        joint_gap_mm=gap,
    )
    return _metric(
        rate=float(row["effective_rate_g_m2_per_sol"]),
        acc=float(row["accumulation_g_m2"]),
    )


def evaluate_dust_ingress_embed(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt
    from dogfood_platform.dust_ingress_on_v1 import evaluate_dust_ingress

    pack = _ingress_pack()
    if condition == "hostile":
        zone, seal, mit, gap = (
            pack["hostile_zone"],
            pack["hostile_seal"],
            pack["hostile_mit"],
            pack["gap_hostile"],
        )
    else:
        zone, seal, mit, gap = (
            pack["safe_zone"],
            pack["safe_seal"],
            pack["safe_mit"],
            pack["gap_safe"],
        )
    row = evaluate_dust_ingress(
        zone=zone,
        seal=seal,
        n_sols=pack["n_sols"],
        mitigation_duty=mit,
        joint_gap_mm=gap,
    )
    rate = float(row["effective_rate_g_m2_per_sol"])
    acc = float(row["accumulation_g_m2"])
    haz = str(row.get("ingress_hazard_class") or "LOW")
    metric = _metric(rate=rate, acc=acc)
    peer = _peer_metric(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="rate+acc",
    )
    ingress_ok = float(share["spent_j"]) < 0.5 * float(budget_j) and haz not in ("SEVERE",)
    return {
        "schema": "ha_dust_ingress_embed_v1",
        "condition": condition,
        "zone": zone,
        "seal_class": seal,
        "n_sols": pack["n_sols"],
        "mitigation_duty": mit,
        "joint_gap_mm": gap,
        "effective_rate_g_m2_per_sol": rate,
        "accumulation_g_m2": acc,
        "ingress_hazard_class": haz,
        "stress_index_multiplier": float(row.get("stress_index_multiplier") or 1.0),
        "ingress_metric": metric,
        "ingress_spent_j": share["spent_j"],
        "dual_share": share,
        "ingress_ok": ingress_ok,
        "ingress_oracle": row.get("oracle"),
        "honesty": {
            "dust_ingress_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_shackleton_flux_meter": True,
            "adapt_tier": True,
        },
    }


def attach_dust_ingress_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_dust_ingress_embed(condition=condition, budget_j=budget_j)
    out["dust_ingress"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update({"dust_ingress_from_rust": True, "spent_dual_share_only": True})
    out["honesty"] = honesty
    out["ingress_rate"] = float(block["effective_rate_g_m2_per_sol"])
    out["ingress_ok"] = bool(block["ingress_ok"])
    if not block["ingress_ok"]:
        out["sinkage_risk"] = True  # ops dust-wear risk Dual — honesty not soil sinkage
    return out


def apply_dust_ingress_to_spent(
    spent_j: float,
    dust_ingress: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(dust_ingress, dict):
        return float(spent_j), 0.0, {"dust_ingress_from_rust": False}
    add = float(dust_ingress.get("ingress_spent_j") or 0.0)
    honesty = {
        "dust_ingress_from_rust": True,
        "spent_from_dust_ingress_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "ingress_spent_j": add,
        "effective_rate_g_m2_per_sol": dust_ingress.get("effective_rate_g_m2_per_sol"),
        "accumulation_g_m2": dust_ingress.get("accumulation_g_m2"),
        "ingress_hazard_class": dust_ingress.get("ingress_hazard_class"),
        "ingress_ok": dust_ingress.get("ingress_ok"),
        "zone": dust_ingress.get("zone"),
    }
    return float(spent_j) + add, add, honesty


def fold_dust_ingress_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("dust_ingress")
        if isinstance(physics, dict) and isinstance(physics.get("dust_ingress"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["dust_ingress_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "ingress_rate_g_m2_per_sol": block.get("effective_rate_g_m2_per_sol"),
            "ingress_accumulation_g_m2": block.get("accumulation_g_m2"),
            "ingress_hazard_class": block.get("ingress_hazard_class"),
            "ingress_ok": block.get("ingress_ok"),
            "ingress_zone": block.get("zone"),
            "dust_ingress_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update({"dust_ingress_from_rust": True, "adapt_tier": True})
    out["honesty"] = honesty
    return out
