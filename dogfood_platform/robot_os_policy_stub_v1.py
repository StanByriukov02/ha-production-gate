"""Policy stub v1 — reproducible bad proposals for governance harness.

v2 inject: world-grounded forbidden traverse intent (not fake confidence).
TABU: claim VLA/LLM wired · random inject without action_id.
"""
from __future__ import annotations

from typing import Any

from dogfood_platform.robot_os_governance_interceptor_v1 import DEFAULT_FRAGILE_RIM_CURSOR_M
from dogfood_platform.robot_os_governance_types_v1 import PolicyProposal

SOURCE_ID = "policy_stub_v1"
DEFAULT_INJECT_BAD_AT = 47
NOMINAL_CONFIDENCE = 0.92
INJECT_CONFIDENCE = 0.31
ACTION_ONLY_NOMINAL_CONFIDENCE = 1.0


def next_action_id(state: dict[str, Any]) -> int:
    gov = state.setdefault("governance", {})
    seq = int(gov.get("action_seq") or 0)
    gov["action_seq"] = seq + 1
    return seq


def propose(
    state: dict[str, Any],
    carrier_id: str,
    *,
    inject_bad_at: int = DEFAULT_INJECT_BAD_AT,
    inject_enabled: bool = True,
    inject_target_cursor_m: float = DEFAULT_FRAGILE_RIM_CURSOR_M,
) -> PolicyProposal:
    """Emit traverse proposal; inject tick sets forbidden-zone intent (governance v2)."""
    carrier = state["carriers"][carrier_id]
    action_id = next_action_id(state)
    live_cmd = str(carrier.get("command") or "idle")
    command = live_cmd if live_cmd in ("traverse", "idle", "recover") else "traverse"
    if command == "idle" and carrier.get("phase") in ("armed", "traverse"):
        command = "traverse"

    if inject_enabled and action_id == inject_bad_at:
        carrier["policy_inject_target_cursor_m"] = float(inject_target_cursor_m)
        return PolicyProposal(
            action_id=action_id,
            command="traverse",
            confidence=ACTION_ONLY_NOMINAL_CONFIDENCE,
            source=SOURCE_ID,
        )

    carrier.pop("policy_inject_target_cursor_m", None)
    return PolicyProposal(
        action_id=action_id,
        command=command,
        confidence=NOMINAL_CONFIDENCE,
        source=SOURCE_ID,
    )
