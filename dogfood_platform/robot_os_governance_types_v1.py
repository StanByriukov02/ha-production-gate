"""Governance types v1 — policy proposal · verdict · action receipt.

proof_tier: GOVERNANCE_SLICE — not MEASURED · not VLA.
TABU: hardcoded allow/veto without envelope fixture.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PROOF_TIER = "GOVERNANCE_SLICE"


@dataclass(frozen=True)
class PolicyProposal:
    action_id: int
    command: str
    confidence: float
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> PolicyProposal:
        return cls(
            action_id=int(row["action_id"]),
            command=str(row["command"]),
            confidence=float(row["confidence"]),
            source=str(row["source"]),
        )


@dataclass(frozen=True)
class GovernanceVerdict:
    allowed: bool
    gate_thresholds: dict[str, Any]
    proof_tier: str = PROOF_TIER
    veto_reason: str | None = None
    rule_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> GovernanceVerdict:
        return cls(
            allowed=bool(row["allowed"]),
            gate_thresholds=dict(row.get("gate_thresholds") or {}),
            proof_tier=str(row.get("proof_tier") or PROOF_TIER),
            veto_reason=row.get("veto_reason"),
            rule_id=row.get("rule_id"),
        )


@dataclass(frozen=True)
class ActionReceipt:
    action_id: int
    carrier_id: str
    proposal: PolicyProposal
    verdict: GovernanceVerdict
    cursor_m: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "carrier_id": self.carrier_id,
            "proposal": self.proposal.to_dict(),
            "verdict": self.verdict.to_dict(),
            "cursor_m": self.cursor_m,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> ActionReceipt:
        return cls(
            action_id=int(row["action_id"]),
            carrier_id=str(row["carrier_id"]),
            proposal=PolicyProposal.from_dict(row["proposal"]),
            verdict=GovernanceVerdict.from_dict(row["verdict"]),
            cursor_m=float(row.get("cursor_m") or 0.0),
        )


def governance_counters() -> dict[str, int]:
    return {
        "actions_evaluated": 0,
        "vetoes": 0,
        "drift_caught": 0,
        "unsafe_intercepted": 0,
    }


def init_governance_state(state: dict[str, Any], *, enabled: bool = True) -> dict[str, Any]:
    state["governance"] = {
        "enabled": enabled,
        "proof_tier": PROOF_TIER,
        "action_seq": 0,
        "log": [],
        "counters": governance_counters(),
        "tabu": "claim MEASURED governance",
    }
    return state
