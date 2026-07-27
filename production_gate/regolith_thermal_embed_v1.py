"""G14 regolith k(T) embed — Sakatani/Woods Dual KPI / spent.



Physics (teaching ADAPT · not Apollo heat-flow MEASURED):

  k = k_solid + b_rad * T^3

  if cryo and T < t_cryo: k *= cryo_scale



Dual from catalog dual_anchors:

  Safe    = highland_regolith_compact @ daytime T · no cryo

  Hostile = highland_regolith_loose @ cold T · cryo on



Metric adversity = 1 / max(k_w_mk, eps)  (low-k louder)

Spent via dual_share only.

thermal_k_ok = spent < half budget.

"""

from __future__ import annotations



from typing import Any, Literal



ConditionId = Literal["safe", "hostile"]

EMBED_SLICE_J = 1.0





def _k_pack() -> dict[str, Any]:

    from production_gate.regolith_thermal_on_v1 import load_regolith_thermal_catalog



    cat = load_regolith_thermal_catalog()

    a = cat["dual_anchors"]

    return {

        "safe_material": str(a["safe_material"]),

        "hostile_material": str(a["hostile_material"]),

        "safe_t_k": float(a["safe_t_k"]),

        "hostile_t_k": float(a["hostile_t_k"]),

        "safe_cryo": bool(a["safe_cryo"]),

        "hostile_cryo": bool(a["hostile_cryo"]),

    }





def _metric(k_w_mk: float) -> float:

    return 1.0 / max(abs(float(k_w_mk)), 1e-12)





def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:

    from production_gate.regolith_thermal_on_v1 import evaluate_thermal_k



    if condition == "hostile":

        mat, t_k, cryo = pack["safe_material"], pack["safe_t_k"], pack["safe_cryo"]

    else:

        mat, t_k, cryo = pack["hostile_material"], pack["hostile_t_k"], pack["hostile_cryo"]

    row = evaluate_thermal_k(material_id=mat, t_k=t_k, cryo=cryo)

    return _metric(float(row["k_w_mk"]))





def evaluate_regolith_thermal_embed(

    *,

    condition: ConditionId,

    budget_j: float = EMBED_SLICE_J,

) -> dict[str, Any]:

    from production_gate.dual_spent_normalize_v1 import dual_share_receipt

    from production_gate.regolith_thermal_on_v1 import evaluate_thermal_k



    pack = _k_pack()

    if condition == "hostile":

        mat, t_k, cryo = pack["hostile_material"], pack["hostile_t_k"], pack["hostile_cryo"]

    else:

        mat, t_k, cryo = pack["safe_material"], pack["safe_t_k"], pack["safe_cryo"]

    row = evaluate_thermal_k(material_id=mat, t_k=t_k, cryo=cryo)

    k = float(row["k_w_mk"])

    metric = _metric(k)

    peer = _peer_metric(condition=condition, pack=pack)

    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)

    share = dual_share_receipt(

        metric=metric,

        metric_safe=m_s,

        metric_hostile=m_h,

        budget_j=budget_j,

        metric_id="1/k_w_mk",

    )

    thermal_k_ok = float(share["spent_j"]) < 0.5 * float(budget_j)

    firm = evaluate_thermal_k(

        material_id=pack["safe_material"],

        t_k=pack["safe_t_k"],

        cryo=pack["safe_cryo"],

    )

    soft = evaluate_thermal_k(

        material_id=pack["hostile_material"],

        t_k=pack["hostile_t_k"],

        cryo=pack["hostile_cryo"],

    )

    compact_gt_loose_cryo = float(firm["k_w_mk"]) > float(soft["k_w_mk"])

    return {

        "schema": "ha_regolith_thermal_embed_v1",

        "condition": condition,

        "material_id": mat,

        "t_k": t_k,

        "cryo": cryo,

        "k_w_mk": k,

        "k_base_w_mk": float(row.get("k_base_w_mk") or k),

        "cryo_applied": bool(row.get("cryo_applied")),

        "compact_k_gt_loose_cryo": compact_gt_loose_cryo,

        "k_metric": metric,

        "k_spent_j": share["spent_j"],

        "dual_share": share,

        "thermal_k_ok": thermal_k_ok,

        "thermal_k_oracle": row.get("oracle"),

        "honesty": {

            "regolith_thermal_from_rust": True,

            "spent_dual_share_only": True,

            "no_orphan_scale": True,

            "packs_from_catalog_dual_anchors": True,

            "not_measured": True,

            "not_apollo_heat_flow": True,

            "teaching_adapt_k_t": True,

        },

    }





def attach_regolith_thermal_to_physics(

    physics: dict[str, Any],

    *,

    condition: ConditionId,

    budget_j: float = EMBED_SLICE_J,

) -> dict[str, Any]:

    out = dict(physics)

    block = evaluate_regolith_thermal_embed(condition=condition, budget_j=budget_j)

    out["regolith_thermal"] = block

    honesty = dict(out.get("honesty") or {})

    honesty.update({"regolith_thermal_from_rust": True, "spent_dual_share_only": True})

    out["honesty"] = honesty

    out["k_w_mk"] = float(block["k_w_mk"])

    out["thermal_k_ok"] = bool(block["thermal_k_ok"])

    return out





def apply_regolith_thermal_to_spent(

    spent_j: float,

    regolith_thermal: dict[str, Any] | None,

) -> tuple[float, float, dict[str, Any]]:

    if not isinstance(regolith_thermal, dict):

        return float(spent_j), 0.0, {"regolith_thermal_from_rust": False}

    add = float(regolith_thermal.get("k_spent_j") or 0.0)

    honesty = {

        "regolith_thermal_from_rust": True,

        "spent_from_regolith_thermal_rust": True,

        "spent_dual_share_only": True,

        "no_orphan_scale": True,

        "k_spent_j": add,

        "k_w_mk": regolith_thermal.get("k_w_mk"),

        "material_id": regolith_thermal.get("material_id"),

        "thermal_k_ok": regolith_thermal.get("thermal_k_ok"),

    }

    return float(spent_j) + add, add, honesty





def fold_regolith_thermal_into_closed_loop(

    closed_loop: dict[str, Any],

    physics: dict[str, Any] | None,

) -> dict[str, Any]:

    out = dict(closed_loop)

    kpi = dict(out.get("kpi") or {})

    block = (

        physics.get("regolith_thermal")

        if isinstance(physics, dict) and isinstance(physics.get("regolith_thermal"), dict)

        else None

    )

    if not isinstance(block, dict):

        kpi["regolith_thermal_from_rust"] = False

        out["kpi"] = kpi

        return out

    kpi.update(

        {

            "k_w_mk": block.get("k_w_mk"),

            "k_material_id": block.get("material_id"),

            "k_t_k": block.get("t_k"),

            "k_cryo": block.get("cryo"),

            "thermal_k_ok": block.get("thermal_k_ok"),

            "compact_k_gt_loose_cryo": block.get("compact_k_gt_loose_cryo"),

            "regolith_thermal_from_rust": True,

            "spent_dual_share_only": True,

        }

    )

    out["kpi"] = kpi

    honesty = dict(out.get("honesty") or {})

    honesty.update({"regolith_thermal_from_rust": True, "not_apollo_heat_flow": True})

    out["honesty"] = honesty

    return out


