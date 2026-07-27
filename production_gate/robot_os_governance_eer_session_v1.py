"""Optional eer-0.1 session accumulator for closed-loop gate governance.

Uses sibling evidence_engine when present. Re-evaluates via GovernanceGate public API.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from production_gate.robot_os_governance_eer_bridge_v1 import evidence_engine_available
from production_gate.robot_os_governance_interceptor_v1 import ACTION_ONLY_SOURCES
from production_gate.robot_os_governance_types_v1 import PolicyProposal
from production_gate.robot_os_mission_envelope_v1 import load_mission_envelope

_EE_SRC = Path(__file__).resolve().parents[1].parent / "evidence_engine" / "src"
_GATE_KEY = "eer_gate"


def _import_gate():
    if not evidence_engine_available():
        return None, None
    if str(_EE_SRC) not in sys.path:
        sys.path.insert(0, str(_EE_SRC))
    from evidence_engine.gate import GovernanceGate  # noqa: WPS433
    from evidence_engine.types import Proposal  # noqa: WPS433

    return GovernanceGate, Proposal


def init_eer_session(state: dict[str, Any], *, profile_id: str = "lunar_crater_5km") -> bool:
    GovernanceGate, _ = _import_gate()
    if GovernanceGate is None:
        return False
    envelope = load_mission_envelope(profile_id=profile_id)
    backend = str((state.get("governance") or {}).get("policy_port", {}).get("backend") or "gate_policy")
    state.setdefault("governance", {})[_GATE_KEY] = GovernanceGate(
        envelope=envelope,
        policy_source_id=backend,
        mode="closed_loop",
    )
    return True


def _to_ee_proposal(
    proposal: PolicyProposal,
    *,
    carrier: dict[str, Any] | None,
    physics: dict[str, Any] | None,
    Proposal,
) -> Any:
    intent: dict[str, Any] = {}
    if carrier:
        raw = carrier.get("policy_inject_target_cursor_m", carrier.get("policy_intent_cursor_m"))
        if raw is not None:
            intent["intent_cursor_m"] = float(raw)
    if physics:
        intent["physics"] = dict(physics)
    confidence = None if proposal.source in ACTION_ONLY_SOURCES else proposal.confidence
    return Proposal(
        action_id=proposal.action_id,
        command=proposal.command,
        confidence=confidence,
        source=proposal.source,
        intent=intent,
    )


def record_eer_step(
    state: dict[str, Any],
    *,
    proposal: PolicyProposal,
    cursor_m: float,
    carrier: dict[str, Any] | None = None,
    physics: dict[str, Any] | None = None,
) -> bool:
    GovernanceGate, Proposal = _import_gate()
    if GovernanceGate is None:
        return False
    gate = (state.get("governance") or {}).get(_GATE_KEY)
    if gate is None:
        return False
    ee_proposal = _to_ee_proposal(proposal, carrier=carrier, physics=physics, Proposal=Proposal)
    gate.evaluate(ee_proposal, cursor_m=cursor_m, physics=physics)
    return True


def export_eer_session_receipt(state: dict[str, Any]) -> dict[str, Any] | None:
    gate = (state.get("governance") or {}).get(_GATE_KEY)
    if gate is None:
        return None
    steps = gate.step_count
    if steps == 0:
        return None
    receipt = gate.build_receipt()
    if not gate.verify_accumulated():
        raise RuntimeError("eer session receipt self-verify failed")
    return receipt
