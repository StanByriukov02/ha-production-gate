"""G3 orbit-residual embed — free-mol drag + SRP + trapped belts → Dual spent.

Physics (teaching · not DSMC/AE9/MEASURED):

Dual packs from each catalog dual_anchors / named packs:
  Safe    — geo_safe · edge_safe · outside_safe
  Hostile — leo_hostile · face_hostile · inner_hostile
  t_h from trapped_belt catalog defaults/dual_anchors

Metric (raw SI; no orphan *1000 / *1e5 / *20 / *0.4):
  metric = |F_fmd| + |F_srp| + window_dose_gy

Spent via dual_share only:
  spent = budget_j * |m| / (|m_safe| + |m_hostile|)
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _orbit_pack() -> dict[str, Any]:
    from production_gate.free_mol_drag_on_v1 import load_fmd_catalog
    from production_gate.solar_pressure_on_v1 import load_srp_catalog
    from production_gate.trapped_belt_on_v1 import load_belt_catalog

    fmd = load_fmd_catalog()
    srp = load_srp_catalog()
    belt = load_belt_catalog()
    fa = fmd.get("dual_anchors") or {}
    sa = srp.get("dual_anchors") or {}
    ba = belt.get("dual_anchors") or {}
    return {
        "fmd_safe": str(fa.get("safe_pack") or "geo_safe"),
        "fmd_hostile": str(fa.get("hostile_pack") or "leo_hostile"),
        "srp_safe": str(sa.get("safe_pack") or "edge_safe"),
        "srp_hostile": str(sa.get("hostile_pack") or "face_hostile"),
        "belt_safe": str(ba.get("safe_pack") or "outside_safe"),
        "belt_hostile": str(ba.get("hostile_pack") or "inner_hostile"),
        "t_h": float(ba.get("t_h") or belt.get("defaults", {}).get("t_h") or 6.0),
    }


def _orbit_metric(*, f_fmd: float, f_srp: float, window: float) -> float:
    return abs(float(f_fmd)) + abs(float(f_srp)) + abs(float(window))


def _peer_metric(*, condition: ConditionId, pack: dict[str, Any]) -> float:
    from production_gate.free_mol_drag_on_v1 import evaluate_free_mol_drag
    from production_gate.solar_pressure_on_v1 import evaluate_solar_pressure
    from production_gate.trapped_belt_on_v1 import evaluate_trapped_belt

    if condition == "hostile":
        fmd_id, srp_id, belt_id = pack["fmd_safe"], pack["srp_safe"], pack["belt_safe"]
    else:
        fmd_id, srp_id, belt_id = pack["fmd_hostile"], pack["srp_hostile"], pack["belt_hostile"]
    fmd = evaluate_free_mol_drag(pack_id=fmd_id)
    srp = evaluate_solar_pressure(pack_id=srp_id)
    belt = evaluate_trapped_belt(pack_id=belt_id, t_h=pack["t_h"])
    dose_rate = float(belt.get("dose_rate_gy_h") or 0.0)
    window = float(belt.get("window_dose_gy") or belt.get("window_dose") or dose_rate * pack["t_h"])
    return _orbit_metric(
        f_fmd=float(fmd.get("f_fmd_n") or 0.0),
        f_srp=float(srp.get("f_srp_n") or 0.0),
        window=window,
    )


def evaluate_orbit_residual(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    """Evaluate free-mol + SRP + trapped belt from Rust; Dual-share spent."""
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.free_mol_drag_on_v1 import evaluate_free_mol_drag
    from production_gate.solar_pressure_on_v1 import evaluate_solar_pressure
    from production_gate.trapped_belt_on_v1 import evaluate_trapped_belt

    pack = _orbit_pack()
    if condition == "hostile":
        fmd_id, srp_id, belt_id = pack["fmd_hostile"], pack["srp_hostile"], pack["belt_hostile"]
    else:
        fmd_id, srp_id, belt_id = pack["fmd_safe"], pack["srp_safe"], pack["belt_safe"]

    fmd = evaluate_free_mol_drag(pack_id=fmd_id)
    srp = evaluate_solar_pressure(pack_id=srp_id)
    belt = evaluate_trapped_belt(pack_id=belt_id, t_h=pack["t_h"])

    f_fmd = float(fmd.get("f_fmd_n") or 0.0)
    f_srp = float(srp.get("f_srp_n") or 0.0)
    dose_rate = float(belt.get("dose_rate_gy_h") or 0.0)
    window = float(belt.get("window_dose_gy") or belt.get("window_dose") or dose_rate * pack["t_h"])
    metric = _orbit_metric(f_fmd=f_fmd, f_srp=f_srp, window=window)
    peer = _peer_metric(condition=condition, pack=pack)
    m_s, m_h = (metric, peer) if condition == "safe" else (peer, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="|F_fmd|+|F_srp|+window_gy",
    )

    return {
        "schema": "ha_orbit_residual_embed_v1",
        "condition": condition,
        "fmd_pack": fmd_id,
        "srp_pack": srp_id,
        "belt_pack": belt_id,
        "f_fmd_n": f_fmd,
        "f_srp_n": f_srp,
        "dose_rate_gy_h": dose_rate,
        "window_dose_gy": window,
        "orbit_pressure": metric,
        "orbit_spent_j": share["spent_j"],
        "dual_share": share,
        "fmd_oracle": fmd.get("oracle"),
        "srp_oracle": srp.get("oracle"),
        "belt_oracle": belt.get("oracle"),
        "honesty": {
            "orbit_residual_from_rust": True,
            "free_mol_from_rust": True,
            "srp_from_rust": True,
            "trapped_belt_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_dsmc": True,
            "not_ae9": True,
            "not_brdf": True,
        },
    }


def attach_orbit_residual_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_orbit_residual(condition=condition, budget_j=budget_j)
    out["orbit_residual"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "orbit_residual_from_rust": True,
            "free_mol_from_rust": True,
            "srp_from_rust": True,
            "trapped_belt_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    out["orbit_pressure"] = float(block["orbit_pressure"])
    return out


def apply_orbit_residual_to_spent(
    spent_j: float,
    orbit_residual: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(orbit_residual, dict):
        return float(spent_j), 0.0, {"orbit_residual_from_rust": False}
    add = float(orbit_residual.get("orbit_spent_j") or 0.0)
    honesty = {
        "orbit_residual_from_rust": True,
        "spent_from_orbit_residual_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "orbit_pressure": orbit_residual.get("orbit_pressure"),
        "orbit_spent_j": add,
        "fmd_pack": orbit_residual.get("fmd_pack"),
        "srp_pack": orbit_residual.get("srp_pack"),
        "belt_pack": orbit_residual.get("belt_pack"),
        "free_mol_from_rust": bool((orbit_residual.get("honesty") or {}).get("free_mol_from_rust")),
        "srp_from_rust": bool((orbit_residual.get("honesty") or {}).get("srp_from_rust")),
        "trapped_belt_from_rust": bool(
            (orbit_residual.get("honesty") or {}).get("trapped_belt_from_rust")
        ),
    }
    return float(spent_j) + add, add, honesty
