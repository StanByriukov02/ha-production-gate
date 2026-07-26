"""W_regolith_robot — wheel traverse → sinkage → ingress disturbance loop.

Terramech sinkage/Rc/drawbar: Rust `ha_physics_gate_bekker` via KLS-1 catalog soil.
Ingress mult: quarantined heuristic sidecar (not Bekker oracle).
"""
from __future__ import annotations

from typing import Any, Literal

from dogfood_platform.lunar_dust_ingress_v1 import SiteZone
from dogfood_platform.lunar_regolith_bearing_v1 import (
    RegolithBearingClass,
    evaluate_bearing_sinkage,
    sinkage_mm_for_pressure_kpa_kls1,
    wheel_terramechanics_class,
)
from dogfood_platform.lunar_zone_table_v1 import ZONES
from dogfood_platform.terramech_bekker_on_v1 import ORACLE as BEKKER_ORACLE

_G_MOON = 1.62


def _contact_pressure_kpa(
    *,
    rover_mass_kg: float,
    wheel_diameter_cm: float,
    wheel_width_cm: float,
    n_wheels: int = 4,
) -> float:
    weight_n = rover_mass_kg * _G_MOON
    patch_m2 = (wheel_width_cm / 100.0) * (wheel_diameter_cm / 200.0)
    patch_m2 = max(patch_m2, 1e-5)
    return (weight_n / max(n_wheels, 1)) / patch_m2 / 1000.0


def simulate_traverse_segment(
    meters: float,
    *,
    wheel_diameter_cm: float = 20.0,
    wheel_width_cm: float = 8.0,
    rover_mass_kg: float = 150.0,
    zone: SiteZone = "massif_traverse",
    bearing_class: RegolithBearingClass = "MEDIUM",
    n_wheels: int = 4,
) -> dict[str, Any]:
    """One traverse leg: Rust Bekker/KLS-1 sinkage + ADAPT bearing gate + quarantined ingress."""
    massif = ZONES["massif_traverse"]
    slope = float(massif["slope_max_deg"])
    limit = float(massif["slope_limit_deg"])
    wheel = wheel_terramechanics_class(wheel_diameter_cm=wheel_diameter_cm)
    contact_kpa = _contact_pressure_kpa(
        rover_mass_kg=rover_mass_kg,
        wheel_diameter_cm=wheel_diameter_cm,
        wheel_width_cm=wheel_width_cm,
        n_wheels=n_wheels,
    )
    plate_radius_m = max(wheel_width_cm / 200.0, 0.02)
    kls1_sink = sinkage_mm_for_pressure_kpa_kls1(contact_kpa, plate_radius_m=plate_radius_m)
    bearing = evaluate_bearing_sinkage(
        bearing_class=bearing_class,
        contact_pressure_kpa=contact_kpa,
        penetration_depth_mm=float(kls1_sink["sinkage_mm"]),
        slope_deg=slope,
        slope_limit_deg=limit,
    )
    # Quarantined heuristic — NOT Bekker / NOT on terramech oracle surface.
    ingress_mult = 1.0
    if zone == "massif_traverse":
        ingress_mult *= 1.15
    elif zone == "rim_sun":
        ingress_mult *= 1.05
    if wheel["wheel_class"] == "SMALL_WHEEL":
        ingress_mult *= 1.10
    if bearing["sinkage_risk"]:
        ingress_mult *= 1.25
    sink_mm = float(kls1_sink["sinkage_mm"])
    ingress_mult *= 1.0 + min(0.35, contact_kpa / 25.0)
    ingress_mult *= 1.0 + min(0.20, sink_mm / 35.0)
    if meters > 0.0:
        ingress_mult *= 1.0 + min(0.5, meters / 500.0)
    ingress_heuristic = {
        "schema": "ingress_disturbance_heuristic_v0",
        "ingress_disturbance_mult": round(ingress_mult, 4),
        "honesty": {
            "not_bekker": True,
            "not_wong": True,
            "magic_constant": True,
            "quarantined_from_oracle_surface": True,
            "not_measured": True,
            "note": "wear/material sidecar — never cite as terramech oracle",
        },
    }
    return {
        "meters": round(meters, 3),
        "zone": zone,
        "n_wheels": n_wheels,
        "wheel": wheel,
        "contact_pressure_kpa": round(contact_kpa, 2),
        "sinkage_mm": float(kls1_sink["sinkage_mm"]),
        "kls1_p_kpa": float(kls1_sink["verified_p_kpa"]),
        "compaction_resistance_n": float(kls1_sink.get("compaction_resistance_n") or 0.0),
        "drawbar_pull_n": kls1_sink.get("drawbar_pull_n"),
        "bearing": bearing,
        # Compat for wear bus — honesty marks quarantine.
        "ingress_disturbance_mult": float(ingress_heuristic["ingress_disturbance_mult"]),
        "ingress_disturbance_heuristic": ingress_heuristic,
        "traverse_feasible": bool(bearing["traverse_feasible"]),
        "l0_cites": ["KIM-JASS-2021-TABLE3", "MEIRION-GRIFFITH-ISTVS-2011-L0-01", "GAP-MR-11"],
        "oracle": BEKKER_ORACLE,
        "soil_id": "kls1_kim_jass_t3",
        "honesty": {
            "bekker_from_rust": True,
            "python_not_oracle": True,
            "ingress_quarantined_from_oracle": True,
            "ingress_is_heuristic_not_bekker": True,
            "adapt_bearing_is_adjunct": True,
            "not_measured": True,
        },
    }


def compare_traverse_ingress_paths(
    *,
    n_sols: float = 30.0,
    meters_per_sol: float = 100.0,
    zone: SiteZone = "massif_traverse",
) -> dict[str, Any]:
    from dogfood_platform.lunar_robot_articulation_v1 import ingress_for_articulation

    idle = ingress_for_articulation(
        joint_tier="hip_actuator",
        zone=zone,
        ingress_disturbance_mult=simulate_traverse_segment(0.0, zone=zone)["ingress_disturbance_mult"],
    )
    active = ingress_for_articulation(
        joint_tier="hip_actuator",
        zone=zone,
        ingress_disturbance_mult=simulate_traverse_segment(meters_per_sol, zone=zone)[
            "ingress_disturbance_mult"
        ],
    )
    idle_acc = float(idle["effective_rate_g_m2_per_sol"]) * n_sols
    active_acc = float(active["effective_rate_g_m2_per_sol"]) * n_sols
    idle_seg = simulate_traverse_segment(0.0, zone=zone)
    active_seg = simulate_traverse_segment(meters_per_sol, zone=zone)
    return {
        "compare_id": "WHEEL_LOCOMOTION_INGRESS_COMPARE_v1",
        "zone": zone,
        "n_sols": n_sols,
        "meters_per_sol": meters_per_sol,
        "idle_segment": idle_seg,
        "active_segment": active_seg,
        "idle_accumulation_proxy_g_m2": round(idle_acc, 5),
        "active_accumulation_proxy_g_m2": round(active_acc, 5),
        "traverse_raises_accumulation": active_acc > idle_acc,
        "variants_diverge": active_acc != idle_acc,
        "oracle": BEKKER_ORACLE,
        "honesty": {
            "bekker_from_rust": True,
            "ingress_quarantined_from_oracle": True,
        },
    }
