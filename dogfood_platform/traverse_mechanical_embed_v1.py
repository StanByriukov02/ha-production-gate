"""F7 traverse-mechanical embed — Bekker jerk consequence on Dual run.

Law already exists:
  traverse_symplectic_proxy · jerk ∝ Bekker severity(Rc, Δsinkage, drawbar deficit)

Dual from field lane soils (same as Bekker Dual):
  Safe    = firm_lab (or lane safe_soil_id)
  Hostile = soft_hostile (or lane hostile_soil_id)
  baseline for severity = Safe soil

Metric = mlcc_jerk_peak
Spent via dual_share only.
Not MEASURED FEM · ADAPT bearing adjunct stays adjunct.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0
DEFAULT_SAFE_SOIL = "firm_lab"
DEFAULT_HOSTILE_SOIL = "soft_hostile"
DEFAULT_G = 1.62


def _soils_from_physics(physics: dict[str, Any] | None) -> tuple[str, str, float]:
    dual = (
        physics.get("bekker_dual")
        if isinstance(physics, dict) and isinstance(physics.get("bekker_dual"), dict)
        else {}
    )
    safe = str(dual.get("safe_soil_id") or DEFAULT_SAFE_SOIL)
    hostile = str(dual.get("hostile_soil_id") or DEFAULT_HOSTILE_SOIL)
    g = DEFAULT_G
    if isinstance(physics, dict):
        load = physics.get("load") if isinstance(physics.get("load"), dict) else {}
        # g may live on honesty/field bind; keep lunar default if absent
        for key in ("g_mps2", "field_g_mps2"):
            if physics.get(key) is not None:
                g = float(physics[key])
                break
            if isinstance(physics.get("honesty"), dict) and physics["honesty"].get(key) is not None:
                g = float(physics["honesty"][key])
                break
        if load.get("g_mps2") is not None:
            g = float(load["g_mps2"])
    return safe, hostile, g


def evaluate_traverse_mechanical(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
    safe_soil_id: str = DEFAULT_SAFE_SOIL,
    hostile_soil_id: str = DEFAULT_HOSTILE_SOIL,
    g_mps2: float = DEFAULT_G,
) -> dict[str, Any]:
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt
    from dogfood_platform.lunar_traverse_mechanical_v1 import traverse_symplectic_proxy
    from dogfood_platform.win_hidden_subprocess_v1 import install_global_no_console_flash

    install_global_no_console_flash()
    soil = hostile_soil_id if condition == "hostile" else safe_soil_id
    side = traverse_symplectic_proxy(
        soil_id=soil,
        g_mps2=g_mps2,
        baseline_soil_id=safe_soil_id,
    )
    peer_soil = safe_soil_id if condition == "hostile" else hostile_soil_id
    peer = traverse_symplectic_proxy(
        soil_id=peer_soil,
        g_mps2=g_mps2,
        baseline_soil_id=safe_soil_id,
    )
    metric = abs(float(side.get("mlcc_jerk_peak") or 0.0))
    peer_m = abs(float(peer.get("mlcc_jerk_peak") or 0.0))
    m_s, m_h = (metric, peer_m) if condition == "safe" else (peer_m, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="mlcc_jerk_peak",
    )
    trav_ok = float(share["spent_j"]) < 0.5 * float(budget_j)
    return {
        "schema": "ha_traverse_mechanical_embed_v1",
        "condition": condition,
        "soil_id": soil,
        "safe_soil_id": safe_soil_id,
        "hostile_soil_id": hostile_soil_id,
        "g_mps2": g_mps2,
        "mlcc_jerk_peak": float(side.get("mlcc_jerk_peak") or 0.0),
        "bekker_severity": float(side.get("bekker_severity") or 0.0),
        "severity_total": float(side.get("severity_total") or 0.0),
        "path_km": float(side.get("path_km") or 0.0),
        "compaction_resistance_n": float(side.get("compaction_resistance_n") or 0.0),
        "sinkage_mm": float(side.get("sinkage_mm") or 0.0),
        "drawbar_pull_n": float(side.get("drawbar_pull_n") or 0.0),
        "sinkage_risk": bool(side.get("sinkage_risk")),
        "traverse_pressure": metric,
        "traverse_spent_j": share["spent_j"],
        "dual_share": share,
        "traverse_ok": trav_ok,
        "oracle": side.get("oracle"),
        "honesty": {
            "traverse_mechanical_from_bekker": True,
            "jerk_from_bekker_consequence": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "bekker_from_rust": True,
            "python_not_oracle": True,
            "not_measured": True,
            "adapt_bearing_adjunct": True,
            "jerk_teaching_scale_not_measured": True,
        },
    }


def attach_traverse_mechanical_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    safe, hostile, g = _soils_from_physics(physics)
    block = evaluate_traverse_mechanical(
        condition=condition,
        budget_j=budget_j,
        safe_soil_id=safe,
        hostile_soil_id=hostile,
        g_mps2=g,
    )
    out["traverse_mechanical"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "traverse_mechanical_from_bekker": True,
            "jerk_from_bekker_consequence": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    out["mlcc_jerk_peak"] = float(block["mlcc_jerk_peak"])
    out["bekker_severity"] = float(block["bekker_severity"])
    return out


def apply_traverse_mechanical_to_spent(
    spent_j: float,
    traverse_mechanical: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(traverse_mechanical, dict):
        return float(spent_j), 0.0, {"traverse_mechanical_from_bekker": False}
    add = float(traverse_mechanical.get("traverse_spent_j") or 0.0)
    honesty = {
        "traverse_mechanical_from_bekker": True,
        "spent_from_traverse_mechanical": True,
        "jerk_from_bekker_consequence": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "traverse_spent_j": add,
        "mlcc_jerk_peak": traverse_mechanical.get("mlcc_jerk_peak"),
        "soil_id": traverse_mechanical.get("soil_id"),
        "traverse_ok": traverse_mechanical.get("traverse_ok"),
    }
    return float(spent_j) + add, add, honesty


def fold_traverse_mechanical_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("traverse_mechanical")
        if isinstance(physics, dict) and isinstance(physics.get("traverse_mechanical"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["traverse_mechanical_from_bekker"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "mlcc_jerk_peak": block.get("mlcc_jerk_peak"),
            "bekker_severity": block.get("bekker_severity"),
            "traverse_path_km": block.get("path_km"),
            "traverse_soil_id": block.get("soil_id"),
            "traverse_ok": block.get("traverse_ok"),
            "traverse_mechanical_from_bekker": True,
            "jerk_from_bekker_consequence": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "traverse_mechanical_from_bekker": True,
            "jerk_from_bekker_consequence": True,
            "not_measured": True,
        }
    )
    out["honesty"] = honesty
    return out
