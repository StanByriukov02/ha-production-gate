"""Pure governance rule evaluation v1 — shared semantics with evidence_engine E1–E4.

Gate interceptor maps rule families → R1–R4 IDs. evidence_engine uses E1–E4.
TABU: hardcoded zone literals · veto after actuation.
"""
from __future__ import annotations

from typing import Any

from production_gate.robot_os_mission_envelope_v1 import (
    command_allowed,
    cursor_in_forbidden_zone,
    traverse_crosses_forbidden_zone,
)

RULE_FAMILY_COMMAND = "command"
RULE_FAMILY_ZONE = "zone"
RULE_FAMILY_PHYSICS = "physics"
RULE_FAMILY_CONFIDENCE = "confidence"


def _physics_gates(envelope: dict[str, Any]) -> dict[str, Any]:
    return dict(envelope.get("physics_gates") or {})


def _sinkage_mm_max(envelope: dict[str, Any]) -> float:
    gates = _physics_gates(envelope)
    return float(gates.get("sinkage_mm_max_traverse", gates.get("sinkage_mm_max", 18.0)))


def physics_blocks_traverse(physics: dict[str, Any], envelope: dict[str, Any]) -> tuple[bool, str | None]:
    gates = _physics_gates(envelope)
    if gates.get("require_traverse_feasible", True) and physics.get("traverse_feasible") is False:
        return True, "traverse_not_feasible"
    if physics.get("sinkage_risk"):
        return True, "sinkage_risk"
    sinkage_mm = float(physics.get("sinkage_mm") or 0.0)
    if sinkage_mm > _sinkage_mm_max(envelope):
        return True, "sinkage_mm_exceeded"
    return False, None


def zone_blocks_traverse(
    cursor_m: float,
    intent_m: float,
    envelope: dict[str, Any],
) -> tuple[bool, str | None, dict[str, Any]]:
    """Align with evidence_engine: in_zone at cursor · segment cross cursor→intent."""
    in_zone, zone_id = cursor_in_forbidden_zone(cursor_m, envelope)
    crossed, cross_zone = traverse_crosses_forbidden_zone(cursor_m, intent_m, envelope)
    meta = {
        "cursor_m": cursor_m,
        "intent_cursor_m": intent_m,
        "in_zone": in_zone,
        "crossed": crossed,
        "zone_id": zone_id or cross_zone,
    }
    if in_zone or crossed:
        return True, str(zone_id or cross_zone or "forbidden"), meta
    return False, None, meta


def confidence_blocks(
    *,
    confidence: float,
    source: str,
    envelope: dict[str, Any],
    legacy_sources: frozenset[str],
    action_only_sources: frozenset[str],
) -> bool:
    confidence_min = float(envelope.get("confidence_min") or 0.6)
    if source in action_only_sources:
        return False
    if source not in legacy_sources:
        return False
    gate_flag = envelope.get("confidence_gate")
    if gate_flag is not None and not bool(gate_flag):
        return False
    return float(confidence) < confidence_min


def evaluate_governance_rules(
    *,
    command: str,
    confidence: float,
    source: str,
    cursor_m: float,
    intent_m: float,
    envelope: dict[str, Any],
    physics: dict[str, Any] | None,
    legacy_confidence_sources: frozenset[str],
    action_only_sources: frozenset[str],
) -> tuple[bool, str | None, str | None, dict[str, Any]]:
    """
    Returns (allowed, veto_reason, rule_family, thresholds).

    rule_family is one of RULE_FAMILY_* or None when allowed.
    """
    confidence_min = float(envelope.get("confidence_min") or 0.6)
    thresholds: dict[str, Any] = {
        "confidence_min": confidence_min,
        "envelope_id": envelope.get("envelope_id"),
        "profile_id": envelope.get("profile_id"),
    }

    if not command_allowed(command, envelope):
        return False, "command_not_in_envelope", RULE_FAMILY_COMMAND, {
            **thresholds,
            "command": command,
        }

    if command == "traverse":
        blocked, zone_id, zone_meta = zone_blocks_traverse(cursor_m, intent_m, envelope)
        if blocked:
            return False, "workspace_envelope_violated", RULE_FAMILY_ZONE, {
                **thresholds,
                **zone_meta,
                "zone_id": zone_id,
            }

        phys = dict(physics or {})
        if phys:
            blocked_phys, reason = physics_blocks_traverse(phys, envelope)
            if blocked_phys:
                return False, reason, RULE_FAMILY_PHYSICS, {
                    **thresholds,
                    "cursor_m": cursor_m,
                    "sinkage_mm": phys.get("sinkage_mm"),
                    "traverse_feasible": phys.get("traverse_feasible"),
                }

    if confidence_blocks(
        confidence=confidence,
        source=source,
        envelope=envelope,
        legacy_sources=legacy_confidence_sources,
        action_only_sources=action_only_sources,
    ):
        return False, "confidence_below_gate", RULE_FAMILY_CONFIDENCE, {
            **thresholds,
            "proposal_confidence": confidence,
        }

    return True, None, None, thresholds
