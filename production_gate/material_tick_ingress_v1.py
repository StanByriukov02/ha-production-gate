"""Material tick ingress resolver v1 — single thermometer for HAL · wear · coupling.

Priority: carrier.material_physics → material_physics_bind + port → HAL lunar_physics.
TABU: claim HAL hardcoded wheel = catalog truth when bind present.
"""
from __future__ import annotations

from typing import Any

PROOF_TIER = "MATERIAL_TICK_INGRESS_SLICE"
DEFAULT_VARIANT = "scout_default_medium"
VALID_SITE_ZONES = ("rim_sun", "massif_traverse", "psr_floor")


def resolve_variant_id_from_state(state: dict[str, Any]) -> str:
    mp_bind = state.get("material_physics_bind")
    if isinstance(mp_bind, dict) and mp_bind.get("variant_id"):
        return str(mp_bind["variant_id"])
    return DEFAULT_VARIANT


def _profile_zone(profile_id: str) -> str:
    from production_gate.robot_os_hal_lunar_profile_v1 import _PROFILE_ZONE

    return _PROFILE_ZONE.get(profile_id, "massif_traverse")


def init_material_zone_cmr_bind(
    state: dict[str, Any],
    *,
    site_zone: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Enable per-tick site_zone resolution for CMR / coupling ENV_IN."""
    state["material_zone_cmr_bind"] = {
        "enabled": enabled,
        "site_zone": site_zone,
        "proof_tier": PROOF_TIER,
        "oracle": "DUST_INGRESS_BIND_v1",
    }
    return state["material_zone_cmr_bind"]


def material_zone_cmr_enabled(state: dict[str, Any]) -> bool:
    row = state.get("material_zone_cmr_bind") or {}
    if not row:
        return True
    return bool(row.get("enabled", True))


def resolve_site_zone_from_state(state: dict[str, Any], carrier_id: str) -> str:
    """Resolve site_zone for live tick — carrier override → bind → lunar → material → profile."""
    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    if carrier.get("site_zone"):
        return str(carrier["site_zone"])
    bind = state.get("material_zone_cmr_bind") or {}
    if material_zone_cmr_enabled(state) and bind.get("site_zone"):
        return str(bind["site_zone"])
    lunar = dict(carrier.get("lunar_physics") or {})
    if lunar.get("zone"):
        return str(lunar["zone"])
    mp = dict(carrier.get("material_physics") or {})
    if mp.get("zone"):
        return str(mp["zone"])
    profile_id = str(state.get("profile_id") or "lunar_crater_5km")
    return _profile_zone(profile_id)


def evaluate_lunar_row_with_material(
    step_m: float,
    *,
    profile_id: str,
    variant_id: str | None = None,
    state: dict[str, Any] | None = None,
    mass_kg: float | None = None,
    respect_factory_tread_slot: bool = True,
    site_zone: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Terramech lunar row + optional material_physics port row."""
    from production_gate.material_physics_port_v1 import compute_env_in_from_material
    from production_gate.robot_os_hal_lunar_profile_v1 import WORLD_ID, WORLD_ORACLE, G_MOON_MPS2
    from production_gate.terramech_bekker_on_v1 import ORACLE as BEKKER_ORACLE

    vid = variant_id or (resolve_variant_id_from_state(state) if state else None)
    zone = site_zone or _profile_zone(profile_id)
    meters = max(float(step_m), 0.01)

    if vid:
        material = compute_env_in_from_material(
            variant_id=vid,
            zone=zone,
            step_m=meters,
            respect_factory_tread_slot=respect_factory_tread_slot,
        )
        terr = dict(material.get("terramech") or {})
        bearing = terr.get("bearing") or {}
        lunar = {
            "oracle": terr.get("oracle") or BEKKER_ORACLE,
            "world_oracle": WORLD_ORACLE,
            "world_id": WORLD_ID,
            "g_mps2": G_MOON_MPS2,
            "zone": zone,
            "step_m": round(meters, 4),
            "traverse_feasible": bool(material.get("traverse_feasible")),
            "sinkage_mm": float(material.get("sinkage_mm") or 0.0),
            "ingress_disturbance_mult": float(material["ingress_disturbance_mult"]),
            "ingress_disturbance_heuristic": terr.get("ingress_disturbance_heuristic"),
            "contact_pressure_kpa": float(material.get("contact_pressure_kpa") or 0.0),
            "compaction_resistance_n": terr.get("compaction_resistance_n"),
            "drawbar_pull_n": terr.get("drawbar_pull_n"),
            "bearing_class": bearing.get("bearing_class") or material.get("bearing_class"),
            "sinkage_risk": bool(bearing.get("sinkage_risk")),
            "ingress_source": "material_physics_bus",
            "material_variant_id": material.get("variant_id"),
            "material_id": material.get("material_id"),
            "factory_tread_material_id": material.get("factory_tread_material_id"),
            "honesty": terr.get("honesty")
            or {
                "bekker_from_rust": True,
                "ingress_quarantined_from_oracle": True,
            },
        }
        return lunar, material

    from production_gate.robot_os_hal_lunar_profile_v1 import evaluate_lunar_traverse_tick

    lunar = evaluate_lunar_traverse_tick(
        meters,
        profile_id=profile_id,
        mass_kg=mass_kg or 20.0,
        use_material_catalog=False,
    )
    lunar["ingress_source"] = "lunar_physics_hal"
    return lunar, None


def attach_material_physics_to_carrier(
    state: dict[str, Any],
    carrier_id: str,
    *,
    step_m: float | None = None,
) -> dict[str, Any]:
    """Prime carrier lunar_physics + material_physics from catalog bind."""
    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    profile_id = str(state.get("profile_id") or "lunar_crater_5km")
    if step_m is None:
        seg_len = abs(float(carrier.get("segment_end_m", 0)) - float(carrier.get("segment_start_m", 0)))
        from production_gate.robot_os_kernel_v1 import SEGMENT_TICKS

        step_m = seg_len / SEGMENT_TICKS if seg_len else 1.0
    site_zone = resolve_site_zone_from_state(state, carrier_id)
    lunar, material = evaluate_lunar_row_with_material(
        float(step_m),
        profile_id=profile_id,
        state=state,
        site_zone=site_zone,
    )
    carrier["lunar_physics"] = lunar
    if material:
        carrier["material_physics"] = material
        carrier["material_variant"] = material.get("variant_id")
    carrier["site_zone"] = lunar.get("zone") or resolve_site_zone_from_state(state, carrier_id)
    state.setdefault("carriers", {})[carrier_id] = carrier
    return carrier


def resolve_tick_ingress(
    state: dict[str, Any],
    carrier_id: str,
) -> dict[str, Any]:
    """Ingress mult + radiation + provenance for wear iron / CXX paths."""
    from production_gate.cmr_wear_chip_coupling_v1 import _traverse_fraction
    from production_gate.robot_os_radiation_bind_v1 import (
        DEFAULT_MISSION_YEARS,
        DEFAULT_SHIELD_G_CM2,
        DEFAULT_SITE_CLASS,
        wear_at_traverse_fraction,
    )

    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    fraction = _traverse_fraction(state, carrier)
    profile_id = str(state.get("profile_id") or "lunar_crater_5km")
    site_zone = resolve_site_zone_from_state(state, carrier_id)

    mp = dict(carrier.get("material_physics") or {})
    lunar = dict(carrier.get("lunar_physics") or {})
    ingress_source = "unknown"
    mp_zone = str(mp.get("zone") or lunar.get("zone") or "")

    if mp.get("ingress_disturbance_mult") is not None and mp_zone == site_zone:
        ingress_mult = float(mp["ingress_disturbance_mult"])
        ingress_source = "material_physics_bus"
    elif lunar.get("ingress_disturbance_mult") is not None and str(lunar.get("zone") or "") == site_zone:
        ingress_mult = float(lunar["ingress_disturbance_mult"])
        ingress_source = str(lunar.get("ingress_source") or "lunar_physics_hal")
    else:
        seg_len = abs(float(carrier.get("segment_end_m", 0.0)) - float(carrier.get("segment_start_m", 0.0)))
        from production_gate.robot_os_kernel_v1 import SEGMENT_TICKS

        step_m = seg_len / SEGMENT_TICKS if seg_len else 1.0
        lunar, material = evaluate_lunar_row_with_material(
            step_m,
            profile_id=profile_id,
            state=state,
            site_zone=site_zone,
        )
        carrier["lunar_physics"] = lunar
        carrier["site_zone"] = site_zone
        if material:
            carrier["material_physics"] = material
        state.setdefault("carriers", {})[carrier_id] = carrier
        ingress_mult = float(lunar["ingress_disturbance_mult"])
        ingress_source = str(lunar.get("ingress_source") or "material_physics_bus")
        mp = dict(material or carrier.get("material_physics") or {})

    rad = wear_at_traverse_fraction(
        fraction,
        mission_years=DEFAULT_MISSION_YEARS,
        shield_g_cm2=DEFAULT_SHIELD_G_CM2,
        site_class=DEFAULT_SITE_CLASS,
    )
    delta_mv = float(rad.get("radiation_delta_vth_mv") or 0.0)

    return {
        "ingress_mult": ingress_mult,
        "radiation_delta_vth_mv": delta_mv,
        "traverse_fraction": fraction,
        "site_zone": site_zone,
        "lunar": lunar,
        "material_physics": mp or carrier.get("material_physics"),
        "ingress_source": ingress_source,
        "variant_id": resolve_variant_id_from_state(state),
    }


def run_material_tick_ingress_smoke() -> dict[str, Any]:
    from production_gate.fleet_live_state_v1 import empty_state

    state = empty_state(profile_id="lunar_crater_5km")
    state["material_physics_bind"] = {"variant_id": "scout_default_medium"}
    state["carriers"]["scout_B"] = {
        "carrier_id": "scout_B",
        "segment_start_m": 0.0,
        "segment_end_m": 600.0,
        "cursor_m": 100.0,
        "ticks": 1,
    }
    attach_material_physics_to_carrier(state, "scout_B", step_m=416.67)
    row = resolve_tick_ingress(state, "scout_B")
    checks = {
        "F_ingress_ge_1": float(row["ingress_mult"]) >= 1.0,
        "F_source_material_bus": row["ingress_source"] == "material_physics_bus",
        "F_material_row_present": bool(row.get("material_physics")),
        "F_seal_b3_on_row": (row.get("material_physics") or {}).get("seal_class") == "B3",
        "F_site_zone_present": bool(row.get("site_zone")),
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "MATERIAL_TICK_INGRESS_PASS" if not fail else "MATERIAL_TICK_INGRESS_FAIL",
        "checks": checks,
        "fail": fail,
        "sample": row,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_material_tick_ingress_smoke(), indent=2))
