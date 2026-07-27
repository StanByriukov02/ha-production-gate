"""G13 radiation-rate embed — GCR window Dual KPI / spent.

Physics (PROXY teaching · not CREME FEM · not MEASURED):
  dD = (D_annual / H_year) * dt_h * clamp(flare, lo, hi)

Dual from catalog dual_anchors:
  Safe    = quiet_cruise · flare=1
  Hostile = polar_surface · flare=hi (gates.flare_hi)

Metric = window_dose_gy (+ see window if present)
Spent via dual_share only.
rad_ok = spent < half budget.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _rad_pack() -> dict[str, Any]:
    from production_gate.radiation_rate_on_v1 import load_radiation_rate_catalog

    cat = load_radiation_rate_catalog()
    a = cat["dual_anchors"]
    g = cat.get("gates") or {}
    d = cat.get("defaults") or {}
    return {
        "safe_site": str(a["safe_site"]),
        "hostile_site": str(a["hostile_site"]),
        "dt_h": float(a.get("dt_h") or d.get("dt_h") or 24.0),
        "safe_flare": float(a.get("safe_flare_scale") or g.get("flare_lo") or 1.0),
        "hostile_flare": float(a.get("hostile_flare_scale") or g.get("flare_hi") or 12.0),
    }


def _metric(row: dict[str, Any]) -> float:
    dose = float(row.get("window_dose_gy") or row.get("dose_gy") or 0.0)
    see = float(
        row.get("window_see_events")
        or row.get("window_see")
        or row.get("see_window")
        or 0.0
    )
    return abs(dose) + abs(see)


def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from production_gate.radiation_rate_on_v1 import evaluate_radiation_rate

    if condition == "hostile":
        site, flare = pack["safe_site"], pack["safe_flare"]
    else:
        site, flare = pack["hostile_site"], pack["hostile_flare"]
    row = evaluate_radiation_rate(dt_h=pack["dt_h"], flare_scale=flare, site_id=site)
    return _metric(row)


def evaluate_radiation_rate_embed(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.radiation_rate_on_v1 import evaluate_radiation_rate

    pack = _rad_pack()
    if condition == "hostile":
        site, flare = pack["hostile_site"], pack["hostile_flare"]
    else:
        site, flare = pack["safe_site"], pack["safe_flare"]
    row = evaluate_radiation_rate(dt_h=pack["dt_h"], flare_scale=flare, site_id=site)
    dose = float(row.get("window_dose_gy") or row.get("dose_gy") or 0.0)
    see = float(
        row.get("window_see_events")
        or row.get("window_see")
        or row.get("see_window")
        or 0.0
    )
    metric = _metric(row)
    peer = _peer_metric(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="window_dose+see",
    )
    rad_ok = float(share["spent_j"]) < 0.5 * float(budget_j)
    return {
        "schema": "ha_radiation_rate_embed_v1",
        "condition": condition,
        "site_id": site,
        "dt_h": pack["dt_h"],
        "flare_scale": flare,
        "window_dose_gy": dose,
        "window_see_events": see,
        "window_see": see,
        "rad_metric": metric,
        "rad_spent_j": share["spent_j"],
        "dual_share": share,
        "rad_ok": rad_ok,
        "radiation_oracle": row.get("oracle"),
        "honesty": {
            "radiation_rate_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_creme_fem": True,
            "proxy_teaching_class": True,
        },
    }


def attach_radiation_rate_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_radiation_rate_embed(condition=condition, budget_j=budget_j)
    out["radiation_rate"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update({"radiation_rate_from_rust": True, "spent_dual_share_only": True})
    out["honesty"] = honesty
    out["window_dose_gy"] = float(block["window_dose_gy"])
    out["rad_ok"] = bool(block["rad_ok"])
    return out


def apply_radiation_rate_to_spent(
    spent_j: float,
    radiation_rate: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(radiation_rate, dict):
        return float(spent_j), 0.0, {"radiation_rate_from_rust": False}
    add = float(radiation_rate.get("rad_spent_j") or 0.0)
    honesty = {
        "radiation_rate_from_rust": True,
        "spent_from_radiation_rate_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "rad_spent_j": add,
        "window_dose_gy": radiation_rate.get("window_dose_gy"),
        "site_id": radiation_rate.get("site_id"),
        "rad_ok": radiation_rate.get("rad_ok"),
    }
    return float(spent_j) + add, add, honesty


def fold_radiation_rate_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("radiation_rate")
        if isinstance(physics, dict) and isinstance(physics.get("radiation_rate"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["radiation_rate_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "window_dose_gy": block.get("window_dose_gy"),
            "window_see_events": block.get("window_see_events") or block.get("window_see"),
            "window_see": block.get("window_see_events") or block.get("window_see"),
            "rad_site_id": block.get("site_id"),
            "rad_ok": block.get("rad_ok"),
            "flare_scale": block.get("flare_scale"),
            "radiation_rate_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update({"radiation_rate_from_rust": True, "not_creme_fem": True})
    out["honesty"] = honesty
    return out
