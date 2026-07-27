"""G5 thermal-world embed — vacuum radiative BC + 1D column → Dual spent/KPI.

Physics (catalog-owned · Rust oracles · not Diviner MEASURED · not 3D FEM):

1) Radiative BC (Stefan–Boltzmann + solar absorb):
     q_rad   = eps * sigma * (T^4 - T_sky^4)
     q_solar = (1 - A) * S * illum
     q_net   = q_rad - q_solar
     q_in    = -q_net   (into surface)
   Dual zones from vacuum_radiative_bc catalog:
     Safe    = rim_sun  @ T=rim_effective (catalog sky)
     Hostile = psr_floor @ T=psr_effective (catalog sky), illum=0

2) One 1D column step (rho cp dT/dt = d/dz(k dT/dz) + q_in):
     q_in from radiative · T0 from catalog ambient · cryo path on PSR
     dt_h = 1.0 (one SI hour teaching step — unit choice, not a fudge scale)
     depth_m = 0.3 matches THERMAL_COLUMN_DUAL_LAW_BIND skin prove

3) Ops Dual metric — cold-trap adversity (NOT |q_net|, which favors sunlit rim):
     cold_trap_index = (T_rim - T_surf) / (T_rim - T_psr)   # 0 at rim · 1 at PSR
     metric = cold_trap_index + (1 if cryo else 0)
   KPI still surfaces q_net / dT_surface from Rust.

4) Spent via dual_share only:
     spent = budget_j * |m| / (|m_safe| + |m_hostile|)
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]

# Unit choice for one column step (SI hour) — not a Dual fudge multiplier.
COLUMN_DT_H = 1.0
COLUMN_N_NODES = 3
# Skin depth matching prove_thermal_column_dual_law_bind_v1 (n_nodes=3, depth_m=0.3).
COLUMN_DEPTH_M = 0.3
EMBED_SLICE_J = 1.0


def _catalog_temps() -> tuple[float, float, float]:
    from production_gate.vacuum_radiative_bc_on_v1 import load_radiative_bc_catalog

    cat = load_radiative_bc_catalog()
    sky = cat["sky_temperature_k"]
    solar = float(cat["constants"]["solar_constant_w_m2"])
    return float(sky["rim_effective"]), float(sky["psr_effective"]), solar


def _cold_trap_metric(*, t_surf_k: float, t_rim: float, t_psr: float, cryo: bool) -> float:
    span = max(t_rim - t_psr, 1e-9)
    cold_trap_index = max(0.0, (t_rim - float(t_surf_k)) / span)
    return cold_trap_index + (1.0 if cryo else 0.0)


def evaluate_thermal_world(*, condition: ConditionId, budget_j: float = EMBED_SLICE_J) -> dict[str, Any]:
    """Evaluate rim/PSR radiative + column step; Dual-share spent into budget."""
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.regolith_thermal_on_v1 import load_regolith_thermal_catalog
    from production_gate.thermal_column_on_v1 import ORACLE as COLUMN_ORACLE
    from production_gate.thermal_column_on_v1 import evaluate_column_step
    from production_gate.universe_env_thermal_column_v1 import (
        _column_dz,
        _rho_cp_from_bind,
        column_init_from_binds,
        thermal_envelope_k,
    )
    from production_gate.vacuum_radiative_bc_on_v1 import evaluate_radiative_bc

    # G14 Dual materials → G5 column (compact day vs loose cold) — same SoT anchors.
    k_cat = load_regolith_thermal_catalog()
    k_anch = k_cat.get("dual_anchors") or {}
    if condition == "hostile":
        material_id = str(k_anch.get("hostile_material") or "highland_regolith_loose")
    else:
        material_id = str(k_anch.get("safe_material") or "highland_regolith_compact")

    t_rim, t_psr, solar_s = _catalog_temps()
    from production_gate.vacuum_radiative_bc_on_v1 import load_radiative_bc_catalog

    rad_a = (load_radiative_bc_catalog().get("dual_anchors") or {})
    safe_zone = str(rad_a.get("safe_zone") or "rim_sun")
    hostile_zone = str(rad_a.get("hostile_zone") or "psr_floor")
    if condition == "hostile":
        zone = hostile_zone
        t_k = t_psr
        regime = "psr_floor"
        cryo = True
    else:
        zone = safe_zone
        t_k = t_rim
        regime = "rim_sunlit"
        cryo = False

    rad = evaluate_radiative_bc(zone=zone, t_k=t_k)
    q_net = float(rad["q_net_w_m2"])
    q_in = float(rad.get("q_in_surface_w_m2") if rad.get("q_in_surface_w_m2") is not None else -q_net)

    col = column_init_from_binds(regime_id=regime, n_nodes=COLUMN_N_NODES, depth_m=COLUMN_DEPTH_M)
    t_in = list(col.t_k)
    dz = _column_dz(col)
    rho, cp = _rho_cp_from_bind()
    rho_cp = float(rho) * float(cp)
    t_lo, t_hi = thermal_envelope_k(regime_id=regime)
    step = evaluate_column_step(
        t_k=t_in,
        dt_h=COLUMN_DT_H,
        dz_m=dz,
        rho_cp=rho_cp,
        q_in_w_m2=q_in,
        material_id=material_id,
        cryo=cryo,
        t_lo=t_lo,
        t_hi=t_hi,
    )
    dT = float(step["dT_surface_k"])

    metric = _cold_trap_metric(t_surf_k=t_k, t_rim=t_rim, t_psr=t_psr, cryo=cryo)
    # Peer Dual side (closed form — same catalog temps / cryo rule; no second Rust call needed).
    if condition == "hostile":
        peer = _cold_trap_metric(t_surf_k=t_rim, t_rim=t_rim, t_psr=t_psr, cryo=False)
        m_safe, m_hostile = peer, metric
    else:
        peer = _cold_trap_metric(t_surf_k=t_psr, t_rim=t_rim, t_psr=t_psr, cryo=True)
        m_safe, m_hostile = metric, peer

    share = dual_share_receipt(
        metric=metric,
        metric_safe=m_safe,
        metric_hostile=m_hostile,
        budget_j=budget_j,
        metric_id="cold_trap_index+cryo",
    )

    return {
        "schema": "ha_thermal_world_embed_v1",
        "condition": condition,
        "zone": zone,
        "regime_id": regime,
        "t_surf_k": t_k,
        "t_rim_k": t_rim,
        "t_psr_k": t_psr,
        "q_net_w_m2": q_net,
        "q_in_w_m2": q_in,
        "q_solar_w_m2": float(rad.get("q_solar_w_m2") or 0.0),
        "solar_constant_w_m2": solar_s,
        "dT_surface_k": dT,
        "cryo": cryo,
        "cold_trap_index": max(0.0, (t_rim - t_k) / max(t_rim - t_psr, 1e-9)),
        "thermal_metric": metric,
        "thermal_spent_j": share["spent_j"],
        "dual_share": share,
        "psr_cold_trap": condition == "hostile",
        "radiative_oracle": rad.get("oracle"),
        "column_oracle": step.get("oracle"),
        "column_material_id": material_id,
        "honesty": {
            "thermal_world_from_rust": True,
            "radiative_from_rust": True,
            "thermal_column_from_rust": True,
            "column_oracle_rust_only": step.get("oracle") == COLUMN_ORACLE,
            "column_material_from_regolith_dual_anchors": True,
            "temps_from_catalog_sky": True,
            "metric_cold_trap_not_qnet_abs": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "not_measured": True,
            "not_3d_fem": True,
            "not_diviner_timeseries": True,
            "column_dt_h_unit_choice": COLUMN_DT_H,
            "column_depth_m_from_thermal_column_dual_prove": COLUMN_DEPTH_M,
            "python_picard_not_on_dual_path": True,
        },
    }


def attach_thermal_world_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_thermal_world(condition=condition, budget_j=budget_j)
    out["thermal_world"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "thermal_world_from_rust": True,
            "radiative_from_rust": True,
            "thermal_column_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    out["thermal_metric"] = float(block["thermal_metric"])
    out["psr_cold_trap"] = bool(block["psr_cold_trap"])
    if block["psr_cold_trap"]:
        out["sinkage_risk"] = True  # cold-trap ops risk Dual — honesty not soil sinkage
    return out


def apply_thermal_world_to_spent(
    spent_j: float,
    thermal_world: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(thermal_world, dict):
        return float(spent_j), 0.0, {"thermal_world_from_rust": False}
    add = float(thermal_world.get("thermal_spent_j") or 0.0)
    honesty = {
        "thermal_world_from_rust": True,
        "spent_from_thermal_world_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "thermal_spent_j": add,
        "thermal_metric": thermal_world.get("thermal_metric"),
        "zone": thermal_world.get("zone"),
        "dT_surface_k": thermal_world.get("dT_surface_k"),
        "q_net_w_m2": thermal_world.get("q_net_w_m2"),
        "radiative_from_rust": bool((thermal_world.get("honesty") or {}).get("radiative_from_rust")),
        "thermal_column_from_rust": bool(
            (thermal_world.get("honesty") or {}).get("thermal_column_from_rust")
        ),
    }
    return float(spent_j) + add, add, honesty


def fold_thermal_world_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("thermal_world")
        if isinstance(physics, dict) and isinstance(physics.get("thermal_world"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["thermal_world_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "t_surf_k": block.get("t_surf_k"),
            "q_net_w_m2": block.get("q_net_w_m2"),
            "dT_surface_k": block.get("dT_surface_k"),
            "thermal_metric": block.get("thermal_metric"),
            "cold_trap_index": block.get("cold_trap_index"),
            "psr_cold_trap": block.get("psr_cold_trap"),
            "column_material_id": block.get("column_material_id"),
            "column_oracle": block.get("column_oracle"),
            "thermal_world_from_rust": True,
            "radiative_from_rust": True,
            "thermal_column_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "thermal_world_from_rust": True,
            "spent_dual_share_only": True,
            "not_3d_fem": True,
        }
    )
    out["honesty"] = honesty
    return out
