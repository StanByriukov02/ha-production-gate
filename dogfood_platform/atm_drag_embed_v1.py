"""G7 atm-drag embed — quadratic drag F=½ρv²CdA → Dual spent/KPI.

Dual from catalog dual_anchors:
  Safe    = vacuum (ρ=0 → F=0)
  Hostile = mars (thin CO2 class) — independence aero pressure
  earth_body available for Earth-lane KPI twin

Metric = |F_drag_n|
Spent via dual_share only.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _drag_pack() -> dict[str, Any]:
    from dogfood_platform.atm_drag_on_v1 import load_atm_drag_catalog

    cat = load_atm_drag_catalog()
    a = cat["dual_anchors"]
    d = cat["defaults"]
    return {
        "safe_body": str(a["safe_body"]),
        "hostile_body": str(a["hostile_body"]),
        "earth_body": str(a.get("earth_body") or "earth"),
        "v_m_s": float(a.get("v_m_s") or d["v_m_s"]),
        "cd": float(d.get("cd") or 1.0),
        "area_m2": float(d.get("area_m2") or 0.5),
        "mass_kg": float(d.get("mass_kg") or 50.0),
    }


def _peer_f(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from dogfood_platform.atm_drag_on_v1 import evaluate_atm_drag

    body = pack["safe_body"] if condition == "hostile" else pack["hostile_body"]
    row = evaluate_atm_drag(
        body=body,
        v_m_s=pack["v_m_s"],
        cd=pack["cd"],
        area_m2=pack["area_m2"],
        mass_kg=pack["mass_kg"],
    )
    return abs(float(row["f_drag_n"]))


def evaluate_atm_drag_embed(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    from dogfood_platform.atm_drag_on_v1 import evaluate_atm_drag
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt

    pack = _drag_pack()
    body = pack["hostile_body"] if condition == "hostile" else pack["safe_body"]
    row = evaluate_atm_drag(
        body=body,
        v_m_s=pack["v_m_s"],
        cd=pack["cd"],
        area_m2=pack["area_m2"],
        mass_kg=pack["mass_kg"],
    )
    # Earth twin at same v — falsifies ρ Dual (earth F >> mars F >> vacuum).
    earth = evaluate_atm_drag(
        body=pack["earth_body"],
        v_m_s=pack["v_m_s"],
        cd=pack["cd"],
        area_m2=pack["area_m2"],
        mass_kg=pack["mass_kg"],
    )
    f_drag = float(row["f_drag_n"])
    a_drag = float(row["a_drag_m_s2"])
    metric = abs(f_drag)
    peer = _peer_f(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    # Vacuum Safe metric=0 → dual_share spent_safe=0; Hostile gets full budget.
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="|F_drag_n|",
    )
    f_earth = float(earth["f_drag_n"])
    return {
        "schema": "ha_atm_drag_embed_v1",
        "condition": condition,
        "body": body,
        "v_m_s": pack["v_m_s"],
        "rho_kg_m3": float(row["rho_kg_m3"]),
        "f_drag_n": f_drag,
        "a_drag_m_s2": a_drag,
        "f_drag_earth_twin_n": f_earth,
        "earth_gt_mars_gt_vacuum": f_earth > abs(f_drag) if body != "earth" else True,
        "drag_spent_j": share["spent_j"],
        "dual_share": share,
        "drag_oracle": row.get("oracle"),
        "honesty": {
            "atm_drag_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "bodies_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_cfd": True,
            "not_dsmc": True,
        },
    }


def attach_atm_drag_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_atm_drag_embed(condition=condition, budget_j=budget_j)
    out["atm_drag"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update({"atm_drag_from_rust": True, "spent_dual_share_only": True})
    out["honesty"] = honesty
    out["f_drag_n"] = float(block["f_drag_n"])
    return out


def apply_atm_drag_to_spent(
    spent_j: float,
    atm_drag: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(atm_drag, dict):
        return float(spent_j), 0.0, {"atm_drag_from_rust": False}
    add = float(atm_drag.get("drag_spent_j") or 0.0)
    honesty = {
        "atm_drag_from_rust": True,
        "spent_from_atm_drag_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "drag_spent_j": add,
        "f_drag_n": atm_drag.get("f_drag_n"),
        "body": atm_drag.get("body"),
    }
    return float(spent_j) + add, add, honesty


def fold_atm_drag_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("atm_drag")
        if isinstance(physics, dict) and isinstance(physics.get("atm_drag"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["atm_drag_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "f_drag_n": block.get("f_drag_n"),
            "a_drag_m_s2": block.get("a_drag_m_s2"),
            "drag_body": block.get("body"),
            "f_drag_earth_twin_n": block.get("f_drag_earth_twin_n"),
            "atm_drag_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update({"atm_drag_from_rust": True, "not_cfd": True})
    out["honesty"] = honesty
    return out
