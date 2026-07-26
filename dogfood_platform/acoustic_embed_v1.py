"""G8 acoustic-wave embed — vp/vs + Beer atten → Dual KPI / spent.

Physics (teaching · not seismogram / FEM):
  vp = sqrt((K+4/3 G)/ρ); vs = sqrt(G/ρ); T = exp(-α L)

Dual from catalog dual_anchors:
  Safe    = basalt_firm (high vp · high T)
  Hostile = regolith_soft (low vp · low T)

Metric adversity = (1 - T) + 1/max(vp, eps)
Spent via dual_share only.
sense_ok = spent < half budget (Safe side of Dual).
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _acoustic_pack() -> dict[str, Any]:
    from dogfood_platform.acoustic_wave_on_v1 import load_acoustic_catalog

    cat = load_acoustic_catalog()
    a = cat["dual_anchors"]
    d = cat["defaults"]
    return {
        "safe_medium": str(a["safe_medium"]),
        "hostile_medium": str(a["hostile_medium"]),
        "path_m": float(a.get("path_m") or d["path_m"]),
    }


def _metric(*, transmittance: float, vp: float) -> float:
    return max(0.0, 1.0 - float(transmittance)) + 1.0 / max(float(vp), 1e-9)


def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from dogfood_platform.acoustic_wave_on_v1 import evaluate_acoustic_wave

    mid = pack["safe_medium"] if condition == "hostile" else pack["hostile_medium"]
    row = evaluate_acoustic_wave(medium_id=mid, path_m=pack["path_m"])
    return _metric(transmittance=float(row["transmittance"]), vp=float(row["vp_m_s"]))


def evaluate_acoustic_embed(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    from dogfood_platform.acoustic_wave_on_v1 import evaluate_acoustic_wave
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt

    pack = _acoustic_pack()
    medium = pack["hostile_medium"] if condition == "hostile" else pack["safe_medium"]
    row = evaluate_acoustic_wave(medium_id=medium, path_m=pack["path_m"])
    vp = float(row["vp_m_s"])
    vs = float(row["vs_m_s"])
    t = float(row["transmittance"])
    metric = _metric(transmittance=t, vp=vp)
    peer = _peer_metric(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="(1-T)+1/vp",
    )
    sense_ok = float(share["spent_j"]) < 0.5 * float(budget_j)
    return {
        "schema": "ha_acoustic_embed_v1",
        "condition": condition,
        "medium_id": medium,
        "path_m": pack["path_m"],
        "vp_m_s": vp,
        "vs_m_s": vs,
        "transmittance": t,
        "acoustic_metric": metric,
        "acoustic_spent_j": share["spent_j"],
        "dual_share": share,
        "sense_ok": sense_ok,
        "acoustic_oracle": row.get("oracle"),
        "honesty": {
            "acoustic_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_seismogram": True,
            "not_fem": True,
        },
    }


def attach_acoustic_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_acoustic_embed(condition=condition, budget_j=budget_j)
    out["acoustic"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update({"acoustic_from_rust": True, "spent_dual_share_only": True})
    out["honesty"] = honesty
    out["vp_m_s"] = float(block["vp_m_s"])
    out["acoustic_sense_ok"] = bool(block["sense_ok"])
    return out


def apply_acoustic_to_spent(
    spent_j: float,
    acoustic: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(acoustic, dict):
        return float(spent_j), 0.0, {"acoustic_from_rust": False}
    add = float(acoustic.get("acoustic_spent_j") or 0.0)
    honesty = {
        "acoustic_from_rust": True,
        "spent_from_acoustic_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "acoustic_spent_j": add,
        "vp_m_s": acoustic.get("vp_m_s"),
        "transmittance": acoustic.get("transmittance"),
        "sense_ok": acoustic.get("sense_ok"),
        "medium_id": acoustic.get("medium_id"),
    }
    return float(spent_j) + add, add, honesty


def fold_acoustic_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("acoustic")
        if isinstance(physics, dict) and isinstance(physics.get("acoustic"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["acoustic_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "vp_m_s": block.get("vp_m_s"),
            "vs_m_s": block.get("vs_m_s"),
            "acoustic_transmittance": block.get("transmittance"),
            "acoustic_sense_ok": block.get("sense_ok"),
            "acoustic_medium_id": block.get("medium_id"),
            "acoustic_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update({"acoustic_from_rust": True, "not_seismogram": True})
    out["honesty"] = honesty
    return out
