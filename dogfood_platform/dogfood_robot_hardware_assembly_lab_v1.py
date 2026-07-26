"""Dogfood robot hardware assembly lab v1 — Earth · Moon · Orbit engineer workflow.

One recipe = compile/assemble + world-realistic test bind.
TABU: Venus · claim product_ready · claim field MEASURED without bench ingress.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_LAB = _REPO / "fixtures" / "robot" / "dogfood_robot_hardware_assembly_lab_v1.json"
_CANON = "docs/agent_workflow/DOGFOOD_ROBOT_HARDWARE_ASSEMBLY_LAB_V1.md"

PROOF_TIER = "DOGFOOD_ROBOT_HARDWARE_ASSEMBLY_LAB_SLICE"
ORACLE = "EARTH_MOON_ORBIT_ASSEMBLE_TEST"


def load_assembly_lab_spec() -> dict[str, Any]:
    return json.loads(_LAB.read_text(encoding="utf-8"))


def _load_json(rel: str) -> dict[str, Any]:
    p = _REPO / rel.replace("\\", "/")
    return json.loads(p.read_text(encoding="utf-8"))


def run_earth_bench_carrier_recipe(*, write_manifest: bool = False) -> dict[str, Any]:
    from dogfood_platform.appendage_robot_create_cli_v1 import run_robot_create_smoke
    from dogfood_platform.rolling_kinematics_crown_v1 import run_rolling_kinematics_crown_smoke
    from dogfood_platform.wheeled_chassis_compose_v1 import run_wheeled_chassis_smoke

    lab = load_assembly_lab_spec()
    recipe = dict((lab.get("recipes") or {})["earth_bench_carrier"])
    create = run_robot_create_smoke()
    rolling = run_rolling_kinematics_crown_smoke()
    wheeled = run_wheeled_chassis_smoke(build=False)
    fixture = _load_json(str(recipe.get("earth_fixture") or ""))
    from dogfood_platform.physics_measured_bench_ingress_v1 import ingest_earth_lab_bench_for_recipe

    bench = ingest_earth_lab_bench_for_recipe()

    checks = {
        "F_create_cli_pass": create.get("verdict") == "APPENDAGE_ROBOT_CREATE_CLI_SLICE_PASS",
        "F_rolling_crown_pass": rolling.get("verdict") == "ROLLING_KINEMATICS_CROWN_SLICE_PASS",
        "F_wheeled_pass": wheeled.get("verdict") == "WHEELED_CHASSIS_COMPOSE_SLICE_PASS",
        "F_earth_fixture_procedure": len(fixture.get("procedure") or []) >= 3,
        "F_earth_fixture_falsifiers": len(fixture.get("falsifiers") or []) >= 2,
        "F_world_earth_lab": recipe.get("world_id") == "earth_lab_1g",
        "F_earth_bench_bus_power_t4": bench["tier_map"].get("bus_power_active_run_w") == "T4",
        "F_earth_bench_foc_t4": bench["tier_map"].get("foc_energy_uj_per_step") == "T4",
        "F_earth_bench_sinkage_t4": bench["tier_map"].get("earth_traverse_sinkage_mm") == "T4",
        "F_bench_not_mutate_teaching": bench.get("teaching_mutated") is False,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "recipe_id": "earth_bench_carrier",
        "verdict": "EARTH_BENCH_CARRIER_RECIPE_PASS" if not fail else "EARTH_BENCH_CARRIER_RECIPE_FAIL",
        "world_id": "earth_lab_1g",
        "checks": checks,
        "fail": fail,
        "create": create.get("verdict"),
        "manifest_path": (create.get("manifest") or {}).get("written_to"),
        "fixture_id": fixture.get("fixture_id"),
        "bench_ingress": {
            "t4_slots": bench.get("t4_slots"),
            "tier_map": bench.get("tier_map"),
            "comparisons": bench.get("compare", {}).get("comparisons"),
        },
        "operator_steps": recipe.get("operator_steps"),
    }


def run_lunar_scout_field_recipe() -> dict[str, Any]:
    from dogfood_platform.fleet_live_state_v1 import empty_state
    from dogfood_platform.full_body_compose_v1 import run_full_body_compose_smoke
    from dogfood_platform.hexapod_foot_contact_v1 import run_hexapod_foot_contact_smoke
    from dogfood_platform.kinematic_chain_ir_v1 import clear_chain_overlay
    from dogfood_platform.robot_os_newton_x_world_step_v1 import init_newton_x_world, step_newton_x_world, validate_newton_x_falsifiers

    lab = load_assembly_lab_spec()
    recipe = dict((lab.get("recipes") or {})["lunar_scout_field"])
    clear_chain_overlay()
    full_body = run_full_body_compose_smoke()
    foot = run_hexapod_foot_contact_smoke()

    state = empty_state(profile_id="lunar_crater_5km", carrier_ids=("scout_A",))
    init_newton_x_world(state, enabled=True)
    state["carriers"]["scout_A"].update(
        {
            "phase": "traverse",
            "command": "traverse",
            "cursor_m": 1200.0,
            "segment_start_m": 0.0,
            "segment_end_m": 2500.0,
        }
    )
    step_row = step_newton_x_world(state, "scout_A", 50.0)
    fals = validate_newton_x_falsifiers(state, carrier_id="scout_A")

    checks = {
        "F_full_body_pass": full_body.get("verdict") == "FULL_BODY_COMPOSE_SLICE_PASS",
        "F_foot_contact_pass": foot.get("verdict") == "HEXAPOD_FOOT_CONTACT_SLICE_PASS",
        "F_newton_x_falsifiers": bool(fals.get("pass")),
        "F_terramech_on_step": "terramech" in step_row,
        "F_heightfield_on_step": "terrain" in step_row,
        "F_world_lunar": recipe.get("world_id") == "lunar_regolith_surface",
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "recipe_id": "lunar_scout_field",
        "verdict": "LUNAR_SCOUT_FIELD_RECIPE_PASS" if not fail else "LUNAR_SCOUT_FIELD_RECIPE_FAIL",
        "world_id": "lunar_regolith_surface",
        "checks": checks,
        "fail": fail,
        "full_body": full_body.get("verdict"),
        "foot_contact": foot.get("verdict"),
        "newton_x_step_m": step_row.get("step_m"),
        "sinkage_mm": (step_row.get("terramech") or {}).get("sinkage_mm"),
        "operator_steps": recipe.get("operator_steps"),
    }


def run_orbit_thermal_bus_recipe() -> dict[str, Any]:
    from dogfood_platform.physics_universe_environment_register_v1 import get_world

    lab = load_assembly_lab_spec()
    recipe = dict((lab.get("recipes") or {})["orbit_thermal_bus"])
    orbit = get_world("vacuum_orbit_microg")
    leo = get_world("leo_debris_orbit")

    g_orbit = orbit.get("g_mps2")
    checks = {
        "F_orbit_register_out_loco": "foot_contact" in (orbit.get("out_of_scope") or []),
        "F_orbit_micro_g": g_orbit is not None and float(g_orbit) < 0.01,
        "F_thermal_vacuum_open": "thermal_vacuum" in (orbit.get("open") or []),
        "F_leo_debris_open": "debris_flux" in (leo.get("open") or []),
        "F_leo_loco_out": str(leo.get("register_state")) == "OUT",
        "F_no_locomotion_claim": orbit.get("locomotion_north_star") is None,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "recipe_id": "orbit_thermal_bus",
        "verdict": "ORBIT_THERMAL_BUS_RECIPE_PASS" if not fail else "ORBIT_THERMAL_BUS_RECIPE_FAIL",
        "world_id": "vacuum_orbit_microg",
        "checks": checks,
        "fail": fail,
        "debris_flux_proxy": leo.get("debris_flux_proxy"),
        "operator_steps": recipe.get("operator_steps"),
        "honesty": "orbit = bus/thermal/debris register · not walking robot",
    }


def run_assembly_recipe(recipe_id: str) -> dict[str, Any]:
    runners = {
        "earth_bench_carrier": run_earth_bench_carrier_recipe,
        "lunar_scout_field": run_lunar_scout_field_recipe,
        "orbit_thermal_bus": run_orbit_thermal_bus_recipe,
    }
    if recipe_id not in runners:
        raise KeyError(f"unknown assembly recipe: {recipe_id}")
    return runners[recipe_id]()


def run_dogfood_robot_hardware_assembly_lab_smoke(*, recipe_id: str | None = None) -> dict[str, Any]:
    lab = load_assembly_lab_spec()
    recipe_ids = [recipe_id] if recipe_id else list(lab.get("smoke_recipes") or [])
    rows = {rid: run_assembly_recipe(rid) for rid in recipe_ids}
    fail_recipes = [rid for rid, row in rows.items() if not str(row.get("verdict", "")).endswith("_PASS")]

    checks = {
        "F_all_mission_worlds_in_lab": set(lab.get("mission_worlds") or []) == {
            "earth_lab_1g",
            "lunar_regolith_surface",
            "vacuum_orbit_microg",
        },
        "F_earth_recipe_pass": rows.get("earth_bench_carrier", {}).get("verdict") == "EARTH_BENCH_CARRIER_RECIPE_PASS",
        "F_lunar_recipe_pass": rows.get("lunar_scout_field", {}).get("verdict") == "LUNAR_SCOUT_FIELD_RECIPE_PASS",
        "F_orbit_recipe_pass": rows.get("orbit_thermal_bus", {}).get("verdict") == "ORBIT_THERMAL_BUS_RECIPE_PASS",
        "F_venus_parked_honesty": bool((lab.get("honesty") or {}).get("venus_parked")),
        "F_not_product_ready": bool((lab.get("honesty") or {}).get("not_product_ready")),
    }
    if recipe_id:
        checks = {f"F_recipe_{recipe_id}": rows[recipe_id].get("verdict", "").endswith("_PASS")}

    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "DOGFOOD_ROBOT_HARDWARE_ASSEMBLY_LAB_SLICE_PASS" if not fail else "DOGFOOD_ROBOT_HARDWARE_ASSEMBLY_LAB_SLICE_FAIL",
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
        "checks": checks,
        "fail": fail,
        "recipes": rows,
        "fail_recipes": fail_recipes,
        "canon": _CANON,
        "entry_command": lab.get("entry_command"),
    }


if __name__ == "__main__":
    import sys

    rid = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(run_dogfood_robot_hardware_assembly_lab_smoke(recipe_id=rid), indent=2))
