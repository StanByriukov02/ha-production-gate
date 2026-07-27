"""G9 Li q_c embed — lunar-g bearing adjunct → Dual KPI / spent.

Physics (teaching · adjunct to Bekker · not MEASURED bevameter):
  q_c(h) = A exp(-h/B) + C

Dual from catalog dual_anchors:
  Safe    = deep (high q_c)
  Hostile = shallow (low q_c near-surface soft)

Metric adversity = 1 / max(q_c_kpa, eps)
Spent via dual_share only.
bearing_ok = spent < half budget.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _li_pack() -> dict[str, Any]:
    from production_gate.li_bearing_qc_on_v1 import load_li_qc_catalog

    cat = load_li_qc_catalog()
    a = cat["dual_anchors"]
    return {
        "safe_depth_mm": float(a["safe_depth_mm"]),
        "hostile_depth_mm": float(a["hostile_depth_mm"]),
    }


def _metric(q_c_kpa: float) -> float:
    return 1.0 / max(abs(float(q_c_kpa)), 1e-9)


def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from production_gate.li_bearing_qc_on_v1 import evaluate_li_qc

    depth = pack["safe_depth_mm"] if condition == "hostile" else pack["hostile_depth_mm"]
    row = evaluate_li_qc(depth_mm=depth)
    return _metric(float(row["q_c_kpa"]))


def evaluate_li_qc_embed(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.li_bearing_qc_on_v1 import evaluate_li_qc

    pack = _li_pack()
    depth = pack["hostile_depth_mm"] if condition == "hostile" else pack["safe_depth_mm"]
    row = evaluate_li_qc(depth_mm=depth)
    q_c = float(row["q_c_kpa"])
    metric = _metric(q_c)
    peer = _peer_metric(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="1/|q_c_kpa|",
    )
    bearing_ok = float(share["spent_j"]) < 0.5 * float(budget_j)
    # Peer depth for Dual falsifier (deep q_c > shallow q_c).
    peer_depth = pack["safe_depth_mm"] if condition == "hostile" else pack["hostile_depth_mm"]
    peer_row = evaluate_li_qc(depth_mm=peer_depth)
    q_peer = float(peer_row["q_c_kpa"])
    deep_gt_shallow = (
        float(evaluate_li_qc(depth_mm=pack["safe_depth_mm"])["q_c_kpa"])
        > float(evaluate_li_qc(depth_mm=pack["hostile_depth_mm"])["q_c_kpa"])
    )
    return {
        "schema": "ha_li_qc_embed_v1",
        "condition": condition,
        "depth_mm": depth,
        "q_c_kpa": q_c,
        "peer_depth_mm": peer_depth,
        "peer_q_c_kpa": q_peer,
        "deep_qc_gt_shallow": deep_gt_shallow,
        "li_metric": metric,
        "li_spent_j": share["spent_j"],
        "dual_share": share,
        "bearing_ok": bearing_ok,
        "li_oracle": row.get("oracle"),
        "honesty": {
            "li_qc_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "adjunct_not_bekker_oracle": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_bevameter_field": True,
        },
    }


def attach_li_qc_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_li_qc_embed(condition=condition, budget_j=budget_j)
    out["li_qc"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "li_qc_from_rust": True,
            "spent_dual_share_only": True,
            "adjunct_not_bekker_oracle": True,
        }
    )
    out["honesty"] = honesty
    out["q_c_kpa"] = float(block["q_c_kpa"])
    out["bearing_ok"] = bool(block["bearing_ok"])
    return out


def apply_li_qc_to_spent(
    spent_j: float,
    li_qc: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(li_qc, dict):
        return float(spent_j), 0.0, {"li_qc_from_rust": False}
    add = float(li_qc.get("li_spent_j") or 0.0)
    honesty = {
        "li_qc_from_rust": True,
        "spent_from_li_qc_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "li_spent_j": add,
        "q_c_kpa": li_qc.get("q_c_kpa"),
        "depth_mm": li_qc.get("depth_mm"),
        "bearing_ok": li_qc.get("bearing_ok"),
    }
    return float(spent_j) + add, add, honesty


def fold_li_qc_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("li_qc")
        if isinstance(physics, dict) and isinstance(physics.get("li_qc"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["li_qc_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "q_c_kpa": block.get("q_c_kpa"),
            "li_depth_mm": block.get("depth_mm"),
            "bearing_ok": block.get("bearing_ok"),
            "deep_qc_gt_shallow": block.get("deep_qc_gt_shallow"),
            "li_qc_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update({"li_qc_from_rust": True, "adjunct_not_bekker": True})
    out["honesty"] = honesty
    return out
