"""Hexapod foot contact v1 — μ catalog bind · per-foot Coulomb · gait-integrated.

Phase AI: closes AI_HEXAPOD_CONTACT (ADAPT teaching).
TABU: claim MEASURED locomotion contact · claim field slip truth.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CONTACT_SPEC = _REPO / "fixtures" / "robot" / "hexapod_foot_contact_v1.json"

PROOF_TIER = "HEXAPOD_FOOT_CONTACT_SLICE"
ORACLE = "FOOT_CONTACT_FRICTION_BIND"


def load_foot_contact_spec() -> dict[str, Any]:
    return json.loads(_CONTACT_SPEC.read_text(encoding="utf-8"))


def _leg_index(appendage_id: str) -> int:
    return int(appendage_id.rsplit("_", 1)[-1])


def is_stance_leg(leg_idx: int, gait_bus: dict[str, Any]) -> bool:
    params = dict(gait_bus.get("params") or {})
    groups = list(params.get("stance_groups") or [[0, 2, 4], [1, 3, 5]])
    half = int(float(gait_bus.get("phase") or 0) * 2.0) % 2
    stance_set = set(groups[half] if groups else [0, 2, 4])
    return leg_idx in stance_set


def evaluate_hexapod_foot_contact(
    *,
    foot_world: dict[str, Any],
    leg_id: str,
    gait_bus: dict[str, Any],
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from production_gate.contact_friction_model_v1 import evaluate_coulomb_contact

    spec = spec or load_foot_contact_spec()
    leg_idx = _leg_index(leg_id)
    stance = is_stance_leg(leg_idx, gait_bus)
    z = float(foot_world.get("z") or 99.0)
    ground = float(spec.get("ground_plane_z_m") or 0.0)
    z_thresh = float(spec.get("contact_z_threshold_m") or 0.14)
    in_contact = stance and z <= ground + z_thresh

    if not in_contact:
        return {
            "leg_id": leg_id,
            "in_contact": False,
            "stance": stance,
            "ee_z": z,
            "slip_predicted": False,
            "proof_tier": PROOF_TIER,
        }

    n_force = float(spec.get("stance_normal_force_n") or 12.0)
    if stance:
        f_t = float(spec.get("stance_tangential_safe_n") or 1.5)
    else:
        f_t = float(spec.get("swing_tangential_force_n") or 9.0)

    friction = evaluate_coulomb_contact(
        normal_force_n=n_force,
        tangential_force_n=f_t,
        pad_material_id=str(spec.get("pad_material_id") or "nbr_70a"),
        surface_id=str(spec.get("surface_id") or "lunar_regolith_compact"),
    )
    return {
        "leg_id": leg_id,
        "in_contact": True,
        "stance": stance,
        "ee_z": z,
        "friction": friction,
        "slip_predicted": bool(friction.get("slip_predicted")),
        "pair_id": friction.get("pair_id"),
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
    }


def hexapod_gait_contact_tick(
    robot: dict[str, Any],
    *,
    dt: float = 0.005,
) -> dict[str, Any]:
    from production_gate.hexapod_gait_bus_v1 import hexapod_gait_tick

    spec = load_foot_contact_spec()
    bus = hexapod_gait_tick(robot, dt=dt)
    gait_bus = robot.get("gait_bus") or {}
    contacts: list[dict[str, Any]] = []
    for foot in bus.get("feet") or []:
        leg_id = str(foot.get("leg") or "leg_0")
        row = evaluate_hexapod_foot_contact(
            foot_world=foot,
            leg_id=leg_id,
            gait_bus=gait_bus,
            spec=spec,
        )
        contacts.append(row)

    bus["foot_contacts"] = contacts
    bus["contact_summary"] = {
        "feet_in_contact": sum(1 for c in contacts if c.get("in_contact")),
        "slip_predicted_count": sum(1 for c in contacts if c.get("slip_predicted")),
        "pair_id": spec.get("pad_material_id"),
    }
    return bus


def run_hexapod_foot_contact_smoke(*, ticks: int = 20) -> dict[str, Any]:
    from production_gate.hexapod_body_compose_v1 import init_hexapod_body
    from production_gate.hexapod_gait_bus_v1 import init_gait_bus

    spec = load_foot_contact_spec()
    robot = init_hexapod_body()
    init_gait_bus(robot, gait_name="tripod")
    all_contacts: list[dict[str, Any]] = []
    for _ in range(ticks):
        bus = hexapod_gait_contact_tick(robot, dt=0.005)
        all_contacts.extend(list(bus.get("foot_contacts") or []))

    in_contact = [c for c in all_contacts if c.get("in_contact")]
    safe = evaluate_hexapod_foot_contact(
        foot_world={"x": 0.1, "y": 0.0, "z": 0.05},
        leg_id="leg_0",
        gait_bus={"phase": 0.0, "params": {"stance_groups": [[0, 2, 4], [1, 3, 5]]}},
        spec={**spec, "stance_tangential_safe_n": 1.0},
    )
    slip = evaluate_hexapod_foot_contact(
        foot_world={"x": 0.1, "y": 0.0, "z": 0.05},
        leg_id="leg_0",
        gait_bus={"phase": 0.0, "params": {"stance_groups": [[0, 2, 4], [1, 3, 5]]}},
        spec={**spec, "stance_tangential_safe_n": 20.0},
    )

    from production_gate.contact_friction_model_v1 import load_friction_catalog, resolve_friction_pair

    catalog = load_friction_catalog()
    pair = resolve_friction_pair(
        pad_material_id=str(spec.get("pad_material_id") or "nbr_70a"),
        surface_id=str(spec.get("surface_id") or "lunar_regolith_compact"),
        catalog=catalog,
    )
    adapt_ok = str(pair.get("confidence") or "") == "ADAPT" and str(catalog.get("proof_tier") or "").endswith("SLICE")

    checks = {
        "F_catalog_pair": str(safe.get("pair_id") or "").startswith("nbr_70a__"),
        "F_some_contact": len(in_contact) > 0,
        "F_safe_no_slip": not bool(safe.get("slip_predicted")),
        "F_high_t_slip": bool(slip.get("slip_predicted")),
        "F_slip_diverge": bool(safe.get("slip_predicted")) != bool(slip.get("slip_predicted")),
        "F_adapt_tier": adapt_ok,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "HEXAPOD_FOOT_CONTACT_SLICE_PASS" if not fail else "HEXAPOD_FOOT_CONTACT_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "contacts_sample": in_contact[:3],
    }
