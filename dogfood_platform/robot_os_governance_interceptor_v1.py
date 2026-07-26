"""Governance interceptor v3 — world-grounded veto before actuation.

Rules: R2 forbidden zone · R4 physics envelope · R3 command allowlist ·
R1 legacy confidence (deprecated — policy_stub / vla_mock / regolith_planner only).

Pure rule evaluation: robot_os_governance_rules_v1 (aligned with evidence_engine E1–E4).
proof_tier: GOVERNANCE_SLICE — pure function, no HAL side effects.
TABU: veto after actuation · rely on VLA self-confidence for action-only backends.
"""
from __future__ import annotations

from typing import Any

from dogfood_platform.robot_os_governance_rules_v1 import (
    RULE_FAMILY_COMMAND,
    RULE_FAMILY_CONFIDENCE,
    RULE_FAMILY_PHYSICS,
    RULE_FAMILY_ZONE,
    evaluate_governance_rules,
)
from dogfood_platform.robot_os_governance_types_v1 import (
    ActionReceipt,
    GovernanceVerdict,
    PolicyProposal,
)
from dogfood_platform.robot_os_mission_envelope_v1 import load_mission_envelope

INTERCEPTOR_VERSION = 3

RULE_LEGACY_CONFIDENCE = "R1_confidence_below_gate"
RULE_FORBIDDEN_ZONE = "R2_workspace_envelope_violated"
RULE_COMMAND = "R3_command_not_in_envelope"
RULE_PHYSICS = "R4_physics_traverse_blocked"

LEGACY_CONFIDENCE_SOURCES = frozenset(
    {
        "policy_stub_v1",
        "vla_mock_v1",
        "regolith_planner_v1",
    }
)

ACTION_ONLY_SOURCES = frozenset(
    {
        "smolvla_trace_v1",
    }
)

DEFAULT_FRAGILE_RIM_CURSOR_M = 2550.0

_RULE_FAMILY_TO_ID = {
    RULE_FAMILY_COMMAND: RULE_COMMAND,
    RULE_FAMILY_ZONE: RULE_FORBIDDEN_ZONE,
    RULE_FAMILY_PHYSICS: RULE_PHYSICS,
    RULE_FAMILY_CONFIDENCE: RULE_LEGACY_CONFIDENCE,
}


def _intent_cursor_m(cursor_m: float, carrier: dict[str, Any] | None) -> float:
    if not carrier:
        return cursor_m
    raw = carrier.get("policy_inject_target_cursor_m")
    if raw is not None:
        return float(raw)
    raw = carrier.get("policy_intent_cursor_m")
    if raw is not None:
        return float(raw)
    return cursor_m


def evaluate_proposal(
    proposal: PolicyProposal,
    *,
    cursor_m: float,
    envelope: dict[str, Any],
    profile_id: str = "lunar_crater_5km",
    carrier: dict[str, Any] | None = None,
    physics: dict[str, Any] | None = None,
) -> GovernanceVerdict:
    intent_m = _intent_cursor_m(cursor_m, carrier)
    phys = dict(physics or (carrier or {}).get("lunar_physics") or {})

    allowed, veto_reason, rule_family, thresholds = evaluate_governance_rules(
        command=proposal.command,
        confidence=proposal.confidence,
        source=proposal.source,
        cursor_m=cursor_m,
        intent_m=intent_m,
        envelope=envelope,
        physics=phys or None,
        legacy_confidence_sources=LEGACY_CONFIDENCE_SOURCES,
        action_only_sources=ACTION_ONLY_SOURCES,
    )
    thresholds = {
        **thresholds,
        "profile_id": profile_id,
        "interceptor_version": INTERCEPTOR_VERSION,
    }
    rule_id = _RULE_FAMILY_TO_ID.get(rule_family) if rule_family else None

    return GovernanceVerdict(
        allowed=allowed,
        veto_reason=veto_reason,
        rule_id=rule_id,
        gate_thresholds=thresholds,
    )


def evaluate_for_profile(
    proposal: PolicyProposal,
    *,
    cursor_m: float,
    profile_id: str = "lunar_crater_5km",
    carrier: dict[str, Any] | None = None,
    physics: dict[str, Any] | None = None,
) -> GovernanceVerdict:
    envelope = load_mission_envelope(profile_id=profile_id)
    return evaluate_proposal(
        proposal,
        cursor_m=cursor_m,
        envelope=envelope,
        profile_id=profile_id,
        carrier=carrier,
        physics=physics,
    )


def record_action_receipt(
    state: dict[str, Any],
    receipt: ActionReceipt,
) -> dict[str, Any]:
    gov = state.setdefault("governance", {})
    log = list(gov.get("log") or [])
    log.append(receipt.to_dict())
    gov["log"] = log
    counters = dict(gov.get("counters") or {})
    counters["actions_evaluated"] = int(counters.get("actions_evaluated") or 0) + 1
    if not receipt.verdict.allowed:
        counters["vetoes"] = int(counters.get("vetoes") or 0) + 1
        counters["unsafe_intercepted"] = int(counters.get("unsafe_intercepted") or 0) + 1
        if receipt.verdict.rule_id in (
            RULE_LEGACY_CONFIDENCE,
            RULE_FORBIDDEN_ZONE,
            RULE_PHYSICS,
        ):
            counters["drift_caught"] = int(counters.get("drift_caught") or 0) + 1
    gov["counters"] = counters
    gov["last_receipt"] = receipt.to_dict()
    return state
