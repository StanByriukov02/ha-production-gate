"""G4 ballistics+Kepler embed — Newton hop + vis-viva → Dual energy/KPI.

Physics (teaching · not MEASURED · not 6DOF · not n-body):

1) Rigid hop under constant g (vacuum ballistic):
     apex = v_up^2 / (2 g) · tof = 2 v_up / g · range = v_h * tof
   Dual pack (catalog-owned defaults · named Hostile mult):
     Safe    — catalog defaults.v_up / v_h
     Hostile — HOSTILE_V_MULT × catalog defaults (recover hop)
   Metric for spent: specific KE ½(v_up²+v_h²) — mass cancels in Dual share.
   Earth twin at same Δv: apex_moon > apex_earth (g Dual).

2) Vis-viva circular teaching:
     v = sqrt(mu/r) · T = 2π sqrt(a³/μ)
   Dual anchors from orbital_visviva catalog:
     Safe = GEO · Hostile = LEO
   Metric: v_orb²

3) Spent — dual_share only (no orphan 0.01 / 1e-6):
     spent = budget_j * |m| / (|m_safe| + |m_hostile|)
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]

# Named Dual pack: Hostile takeoff mult from rigid_hop dual_anchors (fallback 2.0).
def _hostile_v_mult() -> float:
    from production_gate.rigid_hop_on_v1 import load_rigid_hop_catalog

    a = (load_rigid_hop_catalog().get("dual_anchors") or {})
    return float(a.get("hostile_v_mult") if a.get("hostile_v_mult") is not None else 2.0)


HOSTILE_V_MULT = _hostile_v_mult()
# Teaching Dual slice into claim residual — unit J, not an orphan pressure→J fudge.
EMBED_SLICE_J = 1.0


def _hop_defaults() -> tuple[float, float, str]:
    from production_gate.rigid_hop_on_v1 import load_rigid_hop_catalog

    cat = load_rigid_hop_catalog()
    d = cat["defaults"]
    a = cat.get("dual_anchors") or {}
    body = str(a.get("body") or d.get("body") or "moon")
    return float(d["v_up_m_s"]), float(d["v_h_m_s"]), body


def _visviva_anchors() -> tuple[float, float, str]:
    from production_gate.orbital_visviva_on_v1 import load_orbital_catalog

    cat = load_orbital_catalog()
    a = cat["dual_anchors"]
    return float(a["leo_r_km"]), float(a["geo_r_km"]), str(a.get("body") or "earth")


def _peer_hop_metric(*, condition: ConditionId, v_up0: float, v_h0: float) -> float:
    if condition == "hostile":
        v_up, v_h = v_up0, v_h0
    else:
        v_up, v_h = HOSTILE_V_MULT * v_up0, HOSTILE_V_MULT * v_h0
    return 0.5 * (v_up * v_up + v_h * v_h)


def _peer_kepler_metric(*, condition: ConditionId, leo_r: float, geo_r: float, body: str) -> float:
    from production_gate.orbital_visviva_on_v1 import evaluate_orbital_visviva

    r_km = geo_r if condition == "hostile" else leo_r
    orb = evaluate_orbital_visviva(body=body, r_km=r_km, a_km=r_km)
    v = float(orb["v_m_s"])
    return v * v


def evaluate_ballistics_kepler(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
    mass_kg: float | None = None,
) -> dict[str, Any]:
    """Evaluate Newton hop + vis-viva from Rust; Dual-share spent into budget."""
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.orbital_visviva_on_v1 import evaluate_orbital_visviva
    from production_gate.rigid_hop_on_v1 import evaluate_rigid_hop

    v_up0, v_h0, hop_body = _hop_defaults()
    leo_r, geo_r, vis_body = _visviva_anchors()

    if condition == "hostile":
        v_up, v_h = HOSTILE_V_MULT * v_up0, HOSTILE_V_MULT * v_h0
        r_km = leo_r
    else:
        v_up, v_h = v_up0, v_h0
        r_km = geo_r

    hop = evaluate_rigid_hop(body=hop_body, v_up=v_up, v_h=v_h)
    hop_earth = evaluate_rigid_hop(body="earth", v_up=v_up, v_h=v_h)
    orb = evaluate_orbital_visviva(body=vis_body, r_km=r_km, a_km=r_km)

    apex = float(hop["apex_m"])
    tof = float(hop["tof_s"])
    rng = float(hop["range_m"])
    g = float(hop["g_m_s2"])
    specific_ke = 0.5 * (v_up * v_up + v_h * v_h)
    e_kin = None if mass_kg is None else 0.5 * float(mass_kg) * (v_up * v_up + v_h * v_h)
    # eta on specific KE when mass unknown: apex / specific_ke [= 1/g for pure ballistic]
    eta_denom = e_kin if e_kin is not None else specific_ke
    eta_hop = apex / max(float(eta_denom), 1e-9)

    hop_metric = specific_ke
    hop_peer = _peer_hop_metric(condition=condition, v_up0=v_up0, v_h0=v_h0)
    m_hop_s, m_hop_h = (hop_metric, hop_peer) if condition == "safe" else (hop_peer, hop_metric)
    hop_share = dual_share_receipt(
        metric=hop_metric,
        metric_safe=m_hop_s,
        metric_hostile=m_hop_h,
        budget_j=budget_j,
        metric_id="specific_ke_hop",
    )

    v_orb = float(orb["v_m_s"])
    period_s = float(orb["period_s"])
    kep_metric = v_orb * v_orb
    kep_peer = _peer_kepler_metric(condition=condition, leo_r=leo_r, geo_r=geo_r, body=vis_body)
    m_k_s, m_k_h = (kep_metric, kep_peer) if condition == "safe" else (kep_peer, kep_metric)
    kep_share = dual_share_receipt(
        metric=kep_metric,
        metric_safe=m_k_s,
        metric_hostile=m_k_h,
        budget_j=budget_j,
        metric_id="v_orb_sq",
    )

    hop_spent_j = hop_share["spent_j"]
    kepler_spent_j = kep_share["spent_j"]
    ballistics_spent_j = round(hop_spent_j + kepler_spent_j, 6)

    return {
        "schema": "ha_ballistics_kepler_embed_v1",
        "condition": condition,
        "hop_body": hop_body,
        "v_up_m_s": v_up,
        "v_h_m_s": v_h,
        "hostile_v_mult": HOSTILE_V_MULT,
        "g_m_s2": g,
        "apex_m": apex,
        "tof_s": tof,
        "range_m": rng,
        "specific_ke_j_per_kg": specific_ke,
        "e_kin_j": e_kin,
        "mass_kg": mass_kg,
        "eta_hop_m_per_j": eta_hop,
        "hop_spent_j": hop_spent_j,
        "hop_dual_share": hop_share,
        "apex_earth_twin_m": float(hop_earth["apex_m"]),
        "apex_moon_gt_earth": apex > float(hop_earth["apex_m"]),
        "orbit_r_km": r_km,
        "v_orb_m_s": v_orb,
        "period_s": period_s,
        "period_h": float(orb.get("period_h") or period_s / 3600.0),
        "kepler_spent_j": kepler_spent_j,
        "kepler_dual_share": kep_share,
        "ballistics_pressure": ballistics_spent_j,
        "ballistics_spent_j": ballistics_spent_j,
        "hop_oracle": hop.get("oracle"),
        "visviva_oracle": orb.get("oracle"),
        "honesty": {
            "ballistics_kepler_from_rust": True,
            "rigid_hop_from_rust": True,
            "visviva_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "v_from_catalog_defaults": True,
            "orbit_r_from_catalog_dual_anchors": True,
            "hostile_v_mult_named_dual_pack": HOSTILE_V_MULT,
            "not_measured": True,
            "not_6dof_multibody": True,
            "not_nbody": True,
            "vacuum_no_aero": True,
        },
    }


def attach_ballistics_kepler_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
    mass_kg: float | None = None,
) -> dict[str, Any]:
    out = dict(physics)
    # Prefer body contact mass when present on physics honesty / row.
    m = mass_kg
    if m is None:
        h = out.get("honesty") if isinstance(out.get("honesty"), dict) else {}
        raw = h.get("body_mass_kg")
        if raw is not None:
            m = float(raw)
    block = evaluate_ballistics_kepler(condition=condition, budget_j=budget_j, mass_kg=m)
    out["ballistics_kepler"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "ballistics_kepler_from_rust": True,
            "rigid_hop_from_rust": True,
            "visviva_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["honesty"] = honesty
    out["apex_m"] = float(block["apex_m"])
    out["eta_hop_m_per_j"] = float(block["eta_hop_m_per_j"])
    out["v_orb_m_s"] = float(block["v_orb_m_s"])
    return out


def apply_ballistics_kepler_to_spent(
    spent_j: float,
    ballistics_kepler: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(ballistics_kepler, dict):
        return float(spent_j), 0.0, {"ballistics_kepler_from_rust": False}
    add = float(ballistics_kepler.get("ballistics_spent_j") or 0.0)
    honesty = {
        "ballistics_kepler_from_rust": True,
        "spent_from_ballistics_kepler_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "ballistics_spent_j": add,
        "hop_spent_j": ballistics_kepler.get("hop_spent_j"),
        "kepler_spent_j": ballistics_kepler.get("kepler_spent_j"),
        "apex_m": ballistics_kepler.get("apex_m"),
        "eta_hop_m_per_j": ballistics_kepler.get("eta_hop_m_per_j"),
        "v_orb_m_s": ballistics_kepler.get("v_orb_m_s"),
        "rigid_hop_from_rust": bool(
            (ballistics_kepler.get("honesty") or {}).get("rigid_hop_from_rust")
        ),
        "visviva_from_rust": bool(
            (ballistics_kepler.get("honesty") or {}).get("visviva_from_rust")
        ),
    }
    return float(spent_j) + add, add, honesty


def fold_ballistics_kepler_into_closed_loop(
    closed_loop: dict[str, Any],
    physics: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(closed_loop)
    kpi = dict(out.get("kpi") or {})
    block = (
        physics.get("ballistics_kepler")
        if isinstance(physics, dict) and isinstance(physics.get("ballistics_kepler"), dict)
        else None
    )
    if not isinstance(block, dict):
        kpi["ballistics_kepler_from_rust"] = False
        out["kpi"] = kpi
        return out
    kpi.update(
        {
            "apex_m": block.get("apex_m"),
            "tof_s": block.get("tof_s"),
            "range_m": block.get("range_m"),
            "eta_hop_m_per_j": block.get("eta_hop_m_per_j"),
            "e_kin_j": block.get("e_kin_j"),
            "specific_ke_j_per_kg": block.get("specific_ke_j_per_kg"),
            "v_orb_m_s": block.get("v_orb_m_s"),
            "period_h": block.get("period_h"),
            "apex_moon_gt_earth": block.get("apex_moon_gt_earth"),
            "ballistics_kepler_from_rust": True,
            "rigid_hop_from_rust": True,
            "visviva_from_rust": True,
            "spent_dual_share_only": True,
        }
    )
    out["kpi"] = kpi
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "ballistics_kepler_from_rust": True,
            "rigid_hop_from_rust": True,
            "visviva_from_rust": True,
            "spent_dual_share_only": True,
            "not_6dof": True,
        }
    )
    out["honesty"] = honesty
    return out
