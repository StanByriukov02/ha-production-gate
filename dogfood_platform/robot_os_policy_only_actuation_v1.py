"""Policy-only actuation v1 — stub policy without governance (honest VLA sim).

Applies proposals blindly; records zone violations for dual-run falsifier.
TABU: label policy_only as MEASURED VLA · claim governance active.
"""
from __future__ import annotations

from typing import Any

from dogfood_platform.robot_os_governance_types_v1 import init_governance_state
from dogfood_platform.robot_os_hal_v1 import ActuationCommand, RobotOsHalStack
from dogfood_platform.robot_os_mission_envelope_v1 import (
    cursor_in_forbidden_zone,
    load_mission_envelope,
    traverse_crosses_forbidden_zone,
)
from dogfood_platform.robot_os_policy_stub_v1 import DEFAULT_INJECT_BAD_AT, propose

PROOF_TIER = "POLICY_ONLY_SLICE"


def policy_only_enabled(state: dict[str, Any]) -> bool:
    return bool((state.get("policy_only") or {}).get("enabled"))


def init_policy_only_bind(
    state: dict[str, Any],
    *,
    enabled: bool = True,
    inject_bad_at: int = DEFAULT_INJECT_BAD_AT,
    inject_enabled: bool = True,
) -> dict[str, Any]:
    state["policy_only"] = {
        "enabled": enabled,
        "proof_tier": PROOF_TIER,
        "inject_bad_at": int(inject_bad_at),
        "inject_enabled": bool(inject_enabled),
        "tabu": "claim VLA MEASURED",
    }
    init_governance_state(state, enabled=False)
    state["governance"]["enabled"] = False
    return state


def _inject_params(state: dict[str, Any]) -> tuple[int, bool]:
    row = state.get("policy_only") or {}
    raw = row.get("inject_bad_at")
    inject_bad_at = int(DEFAULT_INJECT_BAD_AT if raw is None else raw)
    return inject_bad_at, bool(row.get("inject_enabled", True))


def _policy_only_zone_violation(
    *,
    proposal_command: str,
    cursor_m: float,
    carrier: dict[str, Any],
    envelope: dict[str, Any],
) -> tuple[bool, str | None]:
    if proposal_command != "traverse":
        return False, None
    intent_m = float(
        carrier.get("policy_inject_target_cursor_m")
        or carrier.get("policy_intent_cursor_m")
        or cursor_m
    )
    in_zone, zone_id = cursor_in_forbidden_zone(intent_m, envelope)
    crossed, cross_zone = traverse_crosses_forbidden_zone(cursor_m, intent_m, envelope)
    if in_zone or crossed:
        return True, str(zone_id or cross_zone or "forbidden")
    return False, None


def apply_policy_only_before_actuation(
    state: dict[str, Any],
    carrier_id: str,
    hal: RobotOsHalStack,
) -> dict[str, Any]:
    """Blind policy path — no interceptor; violation flagged for world oracle."""
    carrier = state["carriers"][carrier_id]
    profile_id = str(state.get("profile_id", "lunar_crater_5km"))
    inject_bad_at, inject_enabled = _inject_params(state)
    cursor_m = float(carrier.get("cursor_m", 0.0))

    proposal = propose(state, carrier_id, inject_bad_at=inject_bad_at, inject_enabled=inject_enabled)
    from dogfood_platform.cmr_wear_policy_coupling_v1 import apply_wear_to_policy_proposal

    proposal = apply_wear_to_policy_proposal(state, carrier_id, proposal)
    carrier["last_policy_proposal"] = proposal.to_dict()
    accepted = hal.actuation.accept_command(ActuationCommand(command=proposal.command))

    envelope = load_mission_envelope(profile_id=profile_id)
    violation, zone_id = _policy_only_zone_violation(
        proposal_command=proposal.command,
        cursor_m=cursor_m,
        carrier=carrier,
        envelope=envelope,
    )
    if violation:
        carrier["policy_zone_violation"] = str(zone_id or "forbidden")
        state.setdefault("policy_only", {})["zone_violation"] = True

    return {
        "policy_only": True,
        "proposal": proposal.to_dict(),
        "actuation_accepted": accepted,
        "zone_violation": violation,
        "cursor_m": cursor_m,
    }
