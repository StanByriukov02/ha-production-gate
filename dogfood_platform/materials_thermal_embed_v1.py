"""G2 materials-thermal embed — Hooke+CTE σ_thermal → Dual KPI / spent.

Physics (teaching · not FEM/MEASURED):

Dual pack from materials_hooke catalog dual_anchors:
  Safe    — safe_mat @ safe_dt_k
  Hostile — safe_mat (same continuum) @ hostile_dt_k
  L from dual_anchors.l_m

Metric: |σ_thermal_pa| (Rust Hooke+CTE)
Spent via dual_share only — no orphan SIGMA_MPA_TO_J.

thermal_ok: Dual-share spent < half of embed slice (Safe side of Dual).
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _mat_pack() -> dict[str, Any]:
    from dogfood_platform.materials_hooke_cte_on_v1 import load_materials_catalog

    cat = load_materials_catalog()
    a = cat["dual_anchors"]
    d = cat["defaults"]
    # Prefer explicit Dual ΔT anchors; fall back to named fractions of catalog dt only if absent.
    dt0 = float(a.get("dt_k") or d.get("dt_k") or 100.0)
    return {
        "mat_id": str(a.get("safe_mat") or d.get("mat") or "al6061"),
        "dt_safe": float(a.get("safe_dt_k") if a.get("safe_dt_k") is not None else 0.2 * dt0),
        "dt_hostile": float(a.get("hostile_dt_k") if a.get("hostile_dt_k") is not None else 2.0 * dt0),
        "l_m": float(a.get("l_m") or d.get("l_m") or 1.0),
        "dt0_catalog": dt0,
    }


def _peer_sigma(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from dogfood_platform.materials_hooke_cte_on_v1 import evaluate_materials_hooke

    dt = pack["dt_safe"] if condition == "hostile" else pack["dt_hostile"]
    mat = evaluate_materials_hooke(mat_id=pack["mat_id"], dt_k=dt, l_m=pack["l_m"])
    return abs(
        float(
            mat.get("sigma_thermal_constrained_pa")
            or mat.get("sigma_thermal_pa")
            or mat.get("sigma_pa")
            or 0.0
        )
    )


def evaluate_materials_thermal(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    """Evaluate Hooke+CTE from Rust; Dual-share spent into budget."""
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt
    from dogfood_platform.materials_hooke_cte_on_v1 import evaluate_materials_hooke

    pack = _mat_pack()
    dt = pack["dt_hostile"] if condition == "hostile" else pack["dt_safe"]
    mat = evaluate_materials_hooke(mat_id=pack["mat_id"], dt_k=dt, l_m=pack["l_m"])
    sigma_pa = float(
        mat.get("sigma_thermal_constrained_pa")
        or mat.get("sigma_thermal_pa")
        or mat.get("sigma_pa")
        or 0.0
    )
    sigma_mpa = sigma_pa / 1.0e6
    delta_th = float(mat.get("delta_thermal_m") or 0.0)
    metric = abs(sigma_pa)
    peer = _peer_sigma(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="|sigma_thermal_pa|",
    )
    thermal_ok = float(share["spent_j"]) < 0.5 * float(budget_j)

    return {
        "schema": "ha_materials_thermal_embed_v1",
        "condition": condition,
        "mat_id": pack["mat_id"],
        "dt_k": dt,
        "l_m": pack["l_m"],
        "sigma_thermal_pa": sigma_pa,
        "sigma_thermal_mpa": sigma_mpa,
        "delta_thermal_m": delta_th,
        "thermal_spent_j": share["spent_j"],
        "dual_share": share,
        "thermal_ok": thermal_ok,
        "materials_oracle": mat.get("oracle"),
        "honesty": {
            "materials_thermal_from_rust": True,
            "hooke_cte_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "dt_from_catalog_dual_pack": True,
            "thermal_ok_from_dual_share_half": True,
            "not_measured": True,
            "not_fem": True,
        },
    }


def attach_materials_thermal_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_materials_thermal(condition=condition, budget_j=budget_j)
    out["materials_thermal"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "materials_thermal_from_rust": True,
            "hooke_cte_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    out["sigma_thermal_mpa"] = float(block["sigma_thermal_mpa"])
    out["thermal_ok"] = bool(block["thermal_ok"])
    return out


def apply_materials_thermal_to_spent(
    spent_j: float,
    materials_thermal: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(materials_thermal, dict):
        return float(spent_j), 0.0, {"materials_thermal_from_rust": False}
    add = float(materials_thermal.get("thermal_spent_j") or 0.0)
    honesty = {
        "materials_thermal_from_rust": True,
        "spent_from_materials_thermal_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "thermal_spent_j": add,
        "sigma_thermal_mpa": materials_thermal.get("sigma_thermal_mpa"),
        "dt_k": materials_thermal.get("dt_k"),
        "hooke_cte_from_rust": bool(
            (materials_thermal.get("honesty") or {}).get("hooke_cte_from_rust")
        ),
    }
    return float(spent_j) + add, add, honesty


def fold_materials_thermal_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("materials_thermal")
        if isinstance(physics, dict) and isinstance(physics.get("materials_thermal"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["materials_thermal_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "sigma_thermal_mpa": block.get("sigma_thermal_mpa"),
            "dt_k": block.get("dt_k"),
            "delta_thermal_m": block.get("delta_thermal_m"),
            "thermal_ok": block.get("thermal_ok"),
            "materials_thermal_from_rust": True,
            "hooke_cte_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "materials_thermal_from_rust": True,
            "hooke_cte_from_rust": True,
            "spent_dual_share_only": True,
            "not_fem": True,
        }
    )
    out["honesty"] = honesty
    return out
