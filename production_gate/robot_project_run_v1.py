"""Robot project run v1 — unified condition probe on a durable project.

Loads project body (or demo-world-only when policy present), runs dual-condition
Newton-X policy probes, optionally evaluates policy trace via evidence_engine.

TABU: claim product_ready · claim MEASURED field · claim VLA.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from production_gate.robot_os_newton_x_policy_dual_run_v1 import (
    DEFAULT_CARRIER_ID,
    DEFAULT_PROFILE_ID,
    bad_sinkage_lunar_physics,
    probe_one_tick_actuation_at_sinkage,
    probe_policy_proposals_at_sinkage,
    safe_lunar_physics,
)
from production_gate.terramech_bekker_on_v1 import hostile_bekker_physics, safe_bekker_physics
from production_gate.robot_os_policy_port_v1 import BACKEND_REGOLITH_PLANNER, BACKEND_STUB
from production_gate.robot_project_desk_v1 import (
    get_project,
    project_dir,
    update_project_last_run,
)

ConditionId = Literal["safe", "hostile"]

_REPO = Path(__file__).resolve().parents[1]
_EE = Path.home() / "evidence_engine"

PROOF_TIER = "ROBOT_PROJECT_RUN_SLICE"

# Default Dual soils = ON-grounded Bekker (Wong/Bekker corpus). Lunar inject remains available.
_CONDITIONS: dict[str, dict[str, Any]] = {
    "safe": {
        "label": "Safe firm soil (Bekker ON)",
        "physics": safe_bekker_physics,
    },
    "hostile": {
        "label": "Hostile soft soil sinkage (Bekker ON)",
        "physics": hostile_bekker_physics,
    },
}

# Keep aliases for callers that still import lunar injectors from this module path
_ = (bad_sinkage_lunar_physics, safe_lunar_physics)

_PRESET_PROBE: dict[str, tuple[str, str]] = {
    "open_rrbot": ("lunar_crater_5km", "scout_B"),
    "open_diffbot": ("lunar_crater_5km", "scout_B"),
    "lunar_scout": ("lunar_crater_5km", "scout_B"),
    "earth_bench": ("lunar_crater_5km", "scout_B"),
}


def _is_manipulator_project(project: dict[str, Any]) -> bool:
    body = project.get("body") or {}
    ee = str(body.get("ee_link") or "").lower()
    blob = " ".join(
        [
            str(body.get("label") or ""),
            str(body.get("source_path") or ""),
            str(body.get("stored_file") or ""),
            ee,
        ]
    ).lower()
    if any(tok in blob for tok in ("rrbot", "arm4", "arm_", "manipulator", "planar")):
        return True
    if ee in ("tool_link", "ee_link"):
        return True
    return False


def _manipulator_grasp_kpi_for_condition(
    project: dict[str, Any],
    *,
    condition: ConditionId,
) -> dict[str, Any] | None:
    """Rust grasp_force_step KPI for manipulator Dual runs — sim_slice, not floor life."""
    if not _is_manipulator_project(project):
        return None
    from production_gate.manipulator_grasp_force_port_v1 import grasp_force_step_native

    if condition == "hostile":
        commanded, allowed = 30.0, 18.0
    else:
        commanded, allowed = 20.0, 25.0
    step = grasp_force_step_native(
        commanded_force_n=commanded,
        allowed_max_force_n=allowed,
        current_applied_force_n=0.0,
        build=False,
    )
    ok = str(step.get("verdict") or "").endswith("PASS")
    if condition == "hostile" and not step.get("force_limited"):
        ok = False
    return {
        "schema": "manipulator_grasp_kpi_v1",
        "proof_tier": "GRASP_FORCE_SLICE",
        "ok": ok,
        "condition": condition,
        "verdict": step.get("verdict"),
        "commanded_force_n": commanded,
        "allowed_max_force_n": allowed,
        "applied_force_n": step.get("applied_force_n"),
        "force_limited": step.get("force_limited"),
        "backend_id": step.get("backend_id"),
        "oracle": "manipulator_kinematics_step grasp_force_step",
        "honesty": {
            "not_measured": True,
            "sim_slice": True,
            "not_product_ready": True,
            "hostile_derate_teaching": condition == "hostile",
        },
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    from production_gate.atomic_json_v1 import atomic_write_json

    atomic_write_json(path, doc)


def _condition_dual(
    *,
    condition_id: str,
    label: str,
    physics: dict[str, Any],
    profile_id: str,
    carrier_id: str,
    silicon_fuse_path: str | None = None,
) -> dict[str, Any]:
    """Same dual probe shape as start_here_v1._condition_block."""
    proposals = probe_policy_proposals_at_sinkage(
        profile_id=profile_id,
        carrier_id=carrier_id,
        lunar_physics=physics,
    )
    stub_tick = probe_one_tick_actuation_at_sinkage(
        policy_backend=BACKEND_STUB,
        profile_id=profile_id,
        carrier_id=carrier_id,
        lunar_physics=physics,
        silicon_fuse_path=silicon_fuse_path,
    )
    regolith_tick = probe_one_tick_actuation_at_sinkage(
        policy_backend=BACKEND_REGOLITH_PLANNER,
        profile_id=profile_id,
        carrier_id=carrier_id,
        lunar_physics=physics,
        silicon_fuse_path=silicon_fuse_path,
    )
    stub_p = proposals["stub_proposal"]
    reg_p = proposals["regolith_proposal"]
    stub_delta = float(stub_tick["cursor_after"]) - float(stub_tick["cursor_before"])
    reg_delta = float(regolith_tick["cursor_after"]) - float(regolith_tick["cursor_before"])
    return {
        "condition_id": condition_id,
        "label": label,
        "physics": physics,
        "stub": {
            "proposal": stub_p,
            "tick": stub_tick,
            "cursor_delta_m": round(stub_delta, 4),
            "advanced": stub_delta > 1e-6,
        },
        "regolith": {
            "proposal": reg_p,
            "tick": regolith_tick,
            "cursor_delta_m": round(reg_delta, 4),
            "advanced": reg_delta > 1e-6,
            "hold": bool(regolith_tick.get("governance_hold")),
        },
        "story": {
            "same_command": stub_p.get("command") == reg_p.get("command"),
            "diverged": stub_p.get("command") != reg_p.get("command"),
        },
    }


def _resolve_probe_targets(project: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    body = project.get("body")
    policy = project.get("policy")
    policy_port = project.get("policy_port")
    honesty: dict[str, Any] = {"not_measured": True, "sim_slice": True}

    if body:
        preset_id = str(body.get("preset_id") or "")
        profile_id, carrier_id = _PRESET_PROBE.get(preset_id, (DEFAULT_PROFILE_ID, DEFAULT_CARRIER_ID))
        honesty["body_bound"] = True
        honesty["preset_id"] = preset_id
        honesty["world_id"] = body.get("world_id")
        if policy_port:
            honesty["policy_port_bound"] = True
        return profile_id, carrier_id, honesty

    if policy or policy_port:
        honesty["demo_world_only"] = True
        honesty["no_body_bound"] = True
        if policy:
            honesty["policy_bound"] = True
        if policy_port:
            honesty["policy_port_bound"] = True
            honesty["note"] = (
                "Run uses default lunar_crater_5km / scout_B probe world — "
                "PolicyPort proposals are recorded dumps, not live VLA."
            )
        else:
            honesty["note"] = (
                "Run uses default lunar_crater_5km / scout_B probe world — "
                "no body manifest bound; policy trace may still drive EE eval."
            )
        return DEFAULT_PROFILE_ID, DEFAULT_CARRIER_ID, honesty

    raise ValueError(
        "project requires body, policy, or policy_port before run; "
        "attach_body_from_preset / attach_policy_trace / attach_policy_port first"
    )


def _load_foreign_proposal(project_id: str, *, condition: str) -> dict[str, Any] | None:
    """Pick a recorded PolicyPort proposal for this condition (not live VLA)."""
    path = project_dir(project_id) / "policy_port" / "proposals.jsonl"
    if not path.is_file():
        return None
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        rows.append(json.loads(s))
    if not rows:
        return None
    # Hostile prefers recover/hold if present; safe prefers traverse/idle.
    if condition == "hostile":
        for r in rows:
            if r.get("command") in ("recover", "hold"):
                return r
    else:
        for r in rows:
            if r.get("command") in ("traverse", "idle"):
                return r
    return rows[0]


def _dual_summary(dual_block: dict[str, Any], *, foreign: dict[str, Any] | None = None) -> dict[str, Any]:
    stub_p = dual_block["stub"]["proposal"]
    reg_p = dual_block["regolith"]["proposal"]
    story = dict(dual_block["story"])
    out: dict[str, Any] = {
        "condition_id": dual_block["condition_id"],
        "label": dual_block["label"],
        "stub_command": stub_p.get("command"),
        "regolith_command": reg_p.get("command"),
        "diverged": story["diverged"],
        "same_command": story["same_command"],
        "stub": dual_block["stub"],
        "regolith": dual_block["regolith"],
        "story": story,
    }
    if foreign:
        out["foreign_command"] = foreign.get("command")
        out["foreign"] = {
            "proposal": foreign,
            "honesty": {"recorded_dump": True, "not_live_vla": True},
        }
        out["foreign_vs_regolith"] = foreign.get("command") != reg_p.get("command")
        out["foreign_vs_stub"] = foreign.get("command") != stub_p.get("command")
        story["foreign_diverged_from_planner"] = out["foreign_vs_regolith"]
        out["story"] = story
    return out


def _eval_policy_trace(project_id: str) -> dict[str, Any] | None:
    """Optional evidence_engine eval — never raises if EE is absent."""
    trace_path = project_dir(project_id) / "policy" / "trace.jsonl"
    if not trace_path.is_file():
        return None
    if not (_EE / "src").is_dir():
        return {
            "eval_ok": False,
            "skipped": True,
            "reason": "evidence_engine not installed",
            "trace_rel": "policy/trace.jsonl",
        }

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_EE / "src")
    receipt_json = project_dir(project_id) / "policy" / "receipt.json"
    try:
        from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

        r1 = subprocess.run(
            [
                sys.executable,
                "-m",
                "evidence_engine.cli",
                "eval",
                "--trace",
                str(trace_path),
                "--policy-source",
                "robot_project_run_v1",
                "--out",
                str(receipt_json),
            ],
            cwd=str(_EE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            **hidden_run_kwargs(),
        )
        if r1.returncode not in (0, 1) or not receipt_json.is_file():
            return {
                "eval_ok": False,
                "returncode": r1.returncode,
                "stderr": (r1.stderr or "")[-500:],
                "trace_rel": "policy/trace.jsonl",
            }
        receipt = json.loads(receipt_json.read_text(encoding="utf-8"))
        counters = receipt.get("counters") or {}
        return {
            "eval_ok": True,
            "steps": counters.get("steps"),
            "vetoes": counters.get("vetoes"),
            "per_rule": counters.get("per_rule"),
            "chain_final_hash": (receipt.get("chain_final_hash") or "")[:24],
            "trace_rel": "policy/trace.jsonl",
            "receipt_rel": "policy/receipt.json",
        }
    except OSError as exc:
        return {
            "eval_ok": False,
            "error": str(exc),
            "trace_rel": "policy/trace.jsonl",
        }


def run_project(project_id: str, condition: ConditionId) -> dict[str, Any]:
    """Run one world condition probe on project; persist receipt under runs/."""
    if condition not in ("safe", "hostile"):
        raise ValueError(f"unknown condition={condition!r}; choose from ['hostile', 'safe']")

    project = get_project(project_id)
    profile_id, carrier_id, bind_honesty = _resolve_probe_targets(project)

    # Measurable field lane: session/project field_bind → Dual soils + g (not lat/lon)
    from production_gate.field_world_bind_v1 import physics_pair_for_field
    from production_gate.start_here_session_v1 import load_session

    body = project.get("body") if isinstance(project.get("body"), dict) else {}
    session = load_session()
    robot = session.get("robot") if isinstance(session.get("robot"), dict) else {}
    # Body-bound field wins over ambient desk session — live earth session must not
    # poison lunar_scout / BYO probes (batch flaky + desk pollution).
    body_field = body.get("field_bind") if isinstance(body.get("field_bind"), dict) else None
    body_has_lane = bool(body_field or body.get("world_id") or body.get("globe"))
    if body_has_lane:
        field_bind = body_field
        globe = body.get("globe") or (body_field or {}).get("globe")
        world_id = body.get("world_id") or (body_field or {}).get("world_id")
    else:
        field_bind = (
            robot.get("field_bind") if isinstance(robot.get("field_bind"), dict) else None
        )
        globe = (field_bind or {}).get("globe") or robot.get("globe")
        world_id = (field_bind or {}).get("world_id") or robot.get("world_id")
    pair = physics_pair_for_field(
        globe=globe, world_id=world_id, field_bind=field_bind, body=body
    )
    lane = pair["lane"]
    side = pair[condition]
    physics = dict(side["physics"])
    # Dual peer Bekker pack for energy dual_share (no orphan work/1000).
    safe_ph = (pair.get("safe") or {}).get("physics") or {}
    hostile_ph = (pair.get("hostile") or {}).get("physics") or {}
    physics["bekker_dual"] = {
        "rc_safe_n": float(safe_ph.get("compaction_resistance_n") or 0.0),
        "rc_hostile_n": float(hostile_ph.get("compaction_resistance_n") or 0.0),
        "sink_safe_mm": float(safe_ph.get("sinkage_mm") or 0.0),
        "sink_hostile_mm": float(hostile_ph.get("sinkage_mm") or 0.0),
        "drawbar_safe_n": float(safe_ph.get("drawbar_pull_n") or 0.0),
        "drawbar_hostile_n": float(hostile_ph.get("drawbar_pull_n") or 0.0),
        "safe_soil_id": lane.get("safe_soil_id"),
        "hostile_soil_id": lane.get("hostile_soil_id"),
    }
    from production_gate.drive_chain_embed_v1 import attach_drive_chain_to_physics

    physics = attach_drive_chain_to_physics(physics, condition=condition)
    from production_gate.env_budget_embed_v1 import attach_env_budget_to_physics

    physics = attach_env_budget_to_physics(physics, condition=condition)
    from production_gate.storm_env_embed_v1 import (
        attach_storm_env_to_physics,
        fold_storm_env_into_closed_loop,
    )

    physics = attach_storm_env_to_physics(physics, condition=condition)
    from production_gate.slope_rut_embed_v1 import attach_slope_rut_to_physics

    physics = attach_slope_rut_to_physics(physics, condition=condition)
    from production_gate.traverse_mechanical_embed_v1 import (
        attach_traverse_mechanical_to_physics,
        fold_traverse_mechanical_into_closed_loop,
    )

    # g from field lane — jerk severity uses same Dual g as Bekker.
    if lane.get("g_mps2") is not None:
        physics["g_mps2"] = float(lane["g_mps2"])
    physics = attach_traverse_mechanical_to_physics(physics, condition=condition)
    from production_gate.fatigue_optics_embed_v1 import (
        attach_fatigue_optics_to_physics,
        fold_fatigue_optics_into_closed_loop,
    )

    physics = attach_fatigue_optics_to_physics(physics, condition=condition)
    from production_gate.dust_envelope_embed_v1 import attach_dust_envelope_to_physics

    physics = attach_dust_envelope_to_physics(physics, condition=condition)
    from production_gate.materials_thermal_embed_v1 import (
        attach_materials_thermal_to_physics,
        fold_materials_thermal_into_closed_loop,
    )

    physics = attach_materials_thermal_to_physics(physics, condition=condition)
    from production_gate.orbit_residual_embed_v1 import attach_orbit_residual_to_physics

    physics = attach_orbit_residual_to_physics(physics, condition=condition)
    from production_gate.ballistics_kepler_embed_v1 import (
        attach_ballistics_kepler_to_physics,
        fold_ballistics_kepler_into_closed_loop,
    )

    contact = pair.get("contact") if isinstance(pair.get("contact"), dict) else {}
    load = pair.get("load") if isinstance(pair.get("load"), dict) else {}
    body_mass = contact.get("mass_kg")
    physics = attach_ballistics_kepler_to_physics(
        physics,
        condition=condition,
        mass_kg=float(body_mass) if body_mass is not None else None,
    )
    from production_gate.thermal_world_embed_v1 import (
        attach_thermal_world_to_physics,
        fold_thermal_world_into_closed_loop,
    )

    physics = attach_thermal_world_to_physics(physics, condition=condition)
    from production_gate.isru_sinter_embed_v1 import (
        attach_isru_sinter_to_physics,
        fold_isru_sinter_into_closed_loop,
    )

    physics = attach_isru_sinter_to_physics(physics, condition=condition)
    from production_gate.atm_drag_embed_v1 import (
        attach_atm_drag_to_physics,
        fold_atm_drag_into_closed_loop,
    )

    physics = attach_atm_drag_to_physics(physics, condition=condition)
    from production_gate.acoustic_embed_v1 import (
        attach_acoustic_to_physics,
        fold_acoustic_into_closed_loop,
    )

    physics = attach_acoustic_to_physics(physics, condition=condition)
    from production_gate.li_qc_embed_v1 import (
        attach_li_qc_to_physics,
        fold_li_qc_into_closed_loop,
    )

    physics = attach_li_qc_to_physics(physics, condition=condition)
    from production_gate.albedo_dose_embed_v1 import (
        attach_albedo_dose_to_physics,
        fold_albedo_dose_into_closed_loop,
    )

    physics = attach_albedo_dose_to_physics(physics, condition=condition)
    from production_gate.dust_ingress_embed_v1 import (
        attach_dust_ingress_to_physics,
        fold_dust_ingress_into_closed_loop,
    )

    physics = attach_dust_ingress_to_physics(physics, condition=condition)
    from production_gate.janosi_embed_v1 import (
        attach_janosi_to_physics,
        fold_janosi_into_closed_loop,
    )

    physics = attach_janosi_to_physics(physics, condition=condition)
    from production_gate.radiation_rate_embed_v1 import (
        attach_radiation_rate_to_physics,
        fold_radiation_rate_into_closed_loop,
    )

    physics = attach_radiation_rate_to_physics(physics, condition=condition)
    from production_gate.envelope_refuse_v1 import attach_envelope_refuse_to_physics

    physics = attach_envelope_refuse_to_physics(physics, condition=condition)
    from production_gate.regolith_thermal_embed_v1 import (
        attach_regolith_thermal_to_physics,
        fold_regolith_thermal_into_closed_loop,
    )

    physics = attach_regolith_thermal_to_physics(physics, condition=condition)
    label = str(side["label"])
    bind_honesty = {
        **bind_honesty,
        "field_globe": lane.get("globe"),
        "field_world_id": lane.get("world_id"),
        "field_safe_soil": lane.get("safe_soil_id"),
        "field_hostile_soil": lane.get("hostile_soil_id"),
        "field_g_mps2": lane.get("g_mps2"),
        "field_soil_id": side.get("soil_id"),
        "lat_lon_is_pose_only": True,
        "body_contact_source": contact.get("source"),
        "body_mass_kg": contact.get("mass_kg"),
        "body_ground_pressure_kpa": load.get("ground_pressure_kpa"),
        "body_contact_width_m": load.get("contact_width_b_m"),
        "body_geometry_teaching_not_measured": True,
    }

    from production_gate.silicon_fuse_v1 import ensure_silicon_fuse, fuse_path_for_project

    ensure_silicon_fuse(project_id)
    fuse_path = str(fuse_path_for_project(project_id))
    dual_block = _condition_dual(
        condition_id=condition,
        label=label,
        physics=physics,
        profile_id=profile_id,
        carrier_id=carrier_id,
        silicon_fuse_path=fuse_path,
    )
    foreign = _load_foreign_proposal(project_id, condition=condition)
    dual = _dual_summary(dual_block, foreign=foreign)
    from production_gate.artifact_existence_law_v1 import build_actuation_truth
    from production_gate.energy_claim_v1 import build_energy_claim_from_actuation
    from production_gate.physics_gate_v1 import (
        build_physics_gate_for_run,
        sync_silicon_fuse_after_gate,
    )

    actuation_truth = build_actuation_truth(dual_block, dual)
    energy_claim = build_energy_claim_from_actuation(
        actuation_truth,
        claim_id=f"{project_id}:{condition}",
        physics=physics,
    )
    physics_gate = build_physics_gate_for_run(
        project_id,
        condition=condition,
        dual_block=dual_block,
        actuation_truth=actuation_truth,
        energy_claim=energy_claim,
    )
    silicon_fuse = sync_silicon_fuse_after_gate(project_id, physics_gate)
    ee = _eval_policy_trace(project_id)
    from production_gate.desk_closed_loop_v1 import build_closed_loop_v1

    closed_loop_v1 = build_closed_loop_v1(
        condition=condition,
        dual=dual,
        actuation_truth=actuation_truth,
        foreign=foreign,
    )
    closed_loop_v1 = fold_fatigue_optics_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_materials_thermal_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_ballistics_kepler_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_thermal_world_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_isru_sinter_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_atm_drag_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_acoustic_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_li_qc_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_albedo_dose_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_dust_ingress_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_janosi_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_radiation_rate_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_regolith_thermal_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_storm_env_into_closed_loop(closed_loop_v1, physics)
    closed_loop_v1 = fold_traverse_mechanical_into_closed_loop(closed_loop_v1, physics)
    from production_gate.foundation_closed_loop_fold_v1 import fold_foundation_into_closed_loop

    closed_loop_v1 = fold_foundation_into_closed_loop(
        closed_loop_v1,
        physics=physics,
        energy_claim=energy_claim,
    )

    grasp_kpi = _manipulator_grasp_kpi_for_condition(project, condition=condition)

    run_id = f"run-{uuid.uuid4().hex[:12]}"
    ts = _now()
    run_doc: dict[str, Any] = {
        "run_id": run_id,
        "project_id": project_id,
        "condition": condition,
        "timestamp_utc": ts,
        "profile_id": profile_id,
        "carrier_id": carrier_id,
        "dual": dual,
        "dual_block": dual_block,
        "actuation_truth": actuation_truth,
        "energy_claim": energy_claim,
        "physics_gate": physics_gate,
        "silicon_fuse": silicon_fuse,
        "closed_loop_v1": closed_loop_v1,
        "ee": ee,
        "proof_tier": PROOF_TIER,
        "honesty": {
            "not_vla": True,
            "not_measured": True,
            "verdict_source": "dual_run_probes_only",
            "policy_port_recorded_only": foreign is not None,
            **bind_honesty,
        },
        "tabu": "claim VLA MEASURED · claim product_ready · claim Isaac truth",
    }
    if grasp_kpi is not None:
        run_doc["manipulator_grasp_kpi_v1"] = grasp_kpi
        # also surface in closed_loop kpi without claiming floor life
        kpi = dict((closed_loop_v1.get("kpi") or {}))
        kpi["grasp_force_limited"] = bool(grasp_kpi.get("force_limited"))
        kpi["grasp_applied_force_n"] = grasp_kpi.get("applied_force_n")
        kpi["grasp_rust_verdict"] = grasp_kpi.get("verdict")
        closed_loop_v1 = dict(closed_loop_v1)
        closed_loop_v1["kpi"] = kpi
        run_doc["closed_loop_v1"] = closed_loop_v1

    # Physics OS kernel — sealed inside HA Dual runtime (not Cursor).
    from production_gate.physics_os_kernel_v1 import seal_kernel_on_run

    run_doc = seal_kernel_on_run(run_doc)

    run_path = project_dir(project_id) / "runs" / f"{run_id}.json"
    _write_json(run_path, run_doc)
    update_project_last_run(project_id, run_doc)

    # Persist World bed scene for returning desk opens (local visitor vault)
    try:
        from production_gate.desk_visitor_v1 import remember_scene
        from production_gate.start_here_session_v1 import load_session, write_session

        scene = {
            "clean": False,
            "globe": lane.get("globe"),
            "world_id": lane.get("world_id"),
            "condition": condition,
            "sinkage_mm": physics.get("sinkage_mm"),
            "sinkage_risk": physics.get("sinkage_risk"),
            "traverse_feasible": physics.get("traverse_feasible"),
            "stub_command": dual.get("stub_command"),
            "planner_command": dual.get("regolith_command"),
            "diverged": dual.get("diverged"),
            "g_mps2": lane.get("g_mps2"),
            "note": "last Run probe on this machine",
        }
        sess = load_session()
        sess = dict(sess)
        sess["scene"] = scene
        write_session(sess)
        remember_scene(scene, active_project_id=project_id)
    except Exception:
        pass

    # Return sealed run (OS kernel lives in HA physics receipt, not Cursor).
    return {
        "run_id": run_id,
        "condition": condition,
        "dual": dual,
        "dual_block": dual_block,
        "actuation_truth": actuation_truth,
        "energy_claim": energy_claim,
        "physics_gate": run_doc["physics_gate"],
        "silicon_fuse": silicon_fuse,
        "closed_loop_v1": run_doc["closed_loop_v1"],
        "physics_os_kernel": run_doc["physics_os_kernel"],
        "ee": ee,
        "project_id": project_id,
        "foreign": foreign,
        "manipulator_grasp_kpi_v1": grasp_kpi,
        "honesty": run_doc["honesty"],
        "field": {
            "globe": lane.get("globe"),
            "world_id": lane.get("world_id"),
            "soil_id": side.get("soil_id"),
            "g_mps2": lane.get("g_mps2"),
            "sinkage_mm": physics.get("sinkage_mm"),
            "safe_soil": lane.get("safe_soil_id"),
            "hostile_soil": lane.get("hostile_soil_id"),
            "ground_pressure_kpa": load.get("ground_pressure_kpa"),
            "contact_width_b_m": load.get("contact_width_b_m"),
            "body_mass_kg": contact.get("mass_kg"),
            "body_contact_source": contact.get("source"),
        },
    }
