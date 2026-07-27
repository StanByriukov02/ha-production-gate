"""Newton-X policy dual-run v1 — blind stub vs RegolithPlanner on sinkage inject.

Compares policy proposals and one-tick actuation at injected bad terramech row.
proof_tier: REGOLITH_POLICY_DUAL_RUN_SLICE — not VLA · not Newton-X platform.
TABU: claim learned policy · claim Isaac ground truth.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from production_gate.robot_os_governance_types_v1 import PolicyProposal
from production_gate.robot_os_hal_lunar_profile_v1 import G_MOON_MPS2, ORACLE as REGOLITH_ORACLE
from production_gate.robot_os_newton_x_world_step_v1 import WORLD_ID, init_newton_x_world
from production_gate.robot_os_policy_port_v1 import (
    BACKEND_REGOLITH_PLANNER,
    BACKEND_STUB,
    PolicyStubBackend,
    RegolithPlannerBackend,
)

PROOF_TIER = "REGOLITH_POLICY_DUAL_RUN_SLICE"
DEFAULT_PROFILE_ID = "lunar_crater_5km"
DEFAULT_CARRIER_ID = "scout_B"


def bad_sinkage_lunar_physics() -> dict[str, Any]:
    """Hostile Dual row from Rust Bekker (lunar_soft_proxy) — not magic 22.5 mm theater."""
    from production_gate.terramech_bekker_on_v1 import physics_row_for_dual

    row = physics_row_for_dual("lunar_soft_proxy", g_mps2=G_MOON_MPS2)
    # Preserve REGOLITH_ORACLE consumers that key on lunar profile, but never launder as Bekker.
    row = dict(row)
    row["regolith_profile_oracle"] = REGOLITH_ORACLE
    row["honesty"] = {
        **dict(row.get("honesty") or {}),
        "bekker_from_rust": True,
        "magic_sinkage_mm_retired": True,
        "former_hardcoded_sinkage_mm": 22.5,
    }
    return row


def _proposal_row(proposal: PolicyProposal) -> dict[str, Any]:
    return {
        "action_id": proposal.action_id,
        "command": proposal.command,
        "confidence": round(float(proposal.confidence), 4),
        "source": proposal.source,
    }


def safe_lunar_physics() -> dict[str, Any]:
    """Safe Dual row from Rust Bekker (lunar_firm_proxy) — not magic 4.2 mm theater."""
    from production_gate.terramech_bekker_on_v1 import physics_row_for_dual

    row = physics_row_for_dual("lunar_firm_proxy", g_mps2=G_MOON_MPS2)
    row = dict(row)
    row["regolith_profile_oracle"] = REGOLITH_ORACLE
    row["honesty"] = {
        **dict(row.get("honesty") or {}),
        "bekker_from_rust": True,
        "magic_sinkage_mm_retired": True,
        "former_hardcoded_sinkage_mm": 4.2,
    }
    return row


def _prepare_sinkage_probe_state(
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    carrier_id: str = DEFAULT_CARRIER_ID,
    lunar_physics: dict[str, Any] | None = None,
    silicon_fuse_path: str | None = None,
) -> dict[str, Any]:
    from production_gate.cmr_wear_chip_coupling_v1 import init_wear_chip_bus
    from production_gate.fleet_live_state_v1 import empty_state
    from production_gate.fleet_relay_plan_v1 import segment_bounds, terminal_carrier
    from production_gate.robot_os_clifford_bind_v1 import apply_clifford_bind

    terminal_id = terminal_carrier(profile_id)
    carrier_id = carrier_id or terminal_id
    bounds = segment_bounds(profile_id)
    seg_idx = 1 if carrier_id == "scout_B" else 0
    start_m, end_m = bounds[seg_idx]
    physics = dict(lunar_physics or bad_sinkage_lunar_physics())

    state = apply_clifford_bind(empty_state(profile_id=profile_id), profile_id=profile_id)
    init_wear_chip_bus(state, iron_mmio=False)
    init_newton_x_world(state, enabled=True)
    state["carriers"][carrier_id].update(
        {
            "phase": "traverse",
            "command": "traverse",
            "segment_start_m": start_m,
            "segment_end_m": end_m,
            "cursor_m": start_m + (end_m - start_m) * 0.55,
            "ticks": 3,
            "lunar_physics": physics,
        }
    )
    if silicon_fuse_path:
        from production_gate.silicon_fuse_v1 import load_fuse_into_governance_state

        load_fuse_into_governance_state(state, silicon_fuse_path)
    return state


def probe_policy_proposals_at_sinkage(
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    carrier_id: str = DEFAULT_CARRIER_ID,
    lunar_physics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Proposal-only dual probe — separate state copies preserve action_id seq."""
    physics = dict(lunar_physics or bad_sinkage_lunar_physics())
    base = _prepare_sinkage_probe_state(
        profile_id=profile_id,
        carrier_id=carrier_id,
        lunar_physics=physics,
    )

    state_stub = deepcopy(base)
    stub = PolicyStubBackend(inject_enabled=False)
    stub_prop = stub.propose(state_stub, carrier_id)

    state_regolith = deepcopy(base)
    regolith = RegolithPlannerBackend()
    regolith_prop = regolith.propose(state_regolith, carrier_id)

    return {
        "profile_id": profile_id,
        "carrier_id": carrier_id,
        "world_id": WORLD_ID,
        "physics_inject": physics,
        "stub_proposal": _proposal_row(stub_prop),
        "regolith_proposal": _proposal_row(regolith_prop),
    }


