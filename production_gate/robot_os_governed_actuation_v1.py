"""Governed actuation v1 — policy → interceptor → HAL accept (or veto hold).

Veto BEFORE cursor advance · governance_hold ≠ recover.
TABU: veto after actuation · claim VLA MEASURED.
"""
from __future__ import annotations

from typing import Any

from production_gate.robot_os_governance_eer_session_v1 import init_eer_session, record_eer_step
from production_gate.robot_os_governance_interceptor_v1 import evaluate_for_profile, record_action_receipt
from production_gate.robot_os_governance_types_v1 import ActionReceipt, init_governance_state
from production_gate.robot_os_hal_v1 import ActuationCommand, ActuationState, RobotOsHalStack
from production_gate.robot_os_policy_port_v1 import (
    BACKEND_STUB,
    init_policy_port_bind,
    resolve_policy_port,
)
from production_gate.robot_os_policy_stub_v1 import DEFAULT_INJECT_BAD_AT

GOVERNANCE_SKIP_KEY = "governance_skip_movement"
GOVERNANCE_HOLD_KEY = "governance_hold"


def governance_enabled(state: dict[str, Any]) -> bool:
    return bool((state.get("governance") or {}).get("enabled"))


def init_governance_bind(
    state: dict[str, Any],
    *,
    enabled: bool = True,
    inject_bad_at: int = DEFAULT_INJECT_BAD_AT,
    inject_enabled: bool = True,
    policy_backend: str = BACKEND_STUB,
    vla_mock_trace: list[dict[str, Any]] | None = None,
    smolvla_trace_path: str | None = None,
    smolvla_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    init_governance_state(state, enabled=enabled)
    gov = state["governance"]
    gov["inject_bad_at"] = int(inject_bad_at)
    gov["inject_enabled"] = bool(inject_enabled)
    gov["envelope_profile_id"] = str(state.get("profile_id", "lunar_crater_5km"))
    init_policy_port_bind(
        state,
        backend=policy_backend,
        vla_mock_trace=vla_mock_trace,
        smolvla_trace_path=smolvla_trace_path,
        smolvla_trace=smolvla_trace,
    )
    init_eer_session(state, profile_id=str(state.get("profile_id", "lunar_crater_5km")))
    return state

def _record_veto_actuation(hal: RobotOsHalStack, *, proposed_command: str) -> bool:
    sink = hal.actuation
    sink._last = ActuationState(command=proposed_command, accepted=False)  # type: ignore[attr-defined]
    return False


def apply_governance_before_actuation(
    state: dict[str, Any],
    carrier_id: str,
    hal: RobotOsHalStack,
) -> dict[str, Any]:
    """Evaluate policy proposal; veto blocks traverse actuation for this tick."""
    from production_gate.robot_os_governance_types_v1 import GovernanceVerdict

    carrier = state["carriers"][carrier_id]
    profile_id = str((state.get("governance") or {}).get("envelope_profile_id") or state.get("profile_id", "lunar_crater_5km"))

    if not governance_enabled(state):
        cmd = str(carrier.get("command") or "idle")
        accepted = hal.actuation.accept_command(ActuationCommand(command=cmd))
        return {"governance_active": False, "allowed": True, "actuation_accepted": accepted}

    # H6-iron: C eFUSE CURRENT_GATE — blown fuse blocks current (no actuation)
    fuse = (state.get("governance") or {}).get("silicon_fuse")
    if isinstance(fuse, dict) and fuse.get("blown"):
        port = resolve_policy_port(state)
        proposal = port.propose(state, carrier_id)
        carrier["last_policy_proposal"] = proposal.to_dict()
        verdict = GovernanceVerdict(
            allowed=False,
            gate_thresholds={"silicon_fuse": "APOPTOSIS_FUSE"},
            veto_reason="SE_APOPTOSIS_FUSE_BLOWN",
            rule_id="H6_SILICON_FUSE_CURRENT_GATE",
        )
        receipt = ActionReceipt(
            action_id=proposal.action_id,
            carrier_id=carrier_id,
            proposal=proposal,
            verdict=verdict,
            cursor_m=float(carrier.get("cursor_m", 0.0)),
        )
        record_action_receipt(state, receipt)
        carrier[GOVERNANCE_HOLD_KEY] = True
        carrier[GOVERNANCE_SKIP_KEY] = True
        carrier["governance_last_veto"] = verdict.veto_reason
        carrier["governance_veto"] = verdict.to_dict()
        accepted = _record_veto_actuation(hal, proposed_command=proposal.command)
        return {
            "governance_active": True,
            "allowed": False,
            "actuation_accepted": accepted,
            "action_id": proposal.action_id,
            "policy_backend": proposal.source,
            "proposal": proposal.to_dict(),
            "verdict": verdict.to_dict(),
            "silicon_fuse_block": True,
        }

    port = resolve_policy_port(state)
    proposal = port.propose(state, carrier_id)
    from production_gate.cmr_wear_policy_coupling_v1 import apply_wear_to_policy_proposal

    proposal = apply_wear_to_policy_proposal(state, carrier_id, proposal)
    carrier["last_policy_proposal"] = proposal.to_dict()
    cursor_m = float(carrier.get("cursor_m", 0.0))
    verdict = evaluate_for_profile(
        proposal,
        cursor_m=cursor_m,
        profile_id=profile_id,
        carrier=carrier,
        physics=carrier.get("lunar_physics"),
    )
    receipt = ActionReceipt(
        action_id=proposal.action_id,
        carrier_id=carrier_id,
        proposal=proposal,
        verdict=verdict,
        cursor_m=cursor_m,
    )
    record_action_receipt(state, receipt)
    record_eer_step(
        state,
        proposal=proposal,
        cursor_m=cursor_m,
        carrier=carrier,
        physics=carrier.get("lunar_physics"),
    )

    if verdict.allowed:
        carrier.pop(GOVERNANCE_HOLD_KEY, None)
        carrier.pop("governance_last_veto", None)
        accepted = hal.actuation.accept_command(ActuationCommand(command=proposal.command))
        return {
            "governance_active": True,
            "allowed": True,
            "actuation_accepted": accepted,
            "action_id": proposal.action_id,
            "policy_backend": proposal.source,
            "proposal": proposal.to_dict(),
            "verdict": verdict.to_dict(),
        }

    carrier[GOVERNANCE_HOLD_KEY] = True
    carrier[GOVERNANCE_SKIP_KEY] = True
    carrier["governance_last_veto"] = verdict.veto_reason
    carrier["governance_veto"] = verdict.to_dict()
    accepted = _record_veto_actuation(hal, proposed_command=proposal.command)
    return {
        "governance_active": True,
        "allowed": False,
        "actuation_accepted": accepted,
        "action_id": proposal.action_id,
        "policy_backend": proposal.source,
        "proposal": proposal.to_dict(),
        "verdict": verdict.to_dict(),
    }


def make_governed_on_tick_before(
    state: dict[str, Any],
    hal: RobotOsHalStack,
) -> Any:
    """Return on_tick_before callback wiring governance → actuation."""

    def on_tick_before(cid: str, carrier: dict[str, Any]) -> None:
        apply_governance_before_actuation(state, cid, hal)

    return on_tick_before
