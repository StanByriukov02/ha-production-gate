"""Appendage role taxonomy v1 — body part ↔ geometry ↔ motion bus bind.

Phase AJ: closes APPENDAGE_ROLE_TAXONOMY (D0 from full-robot ladder).
TABU: claim taxonomy = full humanoid · claim all motion buses built.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_TAXONOMY = _REPO / "fixtures" / "robot" / "appendage_role_taxonomy_v0.json"
_REGISTRY = _REPO / "fixtures" / "robot" / "kinematic_chain_ir_v0.json"

PROOF_TIER = "APPENDAGE_ROLE_TAXONOMY_SLICE"
ORACLE = "BODY_PART_MOTION_CLASS_BIND"


def load_role_taxonomy() -> dict[str, Any]:
    return json.loads(_TAXONOMY.read_text(encoding="utf-8"))


def load_registry_chains() -> dict[str, Any]:
    return dict(json.loads(_REGISTRY.read_text(encoding="utf-8")).get("chains") or {})


def validate_role_entry(role_id: str, entry: dict[str, Any]) -> list[str]:
    fail: list[str] = []
    if not entry.get("body_region"):
        fail.append(f"{role_id}:missing_body_region")
    gclasses = entry.get("geometry_classes") or []
    if not gclasses:
        fail.append(f"{role_id}:no_geometry_classes")
    if not entry.get("motion_bus"):
        fail.append(f"{role_id}:no_motion_bus")
    dof = entry.get("typical_dof") or []
    if not dof:
        fail.append(f"{role_id}:no_typical_dof")
    return fail


def validate_registry_role_coverage(
    taxonomy: dict[str, Any],
    chains: dict[str, Any],
) -> dict[str, Any]:
    coverage = dict(taxonomy.get("registry_coverage") or {})
    roles = dict(taxonomy.get("roles") or {})
    checks: dict[str, bool] = {}
    for chain_id, expected_role in coverage.items():
        chain = chains.get(chain_id) or {}
        actual_role = str(chain.get("appendage_role") or "")
        checks[f"F_{chain_id}_role"] = actual_role == expected_role
        role_def = roles.get(expected_role) or {}
        gclass = str(chain.get("geometry_class") or "")
        checks[f"F_{chain_id}_geometry"] = gclass in list(role_def.get("geometry_classes") or [])
    return {"checks": checks, "fail": [k for k, v in checks.items() if not v]}


def validate_motion_bus_honesty(taxonomy: dict[str, Any]) -> dict[str, Any]:
    buses = dict(taxonomy.get("motion_buses") or {})
    checks: dict[str, bool] = {}
    for bus_id, bus in buses.items():
        status = str(bus.get("status") or "")
        module = bus.get("module")
        if status == "PASS":
            checks[f"F_bus_{bus_id}_module"] = bool(module)
        elif status == "DEFERRED":
            checks[f"F_bus_{bus_id}_deferred_named"] = bool(bus.get("target_phase")) or status == "PARK"
            checks[f"F_bus_{bus_id}_no_false_pass"] = module is None
    return {"checks": checks, "fail": [k for k, v in checks.items() if not v]}


def validate_charter_fixture_honesty(taxonomy: dict[str, Any]) -> dict[str, bool]:
    charter_path = _REPO / "fixtures" / "robot" / "appendage_body_phase_charter_v0.json"
    if not charter_path.is_file():
        return {"F_charter_fixture": False}
    charter = json.loads(charter_path.read_text(encoding="utf-8"))
    phases = dict(charter.get("phases") or {})
    required = ["AK", "AL", "AM", "AN", "AO", "AP", "AQ"]
    return {
        "F_charter_fixture": True,
        "F_charter_seven_phases": all(p in phases for p in required),
        "F_charter_ak_gate_only": phases.get("AK", {}).get("operator_priority") == "GATE_ONLY",
        "F_charter_has_falsifiers": all(bool(phases[p].get("falsifiers")) for p in required),
    }


def run_appendage_role_taxonomy_smoke() -> dict[str, Any]:
    taxonomy = load_role_taxonomy()
    chains = load_registry_chains()
    roles = dict(taxonomy.get("roles") or {})

    role_fail: list[str] = []
    for role_id, entry in roles.items():
        role_fail.extend(validate_role_entry(role_id, entry))

    reg = validate_registry_role_coverage(taxonomy, chains)
    bus = validate_motion_bus_honesty(taxonomy)
    charter_checks = validate_charter_fixture_honesty(taxonomy)

    checks = {
        "F_taxonomy_id": bool(taxonomy.get("taxonomy_id")),
        "F_seven_roles": len(roles) >= 7,
        "F_role_schema": not role_fail,
        "F_registry_coverage": not reg["fail"],
        "F_motion_bus_honesty": not bus["fail"],
        "F_manipulator_arm": "manipulator_arm" in roles,
        "F_locomotion_leg": "locomotion_leg" in roles,
        "F_wheel_axle_gate": str(
            (taxonomy.get("motion_buses") or {}).get("wheeled_chassis_compose", {}).get("operator_priority")
        )
        in ("GATE_ACTIVE", "GATE_ONLY"),
        "F_head_neck_bus": str(
            (taxonomy.get("motion_buses") or {}).get("pan_tilt_bus", {}).get("status")
        )
        == "PASS",
        **charter_checks,
    }
    fail = [k for k, v in checks.items() if not v] + role_fail
    return {
        "verdict": "APPENDAGE_ROLE_TAXONOMY_SLICE_PASS" if not fail else "APPENDAGE_ROLE_TAXONOMY_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "registry_coverage": reg["checks"],
        "motion_bus_checks": bus["checks"],
        "role_count": len(roles),
    }


def resolve_motion_bus_for_role(role: str) -> dict[str, Any]:
    taxonomy = load_role_taxonomy()
    role_def = dict((taxonomy.get("roles") or {}).get(role) or {})
    bus_id = str(role_def.get("motion_bus") or "")
    bus = dict((taxonomy.get("motion_buses") or {}).get(bus_id) or {})
    return {
        "role": role,
        "motion_bus": bus_id,
        "bus_status": bus.get("status"),
        "module": bus.get("module"),
        "operator_priority": role_def.get("operator_priority"),
        "deferred": list(role_def.get("deferred") or []),
        "proof_tier": role_def.get("proof_tier"),
    }


if __name__ == "__main__":
    print(json.dumps(run_appendage_role_taxonomy_smoke(), indent=2))
