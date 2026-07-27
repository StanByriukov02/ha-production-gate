"""G12/G15 Janosi shear-curve embed — τ(j) Dual KPI / spent.

Physics (Wong Janosi–Hanamoto · teaching · not MEASURED bevameter):
  τ(j) = (c + p tan φ)(1 - e^{-j/K})

Dual from catalog dual_anchors:
  Safe    = firm_lab
  Hostile = soft_hostile
  probe at j_probe_m
  p_kpa   = Bekker contact ground_pressure when on Dual run (G15),
            else catalog dual_anchors.p_kpa

Metric adversity = 1 / max(τ_probe, eps)  (soft traction louder)
Spent via dual_share only.
shear_ok = spent < half budget.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _janosi_pack(*, p_kpa: float | None = None) -> dict[str, Any]:
    from production_gate.janosi_shear_curve_on_v1 import load_janosi_curve_catalog

    cat = load_janosi_curve_catalog()
    a = cat["dual_anchors"]
    d = cat["defaults"]
    catalog_p = float(a.get("p_kpa") or d["p_kpa"])
    p_from_bekker = p_kpa is not None
    return {
        "safe_soil": str(a["safe_soil_id"]),
        "hostile_soil": str(a["hostile_soil_id"]),
        "j_probe": float(a["j_probe_m"]),
        "p_kpa": float(p_kpa) if p_from_bekker else catalog_p,
        "p_from_bekker_contact": p_from_bekker,
        "catalog_p_kpa": catalog_p,
        "area": float(d["contact_area_m2"]),
    }


def _tau_at_probe(row: dict[str, Any], j_probe: float) -> float:
    curve = row.get("curve") or []
    if not curve:
        return float(row.get("tau_at_jmax_kpa") or 0.0)
    best = min(curve, key=lambda p: abs(float(p["j_m"]) - j_probe))
    return float(best["tau_kpa"])


def _metric(tau_probe: float) -> float:
    return 1.0 / max(abs(float(tau_probe)), 1e-9)


def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from production_gate.janosi_shear_curve_on_v1 import evaluate_janosi_curve

    soil = pack["safe_soil"] if condition == "hostile" else pack["hostile_soil"]
    row = evaluate_janosi_curve(soil_id=soil, p_kpa=pack["p_kpa"], area_m2=pack["area"])
    return _metric(_tau_at_probe(row, pack["j_probe"]))


def evaluate_janosi_embed(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
    p_kpa: float | None = None,
) -> dict[str, Any]:
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.janosi_shear_curve_on_v1 import evaluate_janosi_curve

    pack = _janosi_pack(p_kpa=p_kpa)
    soil = pack["hostile_soil"] if condition == "hostile" else pack["safe_soil"]
    row = evaluate_janosi_curve(soil_id=soil, p_kpa=pack["p_kpa"], area_m2=pack["area"])
    tau_probe = _tau_at_probe(row, pack["j_probe"])
    tau_inf = float(row.get("tau_inf_kpa") or 0.0)
    metric = _metric(tau_probe)
    peer = _peer_metric(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="1/tau_probe",
    )
    shear_ok = float(share["spent_j"]) < 0.5 * float(budget_j)
    # Falsifier: firm tau > soft tau at same j and same p.
    firm = evaluate_janosi_curve(
        soil_id=pack["safe_soil"], p_kpa=pack["p_kpa"], area_m2=pack["area"]
    )
    soft = evaluate_janosi_curve(
        soil_id=pack["hostile_soil"], p_kpa=pack["p_kpa"], area_m2=pack["area"]
    )
    firm_gt_soft = _tau_at_probe(firm, pack["j_probe"]) > _tau_at_probe(soft, pack["j_probe"])
    return {
        "schema": "ha_janosi_embed_v1",
        "condition": condition,
        "soil_id": soil,
        "j_probe_m": pack["j_probe"],
        "p_kpa": pack["p_kpa"],
        "p_from_bekker_contact": pack["p_from_bekker_contact"],
        "catalog_p_kpa": pack["catalog_p_kpa"],
        "tau_probe_kpa": tau_probe,
        "tau_inf_kpa": tau_inf,
        "tau_at_0_kpa": float(row.get("tau_at_0_kpa") or 0.0),
        "firm_tau_gt_soft": firm_gt_soft,
        "janosi_metric": metric,
        "janosi_spent_j": share["spent_j"],
        "dual_share": share,
        "shear_ok": shear_ok,
        "janosi_oracle": row.get("oracle"),
        "honesty": {
            "janosi_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "p_from_bekker_contact": pack["p_from_bekker_contact"],
            "not_measured": True,
            "not_bevameter_slip_curve": True,
            "curve_adjunct_to_bekker_point": True,
        },
    }


def attach_janosi_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    contact_p = physics.get("ground_pressure_kpa")
    p_kpa = float(contact_p) if contact_p is not None else None
    block = evaluate_janosi_embed(condition=condition, budget_j=budget_j, p_kpa=p_kpa)
    out["janosi"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "janosi_from_rust": True,
            "spent_dual_share_only": True,
            "janosi_p_from_bekker_contact": bool(block.get("p_from_bekker_contact")),
        }
    )
    out["honesty"] = honesty
    out["tau_probe_kpa"] = float(block["tau_probe_kpa"])
    out["shear_ok"] = bool(block["shear_ok"])
    return out


def apply_janosi_to_spent(
    spent_j: float,
    janosi: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(janosi, dict):
        return float(spent_j), 0.0, {"janosi_from_rust": False}
    add = float(janosi.get("janosi_spent_j") or 0.0)
    honesty = {
        "janosi_from_rust": True,
        "spent_from_janosi_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "janosi_spent_j": add,
        "tau_probe_kpa": janosi.get("tau_probe_kpa"),
        "p_kpa": janosi.get("p_kpa"),
        "p_from_bekker_contact": janosi.get("p_from_bekker_contact"),
        "soil_id": janosi.get("soil_id"),
        "shear_ok": janosi.get("shear_ok"),
    }
    return float(spent_j) + add, add, honesty


def fold_janosi_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("janosi")
        if isinstance(physics, dict) and isinstance(physics.get("janosi"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["janosi_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "tau_probe_kpa": block.get("tau_probe_kpa"),
            "tau_inf_kpa": block.get("tau_inf_kpa"),
            "janosi_soil_id": block.get("soil_id"),
            "janosi_p_kpa": block.get("p_kpa"),
            "janosi_p_from_bekker_contact": block.get("p_from_bekker_contact"),
            "shear_ok": block.get("shear_ok"),
            "firm_tau_gt_soft": block.get("firm_tau_gt_soft"),
            "janosi_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "janosi_from_rust": True,
            "not_bevameter": True,
            "janosi_p_from_bekker_contact": bool(block.get("p_from_bekker_contact")),
        }
    )
    out["honesty"] = honesty
    return out
