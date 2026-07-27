"""PolicyPort v1 — adapter surface for future VLA/LLM backends.

Default: PolicyStubBackend only. TABU: claim VLA MEASURED wired.
"""
from __future__ import annotations

from typing import Any, Protocol

from production_gate.robot_os_governance_types_v1 import PolicyProposal
from production_gate.robot_os_policy_stub_v1 import DEFAULT_INJECT_BAD_AT, propose as stub_propose

PROOF_TIER = "POLICY_PORT_SLICE"
BACKEND_STUB = "policy_stub_v1"
BACKEND_VLA_MOCK = "vla_mock_v1"
BACKEND_REGOLITH_PLANNER = "regolith_planner_v1"
BACKEND_SMOLVLA_TRACE = "smolvla_trace_v1"


class PolicyPort(Protocol):
    def propose(self, state: dict[str, Any], carrier_id: str) -> PolicyProposal: ...


class PolicyStubBackend:
    """Default backend — reproducible inject stub."""

    source_id = BACKEND_STUB

    def __init__(
        self,
        *,
        inject_bad_at: int = DEFAULT_INJECT_BAD_AT,
        inject_enabled: bool = True,
    ) -> None:
        self.inject_bad_at = inject_bad_at
        self.inject_enabled = inject_enabled

    def propose(self, state: dict[str, Any], carrier_id: str) -> PolicyProposal:
        return stub_propose(
            state,
            carrier_id,
            inject_bad_at=self.inject_bad_at,
            inject_enabled=self.inject_enabled,
        )


class VlaMockBackend:
    """Recorded-trace mock — not live VLA. TABU: claim production VLA."""

    source_id = BACKEND_VLA_MOCK

    def __init__(self, trace: list[dict[str, Any]]) -> None:
        self._trace = list(trace)
        self._idx = 0

    def propose(self, state: dict[str, Any], carrier_id: str) -> PolicyProposal:
        if self._idx >= len(self._trace):
            return PolicyStubBackend(inject_enabled=False).propose(state, carrier_id)
        row = self._trace[self._idx]
        self._idx += 1
        return PolicyProposal(
            action_id=int(row.get("action_id", self._idx - 1)),
            command=str(row.get("command", "traverse")),
            confidence=float(row.get("confidence", 0.9)),
            source=self.source_id,
        )


class RegolithPlannerBackend:
    """Policy from W_regolith / Newton-X physics — not external VLA. TABU: claim learned policy."""

    source_id = BACKEND_REGOLITH_PLANNER
    NOMINAL_CONFIDENCE = 0.88
    MARGINAL_CONFIDENCE = 0.45
    RECOVER_CONFIDENCE = 0.25

    def _ensure_physics(self, state: dict[str, Any], carrier_id: str) -> dict[str, Any]:
        carrier = state["carriers"][carrier_id]
        physics = carrier.get("lunar_physics")
        if physics:
            return physics
        if (state.get("newton_x") or {}).get("enabled"):
            from production_gate.robot_os_newton_x_world_step_v1 import step_newton_x_world
            from production_gate.robot_os_kernel_v1 import SEGMENT_TICKS

            seg_len = abs(
                float(carrier.get("segment_end_m", 0.0)) - float(carrier.get("segment_start_m", 0.0))
            )
            step_m = seg_len / SEGMENT_TICKS if seg_len else 0.01
            step_newton_x_world(state, carrier_id, step_m)
            return dict(carrier.get("lunar_physics") or {})
        return {}

    def propose(self, state: dict[str, Any], carrier_id: str) -> PolicyProposal:
        from production_gate.robot_os_policy_stub_v1 import next_action_id

        carrier = state["carriers"][carrier_id]
        action_id = next_action_id(state)
        physics = self._ensure_physics(state, carrier_id)

        live_cmd = str(carrier.get("command") or "idle")
        command = live_cmd if live_cmd in ("traverse", "idle", "recover") else "traverse"
        if command == "idle" and carrier.get("phase") in ("armed", "traverse"):
            command = "traverse"

        traverse_feasible = bool(physics.get("traverse_feasible", True))
        sinkage_risk = bool(physics.get("sinkage_risk", False))
        sinkage_mm = float(physics.get("sinkage_mm") or 0.0)

        if not traverse_feasible or sinkage_risk:
            command = "recover"
            confidence = self.RECOVER_CONFIDENCE
        elif sinkage_mm > 15.0:
            confidence = self.MARGINAL_CONFIDENCE
        else:
            confidence = self.NOMINAL_CONFIDENCE

        return PolicyProposal(
            action_id=action_id,
            command=command,
            confidence=confidence,
            source=self.source_id,
        )


def default_policy_port(
    *,
    inject_bad_at: int = DEFAULT_INJECT_BAD_AT,
    inject_enabled: bool = True,
) -> PolicyStubBackend:
    return PolicyStubBackend(inject_bad_at=inject_bad_at, inject_enabled=inject_enabled)


def _inject_params_from_governance(state: dict[str, Any]) -> tuple[int, bool]:
    gov = state.get("governance") or {}
    raw = gov.get("inject_bad_at")
    inject_bad_at = int(DEFAULT_INJECT_BAD_AT if raw is None else raw)
    return inject_bad_at, bool(gov.get("inject_enabled", True))


def init_policy_port_bind(
    state: dict[str, Any],
    *,
    backend: str = BACKEND_STUB,
    inject_bad_at: int | None = None,
    inject_enabled: bool | None = None,
    vla_mock_trace: list[dict[str, Any]] | None = None,
    smolvla_trace_path: str | None = None,
    smolvla_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Persist PolicyPort selection in live state for governed actuation."""
    gov = state.setdefault("governance", {})
    if inject_bad_at is not None:
        gov["inject_bad_at"] = int(inject_bad_at)
    if inject_enabled is not None:
        gov["inject_enabled"] = bool(inject_enabled)
    cfg: dict[str, Any] = {"backend": str(backend)}
    if vla_mock_trace is not None:
        cfg["vla_mock_trace"] = list(vla_mock_trace)
    if smolvla_trace_path is not None:
        cfg["smolvla_trace_path"] = str(smolvla_trace_path)
    if smolvla_trace is not None:
        cfg["smolvla_trace"] = list(smolvla_trace)
    gov["policy_port"] = cfg
    return state


def resolve_policy_port(state: dict[str, Any]) -> PolicyPort:
    """Build PolicyPort backend from governance state (default: stub)."""
    gov = state.get("governance") or {}
    cfg = gov.get("policy_port") or {}
    backend = str(cfg.get("backend") or BACKEND_STUB)
    inject_bad_at, inject_enabled = _inject_params_from_governance(state)

    if backend == BACKEND_VLA_MOCK:
        trace = list(cfg.get("vla_mock_trace") or [])
        return VlaMockBackend(trace)

    if backend == BACKEND_SMOLVLA_TRACE:
        from production_gate.robot_os_policy_smolvla_trace_v1 import (
            SmolVlaTraceBackend,
            load_smolvla_trace,
        )

        inline = cfg.get("smolvla_trace")
        if inline:
            return SmolVlaTraceBackend(list(inline))
        path = cfg.get("smolvla_trace_path")
        return SmolVlaTraceBackend(load_smolvla_trace(path))

    if backend == BACKEND_REGOLITH_PLANNER:
        return RegolithPlannerBackend()

    return PolicyStubBackend(inject_bad_at=inject_bad_at, inject_enabled=inject_enabled)
