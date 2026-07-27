"""F6 U4 storm-env embed — coupled integrator → Dual spent / KPI.

Law already exists:
  run_concurrent_storm_env_physics (radiation rate + thermal column + overlap)

Dual from named storm profiles (U4 prove anchors · not new catalog):
  Safe    = STORM-THERMAL-ECLIPSE · seed=11
  Hostile = STORM-CME-MAX · seed=17 · intensity=0.85

Metric = dose_gy_final (integrated consequence · not static year dump)
Spent via dual_share only.
E3 env_budget remains static Fourier/eclipse/TID/Peukert point-sum —
this embed is the coupled storm consequence that E3 does not carry.
Not CREME FEM · not MEASURED.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0
HORIZON_H = 6.0
DT_H = 0.25

# Named Dual anchors — same storms as prove_universe_env_field_coupling_v1
DUAL_ANCHORS = {
    "safe_storm": "STORM-THERMAL-ECLIPSE",
    "hostile_storm": "STORM-CME-MAX",
    "safe_seed": 11,
    "hostile_seed": 17,
    "hostile_intensity": 0.85,
    "horizon_h": HORIZON_H,
    "dt_h": DT_H,
    "shield_g_cm2": 0.0,
}


def _storm_pack() -> dict[str, Any]:
    return dict(DUAL_ANCHORS)


def _run_side(*, hostile: bool, pack: dict[str, Any]) -> dict[str, Any]:
    from production_gate.universe_storm_engine_v1 import compose_storm
    from production_gate.universe_storm_state_v1 import run_concurrent_storm_env_physics

    if hostile:
        storm_id = str(pack["hostile_storm"])
        seed = int(pack["hostile_seed"])
        intensity = float(pack["hostile_intensity"])
    else:
        storm_id = str(pack["safe_storm"])
        seed = int(pack["safe_seed"])
        intensity = 1.0
    storm = compose_storm(storm_id, seed=seed, intensity_scale=intensity)
    row = run_concurrent_storm_env_physics(
        storm,
        horizon_h=float(pack["horizon_h"]),
        dt_h=float(pack["dt_h"]),
        shield_g_cm2=float(pack["shield_g_cm2"]),
    )
    dose = float(row.get("dose_gy_final") or 0.0)
    flare = float(row.get("radiation_mean_flare_scale") or 1.0)
    t_col = float(row.get("thermal_column_final_k") or 0.0)
    lag = float(row.get("subsurface_lag_k") or 0.0)
    steps = int(row.get("integrator_steps") or 0)
    return {
        "storm_id": storm_id,
        "seed": seed,
        "intensity_scale": intensity,
        "dose_gy_final": dose,
        "radiation_mean_flare_scale": flare,
        "thermal_column_final_k": t_col,
        "subsurface_lag_k": lag,
        "integrator_steps": steps,
        "overlap_peak": int(row.get("overlap_peak") or 0),
        "metric": abs(dose),
        "storm_verdict": row.get("verdict"),
        "integrator": row.get("integrator"),
    }


def evaluate_storm_env(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.win_hidden_subprocess_v1 import install_global_no_console_flash

    install_global_no_console_flash()
    pack = _storm_pack()
    side = _run_side(hostile=(condition == "hostile"), pack=pack)
    peer = _run_side(hostile=(condition != "hostile"), pack=pack)
    metric = float(side["metric"])
    peer_m = float(peer["metric"])
    m_s, m_h = (metric, peer_m) if condition == "safe" else (peer_m, metric)
    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="storm_dose_gy_final",
    )
    storm_ok = float(share["spent_j"]) < 0.5 * float(budget_j)
    return {
        "schema": "ha_storm_env_embed_v1",
        "condition": condition,
        "storm_id": side["storm_id"],
        "seed": side["seed"],
        "intensity_scale": side["intensity_scale"],
        "horizon_h": pack["horizon_h"],
        "dt_h": pack["dt_h"],
        "dose_gy_final": side["dose_gy_final"],
        "radiation_mean_flare_scale": side["radiation_mean_flare_scale"],
        "thermal_column_final_k": side["thermal_column_final_k"],
        "subsurface_lag_k": side["subsurface_lag_k"],
        "integrator_steps": side["integrator_steps"],
        "overlap_peak": side["overlap_peak"],
        "storm_pressure": metric,
        "storm_spent_j": share["spent_j"],
        "dual_share": share,
        "storm_ok": storm_ok,
        "storm_verdict": side["storm_verdict"],
        "integrator": side["integrator"],
        "dual_anchors": {
            "safe_storm": pack["safe_storm"],
            "hostile_storm": pack["hostile_storm"],
        },
        "honesty": {
            "env_storm_from_integrator": True,
            "storm_coupled_not_e3_point_sum": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_named_storm_dual_anchors": True,
            "not_measured": True,
            "not_creme_fem": True,
            "e3_env_budget_remains_static_point_sum": True,
        },
    }


def attach_storm_env_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_storm_env(condition=condition, budget_j=budget_j)
    out["storm_env"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "env_storm_from_integrator": True,
            "storm_coupled_not_e3_point_sum": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    out["storm_dose_gy"] = float(block["dose_gy_final"])
    out["storm_ok"] = bool(block["storm_ok"])
    return out


def apply_storm_env_to_spent(
    spent_j: float,
    storm_env: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(storm_env, dict):
        return float(spent_j), 0.0, {"env_storm_from_integrator": False}
    add = float(storm_env.get("storm_spent_j") or 0.0)
    honesty = {
        "env_storm_from_integrator": True,
        "spent_from_storm_env_integrator": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "storm_spent_j": add,
        "dose_gy_final": storm_env.get("dose_gy_final"),
        "storm_id": storm_env.get("storm_id"),
        "storm_ok": storm_env.get("storm_ok"),
        "storm_coupled_not_e3_point_sum": True,
    }
    return float(spent_j) + add, add, honesty


def fold_storm_env_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("storm_env")
        if isinstance(physics, dict) and isinstance(physics.get("storm_env"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["env_storm_from_integrator"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "storm_id": block.get("storm_id"),
            "storm_dose_gy": block.get("dose_gy_final"),
            "storm_flare_scale": block.get("radiation_mean_flare_scale"),
            "storm_thermal_column_k": block.get("thermal_column_final_k"),
            "storm_subsurface_lag_k": block.get("subsurface_lag_k"),
            "storm_integrator_steps": block.get("integrator_steps"),
            "storm_ok": block.get("storm_ok"),
            "env_storm_from_integrator": True,
            "storm_coupled_not_e3_point_sum": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "env_storm_from_integrator": True,
            "storm_coupled_not_e3_point_sum": True,
            "not_creme_fem": True,
        }
    )
    out["honesty"] = honesty
    return out
