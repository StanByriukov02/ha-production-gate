"""E3 env-budget embed — Fourier + eclipse + TID + Peukert → Dual residual.

Packs from catalog dual_anchors (not hard-coded IDs as SoT).
Metric (raw SI adversity; no orphan /1000 or 0.1 scales):
  metric = 1/q_flux + f_eclipse + tid_proxy + 1/t_discharge_h
Spent via dual_share only:
  spent = budget_j * |m| / (|m_safe| + |m_hostile|)
budget_factor = 1 - spent/budget  (Safe residual capacity Dual)
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _env_pack() -> dict[str, Any]:
    from dogfood_platform.battery_peukert_on_v1 import load_battery_catalog
    from dogfood_platform.eclipse_umbra_on_v1 import load_eclipse_catalog
    from dogfood_platform.fourier_flux_on_v1 import load_fourier_catalog
    from dogfood_platform.rad_damage_tid_on_v1 import load_tid_catalog

    f = load_fourier_catalog()
    e = load_eclipse_catalog()
    t = load_tid_catalog()
    b = load_battery_catalog()
    fa, ea, ta, ba = f["dual_anchors"], e["dual_anchors"], t["dual_anchors"], b["dual_anchors"]
    bd = b.get("defaults") or {}
    return {
        "fourier_safe": str(fa["safe_pack"]),
        "fourier_hostile": str(fa["hostile_pack"]),
        "eclipse_safe": str(ea["safe_orbit"]),
        "eclipse_hostile": str(ea["hostile_orbit"]),
        "tid_safe": str(ta["safe_pack"]),
        "tid_hostile": str(ta["hostile_pack"]),
        "tid_t_h": float(ta.get("t_h") or 48.0),
        "batt_safe": str(ba.get("safe_pack") or bd.get("pack") or "scout_safe"),
        "batt_hostile": str(ba.get("hostile_pack") or "scout_hostile"),
        "batt_i_a": float(ba.get("i_a") or bd.get("i_a") or 8.0),
        "batt_soc": float(ba.get("soc") or bd.get("soc") or 0.5),
    }


def _env_metric(*, q_flux: float, f_ecl: float, tid: float, t_batt: float) -> float:
    return (
        1.0 / max(float(q_flux), 1e-12)
        + max(float(f_ecl), 0.0)
        + max(float(tid), 0.0)
        + 1.0 / max(float(t_batt), 1e-12)
    )


def _eval_side(pack: dict[str, Any], *, hostile: bool) -> dict[str, Any]:
    from dogfood_platform.battery_peukert_on_v1 import evaluate_battery_peukert
    from dogfood_platform.eclipse_umbra_on_v1 import evaluate_eclipse_umbra
    from dogfood_platform.fourier_flux_on_v1 import evaluate_fourier_flux
    from dogfood_platform.rad_damage_tid_on_v1 import evaluate_rad_damage_tid

    if hostile:
        f_id, e_id, t_id, b_id = (
            pack["fourier_hostile"],
            pack["eclipse_hostile"],
            pack["tid_hostile"],
            pack["batt_hostile"],
        )
    else:
        f_id, e_id, t_id, b_id = (
            pack["fourier_safe"],
            pack["eclipse_safe"],
            pack["tid_safe"],
            pack["batt_safe"],
        )
    fourier = evaluate_fourier_flux(pack_id=f_id)
    eclipse = evaluate_eclipse_umbra(orbit_id=e_id)
    tid = evaluate_rad_damage_tid(pack_id=t_id, t_h=pack["tid_t_h"])
    batt = evaluate_battery_peukert(pack_id=b_id, i_a=pack["batt_i_a"], soc=pack["batt_soc"])
    q_flux = float(fourier["q_flux_w_m2"])
    f_ecl = float(eclipse["f_eclipse"])
    tid_proxy = float(tid["damage_proxy"])
    t_batt = float(batt["t_discharge_h"])
    return {
        "fourier_pack": f_id,
        "eclipse_orbit": e_id,
        "tid_pack": t_id,
        "battery_pack": b_id,
        "q_flux_w_m2": q_flux,
        "f_eclipse": f_ecl,
        "tid_damage_proxy": tid_proxy,
        "t_discharge_h": t_batt,
        "metric": _env_metric(q_flux=q_flux, f_ecl=f_ecl, tid=tid_proxy, t_batt=t_batt),
        "fourier_oracle": fourier.get("oracle"),
        "eclipse_oracle": eclipse.get("oracle"),
        "tid_oracle": tid.get("oracle"),
        "battery_oracle": batt.get("oracle"),
    }


def evaluate_env_budget(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    """Evaluate env oracles from Rust; Dual-share spent + budget_factor."""
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt

    pack = _env_pack()
    side = _eval_side(pack, hostile=(condition == "hostile"))
    peer = _eval_side(pack, hostile=(condition != "hostile"))
    metric = float(side["metric"])
    peer_m = float(peer["metric"])
    m_s, m_h = (metric, peer_m) if condition == "safe" else (peer_m, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="1/q+f_ecl+tid+1/t_batt",
    )
    env_spent = float(share["spent_j"])
    budget_factor = 1.0 - (env_spent / max(float(budget_j), 1e-9))
    budget_factor = min(max(budget_factor, 0.05), 1.0)

    return {
        "schema": "ha_env_budget_embed_v1",
        "condition": condition,
        "fourier_pack": side["fourier_pack"],
        "eclipse_orbit": side["eclipse_orbit"],
        "tid_pack": side["tid_pack"],
        "battery_pack": side["battery_pack"],
        "q_flux_w_m2": side["q_flux_w_m2"],
        "f_eclipse": side["f_eclipse"],
        "tid_damage_proxy": side["tid_damage_proxy"],
        "t_discharge_h": side["t_discharge_h"],
        "env_pressure": metric,
        "budget_factor": budget_factor,
        "env_spent_j": env_spent,
        "dual_share": share,
        "fourier_oracle": side["fourier_oracle"],
        "eclipse_oracle": side["eclipse_oracle"],
        "tid_oracle": side["tid_oracle"],
        "battery_oracle": side["battery_oracle"],
        "honesty": {
            "env_budget_from_rust": True,
            "fourier_from_rust": True,
            "eclipse_from_rust": True,
            "tid_from_rust": True,
            "peukert_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_creme_ae9": True,
        },
    }


def attach_env_budget_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    env = evaluate_env_budget(condition=condition, budget_j=budget_j)
    out["env_budget"] = env
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "env_budget_from_rust": True,
            "fourier_from_rust": True,
            "eclipse_from_rust": True,
            "tid_from_rust": True,
            "peukert_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    return out


def apply_env_budget_to_spent(
    spent_j: float,
    env_budget: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    """Add Dual-share env spent — Hostile burns residual harder."""
    if not isinstance(env_budget, dict):
        return float(spent_j), 0.0, {"env_budget_from_rust": False, "budget_factor": 1.0}
    env_spent = float(env_budget.get("env_spent_j") or 0.0)
    factor = float(env_budget.get("budget_factor") or 1.0)
    honesty = {
        "env_budget_from_rust": True,
        "spent_from_env_budget_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "budget_factor": factor,
        "env_pressure": env_budget.get("env_pressure"),
        "env_spent_j": env_spent,
        "fourier_pack": env_budget.get("fourier_pack"),
        "eclipse_orbit": env_budget.get("eclipse_orbit"),
        "tid_pack": env_budget.get("tid_pack"),
        "battery_pack": env_budget.get("battery_pack"),
        "fourier_from_rust": bool((env_budget.get("honesty") or {}).get("fourier_from_rust")),
        "eclipse_from_rust": bool((env_budget.get("honesty") or {}).get("eclipse_from_rust")),
        "tid_from_rust": bool((env_budget.get("honesty") or {}).get("tid_from_rust")),
        "peukert_from_rust": bool((env_budget.get("honesty") or {}).get("peukert_from_rust")),
    }
    return float(spent_j) + env_spent, env_spent, honesty
