"""G6 ISRU sinter embed — Arrhenius progress → Dual KPI / spent.

Physics (teaching · not kiln MEASURED · not densification FEM):
  rate = A exp(-Ea/(R T))
  progress = 1 - exp(-rate t)
  E = P · t

Dual from catalog dual_anchors:
  Safe    = safe_recipe @ dual t_k/t_s/p_w
  Hostile = hostile_recipe @ same T,t,P (higher Ea → less progress)

Metric adversity = 1 - progress  (Hostile colder kinetics louder)
Spent via dual_share only.
sinter_ok = progress > Dual midpoint (spent < half budget).
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _sinter_pack() -> dict[str, Any]:
    from production_gate.isru_sinter_on_v1 import load_sinter_catalog

    cat = load_sinter_catalog()
    a = cat["dual_anchors"]
    d = cat["defaults"]
    return {
        "safe_recipe": str(a["safe_recipe"]),
        "hostile_recipe": str(a["hostile_recipe"]),
        "t_k": float(a.get("t_k") or d["t_k"]),
        "t_s": float(a.get("t_s") or d["t_s"]),
        "p_w": float(a.get("p_w") or d["p_w"]),
    }


def _peer_progress(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from production_gate.isru_sinter_on_v1 import evaluate_isru_sinter

    rid = pack["safe_recipe"] if condition == "hostile" else pack["hostile_recipe"]
    row = evaluate_isru_sinter(
        recipe_id=rid, t_k=pack["t_k"], t_s=pack["t_s"], p_w=pack["p_w"]
    )
    return 1.0 - float(row["progress"])


def evaluate_isru_sinter_embed(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.isru_sinter_on_v1 import evaluate_isru_sinter

    pack = _sinter_pack()
    recipe = pack["hostile_recipe"] if condition == "hostile" else pack["safe_recipe"]
    row = evaluate_isru_sinter(
        recipe_id=recipe, t_k=pack["t_k"], t_s=pack["t_s"], p_w=pack["p_w"]
    )
    progress = float(row["progress"])
    rate = float(row["rate_per_s"])
    energy_j = float(row["energy_j"])
    metric = 1.0 - progress
    peer = _peer_progress(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="1-progress",
    )
    sinter_ok = float(share["spent_j"]) < 0.5 * float(budget_j)

    return {
        "schema": "ha_isru_sinter_embed_v1",
        "condition": condition,
        "recipe_id": recipe,
        "t_k": pack["t_k"],
        "t_s": pack["t_s"],
        "p_w": pack["p_w"],
        "rate_per_s": rate,
        "progress": progress,
        "energy_j": energy_j,
        "sinter_adversity": metric,
        "sinter_spent_j": share["spent_j"],
        "dual_share": share,
        "sinter_ok": sinter_ok,
        "sinter_oracle": row.get("oracle"),
        "honesty": {
            "isru_sinter_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_densification_fem": True,
            "not_kiln_campaign": True,
        },
    }


def attach_isru_sinter_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_isru_sinter_embed(condition=condition, budget_j=budget_j)
    out["isru_sinter"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "isru_sinter_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    out["sinter_progress"] = float(block["progress"])
    out["sinter_ok"] = bool(block["sinter_ok"])
    return out


def apply_isru_sinter_to_spent(
    spent_j: float,
    isru_sinter: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(isru_sinter, dict):
        return float(spent_j), 0.0, {"isru_sinter_from_rust": False}
    add = float(isru_sinter.get("sinter_spent_j") or 0.0)
    honesty = {
        "isru_sinter_from_rust": True,
        "spent_from_isru_sinter_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "sinter_spent_j": add,
        "progress": isru_sinter.get("progress"),
        "recipe_id": isru_sinter.get("recipe_id"),
        "sinter_ok": isru_sinter.get("sinter_ok"),
    }
    return float(spent_j) + add, add, honesty


def fold_isru_sinter_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("isru_sinter")
        if isinstance(physics, dict) and isinstance(physics.get("isru_sinter"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["isru_sinter_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "sinter_progress": block.get("progress"),
            "sinter_rate_per_s": block.get("rate_per_s"),
            "sinter_energy_j": block.get("energy_j"),
            "sinter_ok": block.get("sinter_ok"),
            "sinter_recipe_id": block.get("recipe_id"),
            "isru_sinter_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update({"isru_sinter_from_rust": True, "not_kiln_measured": True})
    out["honesty"] = honesty
    return out