def probe_one_tick_actuation_at_sinkage(
    *,
    policy_backend: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    carrier_id: str = DEFAULT_CARRIER_ID,
    lunar_physics: dict[str, Any] | None = None,
    silicon_fuse_path: str | None = None,
) -> dict[str, Any]:
    """One governed kernel tick with Newton-X HAL at sinkage inject."""
    from production_gate.robot_carrier_sim_runtime_v1 import _tick_via_kernel
    from production_gate.robot_os_governed_actuation_v1 import init_governance_bind

    state = _prepare_sinkage_probe_state(
        profile_id=profile_id,
        carrier_id=carrier_id,
        lunar_physics=lunar_physics,
        silicon_fuse_path=silicon_fuse_path,
    )
    init_governance_bind(
        state,
        enabled=True,
        inject_enabled=False,
        policy_backend=policy_backend,
    )
    # init_governance_bind recreates governance — re-bind C fuse MMIO after
    if silicon_fuse_path:
        from production_gate.silicon_fuse_v1 import load_fuse_into_governance_state

        load_fuse_into_governance_state(state, silicon_fuse_path)
    carrier_before = dict(state["carriers"][carrier_id])
    cursor_before = float(carrier_before.get("cursor_m") or 0.0)
    ticks_before = int(carrier_before.get("ticks") or 0)

    state = _tick_via_kernel(carrier_id, state)
    carrier = state["carriers"][carrier_id]
    gov = state.get("governance") or {}
    last_receipt = gov.get("last_receipt") or {}
    verdict = last_receipt.get("verdict") or {}

    return {
        "policy_backend": policy_backend,
        "cursor_before": cursor_before,
        "cursor_after": float(carrier.get("cursor_m") or 0.0),
        "ticks_before": ticks_before,
        "ticks_after": int(carrier.get("ticks") or 0),
        "phase_after": carrier.get("phase"),
        "last_policy_proposal": carrier.get("last_policy_proposal"),
        "governance_hold": bool(carrier.get("governance_hold")),
        "governance_allowed": verdict.get("allowed"),
        "silicon_fuse_block": verdict.get("rule_id") == "H6_SILICON_FUSE_CURRENT_GATE",
        "newton_x_obs": bool(carrier.get("newton_x_obs")),
    }


def validate_newton_x_policy_dual_falsifiers(
    *,
    proposal_probe: dict[str, Any],
    stub_tick: dict[str, Any],
    regolith_tick: dict[str, Any],
) -> dict[str, Any]:
    stub_p = proposal_probe.get("stub_proposal") or {}
    regolith_p = proposal_probe.get("regolith_proposal") or {}

    checks: dict[str, bool] = {
        "F_physics_inject_infeasible": (proposal_probe.get("physics_inject") or {}).get("traverse_feasible")
        is False,
        "F_stub_blind_traverse": stub_p.get("command") == "traverse",
        "F_stub_high_confidence": float(stub_p.get("confidence") or 0.0) >= 0.85,
        "F_stub_source": stub_p.get("source") == BACKEND_STUB,
        "F_regolith_recover_command": regolith_p.get("command") == "recover",
        "F_regolith_low_confidence": float(regolith_p.get("confidence") or 1.0) < 0.5,
        "F_regolith_source": regolith_p.get("source") == BACKEND_REGOLITH_PLANNER,
        "F_delta_confidence": float(regolith_p.get("confidence") or 1.0)
        < float(stub_p.get("confidence") or 0.0),
        "F_stub_tick_advances": float(stub_tick.get("cursor_after") or 0.0)
        > float(stub_tick.get("cursor_before") or 0.0),
        "F_regolith_tick_holds": float(regolith_tick.get("cursor_after") or 0.0)
        == float(regolith_tick.get("cursor_before") or 0.0),
        "F_regolith_governance_hold": regolith_tick.get("governance_hold") is True,
        "F_regolith_reads_injected_physics": (regolith_tick.get("last_policy_proposal") or {}).get("command")
        == "recover",
        "F_stub_newton_x_obs": stub_tick.get("newton_x_obs") is True,
    }
    fail = [k for k, v in checks.items() if not v]
    return {"checks": checks, "fail": fail, "pass": len(fail) == 0}


def run_newton_x_policy_dual_harness(
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    carrier_id: str = DEFAULT_CARRIER_ID,
) -> dict[str, Any]:
    proposal_probe = probe_policy_proposals_at_sinkage(profile_id=profile_id, carrier_id=carrier_id)
    stub_tick = probe_one_tick_actuation_at_sinkage(
        policy_backend=BACKEND_STUB,
        profile_id=profile_id,
        carrier_id=carrier_id,
    )
    regolith_tick = probe_one_tick_actuation_at_sinkage(
        policy_backend=BACKEND_REGOLITH_PLANNER,
        profile_id=profile_id,
        carrier_id=carrier_id,
    )
    fals = validate_newton_x_policy_dual_falsifiers(
        proposal_probe=proposal_probe,
        stub_tick=stub_tick,
        regolith_tick=regolith_tick,
    )
    return {
        "harness_id": "robot_os_newton_x_policy_dual_run_v1",
        "profile_id": profile_id,
        "carrier_id": carrier_id,
        "proof_tier": PROOF_TIER,
        "world_id": WORLD_ID,
        "proposal_probe": proposal_probe,
        "stub_tick": stub_tick,
        "regolith_tick": regolith_tick,
        "falsifiers": fals,
        "verdict": "PASS" if fals["pass"] else "FAIL",
        "honesty": {
            "not_vla": True,
            "not_measured": True,
            "not_newton_x_platform": True,
            "verdict_source": "dual_run_falsifiers_only",
            "physics_oracle": REGOLITH_ORACLE,
        },
        "tabu": "claim VLA MEASURED · claim Newton-X platform built · claim Isaac truth",
    }
