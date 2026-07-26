"""Robot OS kernel slice v1 — L5 carrier-side tick scheduler + phase FSM + HAL hooks.

NOT a full robot OS. proof_tier: SIM_KERNEL_SLICE — not MEASURED.
TABU: hardcoded stack_replay_hash · claim full robot OS.
Reads/writes carrier slot in live_fleet_state_v1.json via caller.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from dogfood_platform.fleet_handoff_protocol_v1 import build_handoff_packet
from dogfood_platform.fleet_relay_plan_v1 import hop_for_donor, is_terminal
from dogfood_platform.robot_os_clifford_bind_v1 import stack_replay_hash_from_state
from dogfood_platform.robot_os_sched_policy_v1 import (
    CommandQueue,
    PROOF_TIER,
    default_wh_budget,
    wh_budget_gate,
)

KERNEL_PHASE_IDLE = "idle"
KERNEL_PHASE_TRAVERSE = "traverse"
KERNEL_PHASE_HANDOFF = "handoff"
KERNEL_PHASE_RECOVER = "recover"

KERNEL_PHASES = frozenset(
    {KERNEL_PHASE_IDLE, KERNEL_PHASE_TRAVERSE, KERNEL_PHASE_HANDOFF, KERNEL_PHASE_RECOVER}
)

# Live-state carrier.phase values the kernel accepts as entry points.
_LIVE_ARMED = frozenset({"idle", "armed"})
_LIVE_TRAVERSE = frozenset({"traverse"})
_LIVE_HANDOFF = frozenset({"handoff_pending", "handoff"})
_LIVE_RECOVER = frozenset({"recover"})

SEGMENT_TICKS = 6


@dataclass
class HalHooks:
    """Optional HAL injection points — default no-ops for sim slice."""

    on_tick_before: Callable[[str, dict[str, Any]], None] = field(default=lambda _cid, _c: None)
    on_tick_after: Callable[[str, dict[str, Any]], None] = field(default=lambda _cid, _c: None)
    on_phase_enter: Callable[[str, str, dict[str, Any]], None] = field(
        default=lambda _cid, _phase, _c: None
    )


def live_phase_to_kernel(phase: str) -> str:
    if phase in _LIVE_TRAVERSE or phase == "armed":
        return KERNEL_PHASE_TRAVERSE
    if phase in _LIVE_HANDOFF:
        return KERNEL_PHASE_HANDOFF
    if phase in _LIVE_RECOVER:
        return KERNEL_PHASE_RECOVER
    return KERNEL_PHASE_IDLE


def kernel_phase_to_live(kernel_phase: str, *, prior_live: str) -> str:
    if kernel_phase == KERNEL_PHASE_TRAVERSE:
        return "traverse"
    if kernel_phase == KERNEL_PHASE_HANDOFF:
        return "handoff_pending"
    if kernel_phase == KERNEL_PHASE_RECOVER:
        return "recover"
    if prior_live in ("relay", "done"):
        return prior_live
    if prior_live == "armed":
        return "armed"
    return "idle"


@dataclass
class RobotOsKernel:
    carrier_id: str
    hal: HalHooks = field(default_factory=HalHooks)
    command_queue: CommandQueue = field(default_factory=CommandQueue)
    kernel_phase: str = KERNEL_PHASE_IDLE
    recover_reason: str | None = None
    wh_budget_wh: float | None = None

    def _carrier(self, state: dict[str, Any]) -> dict[str, Any]:
        c = state["carriers"].get(self.carrier_id)
        if not c:
            raise KeyError(f"unknown carrier: {self.carrier_id}")
        return c

    def _budget(self, state: dict[str, Any]) -> float:
        if self.wh_budget_wh is not None:
            return self.wh_budget_wh
        return default_wh_budget(str(state.get("profile_id", "lunar_crater_5km")))

    def sync_from_state(self, state: dict[str, Any]) -> None:
        c = self._carrier(state)
        self.kernel_phase = live_phase_to_kernel(str(c.get("phase", "idle")))
        live_cmd = str(c.get("command") or "idle")
        self.command_queue.pull_from_live(None if live_cmd == "idle" else live_cmd)

    def should_tick(self, state: dict[str, Any]) -> bool:
        c = self._carrier(state)
        cmd = c.get("command")
        phase = c.get("phase")
        return cmd == "traverse" or phase == "traverse"

    def _set_kernel_phase(self, state: dict[str, Any], phase: str) -> None:
        c = self._carrier(state)
        prior = str(c.get("phase", "idle"))
        live = kernel_phase_to_live(phase, prior_live=prior)
        if str(c.get("phase")) == live and self.kernel_phase == phase:
            return
        if str(c.get("phase")) != live:
            c["phase"] = live
            self.hal.on_phase_enter(self.carrier_id, phase, c)
        self.kernel_phase = phase

    def _segment_m(self, c: dict[str, Any]) -> float:
        return abs(float(c.get("segment_end_m", 0)) - float(c.get("segment_start_m", 0)))

    def _dispatch_command(self, state: dict[str, Any]) -> None:
        c = self._carrier(state)
        cmd, reject = self.command_queue.select(
            profile_id=str(state.get("profile_id", "lunar_crater_5km")),
            segment_m=self._segment_m(c),
            budget_wh=self._budget(state),
            live_command=str(c.get("command") or "idle"),
        )
        if reject:
            self.recover_reason = reject
            self._set_kernel_phase(state, KERNEL_PHASE_RECOVER)
            c["command"] = "recover"
            return
        if cmd == "recover":
            self.recover_reason = reject or "sched_recover"
            self._set_kernel_phase(state, KERNEL_PHASE_RECOVER)
            c["command"] = "recover"
        elif cmd == "traverse":
            self._set_kernel_phase(state, KERNEL_PHASE_TRAVERSE)
            c["command"] = "traverse"
        elif cmd == "handoff":
            self._set_kernel_phase(state, KERNEL_PHASE_HANDOFF)
            c["command"] = "idle"

    def _tick_traverse(self, state: dict[str, Any]) -> None:
        c = self._carrier(state)
        c["_cursor_before_tick"] = float(c.get("cursor_m", 0.0))
        self.hal.on_tick_before(self.carrier_id, c)
        from dogfood_platform.manipulator_integrator_port_v1 import (
            advance_manipulator_tick,
            manipulator_integrator_enabled,
        )

        if manipulator_integrator_enabled(state) and str(c.get("manipulator_command") or "idle") != "idle":
            advance_manipulator_tick(state, c)
        if c.pop("governance_skip_movement", False):
            return
        c["ticks"] = int(c.get("ticks", 0)) + 1
        seg_len = float(c["segment_end_m"]) - float(c["segment_start_m"])
        step = seg_len / SEGMENT_TICKS
        lie_cfg = state.get("lie_integrator") or {}
        if lie_cfg.get("enabled"):
            from dogfood_platform.lie_integrator_port_v1 import advance_traverse_segment_lie

            advance_traverse_segment_lie(state, c, step_m=step)
        else:
            c["cursor_m"] = float(c["segment_start_m"]) + step * c["ticks"]
        self.hal.on_tick_after(self.carrier_id, c)

        from dogfood_platform.cmr_wear_chip_coupling_v1 import apply_wear_chip_tick

        apply_wear_chip_tick(state, self.carrier_id)

        if c["ticks"] >= SEGMENT_TICKS:
            self._set_kernel_phase(state, KERNEL_PHASE_HANDOFF)
            c["command"] = "idle"
            if state.get("construction_mode"):
                c["phase"] = "idle"
                self.kernel_phase = KERNEL_PHASE_IDLE
                return
            profile_id = str(state.get("profile_id", "lunar_crater_5km"))
            replay = stack_replay_hash_from_state(state)
            if not replay:
                raise RuntimeError("clifford_bind missing stack_replay_hash — run ensure_clifford_bind_cache")
            if is_terminal(profile_id, self.carrier_id):
                c["phase"] = "done"
                c["command"] = "idle"
                self.kernel_phase = KERNEL_PHASE_IDLE
                return
            hop = hop_for_donor(profile_id, self.carrier_id)
            if not hop:
                c["phase"] = "done"
                c["command"] = "idle"
                self.kernel_phase = KERNEL_PHASE_IDLE
                return
            hid = f"ho-{uuid.uuid4().hex[:8]}"
            pkt = build_handoff_packet(
                handoff_id=hid,
                donor_id=self.carrier_id,
                recipient_id=str(hop["recipient"]),
                profile_id=profile_id,
                map_hash=str(c.get("map_hash") or ""),
                cursor_m=float(c["cursor_m"]),
                segment_end_m=float(c["segment_end_m"]),
                stack_replay_hash=replay,
            )
            c["handoff_packet"] = pkt.to_dict()
            state["coordinator"]["phase"] = "wait_handoff"

    def _tick_handoff(self, state: dict[str, Any]) -> None:
        # Handoff completion is coordinator-driven; kernel holds phase until relay/done.
        pass

    def _tick_recover(self, state: dict[str, Any]) -> None:
        c = self._carrier(state)
        c["command"] = "idle"
        self.recover_reason = None
        self._set_kernel_phase(state, KERNEL_PHASE_IDLE)

    def _wh_gate_or_recover(self, state: dict[str, Any]) -> bool:
        """Return True if caller should continue tick; False if entered recover."""
        c = self._carrier(state)
        if c.get("command") != "traverse":
            return True
        ok, reason, _ = wh_budget_gate(
            str(state.get("profile_id", "lunar_crater_5km")),
            self._segment_m(c),
            self._budget(state),
        )
        if ok:
            return True
        self.recover_reason = reason
        self._set_kernel_phase(state, KERNEL_PHASE_RECOVER)
        c["command"] = "recover"
        return False

    def tick_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """One scheduler tick — mutates carrier slot + returns state."""
        self.sync_from_state(state)
        c = self._carrier(state)

        from dogfood_platform.manipulator_integrator_port_v1 import (
            advance_manipulator_tick,
            manipulator_integrator_enabled,
        )

        manip_cmd = str(c.get("manipulator_command") or "idle")
        if (
            manipulator_integrator_enabled(state)
            and manip_cmd != "idle"
            and c.get("command") == "idle"
            and c.get("phase") == "idle"
        ):
            advance_manipulator_tick(state, c)
            return state

        if c.get("command") != "traverse" and c.get("phase") not in ("armed", "traverse"):
            return state

        if not self._wh_gate_or_recover(state):
            return state

        if self.kernel_phase == KERNEL_PHASE_TRAVERSE or c.get("phase") in ("armed", "traverse"):
            self._set_kernel_phase(state, KERNEL_PHASE_TRAVERSE)
            self._tick_traverse(state)
        elif self.kernel_phase == KERNEL_PHASE_HANDOFF:
            self._tick_handoff(state)
        elif self.kernel_phase == KERNEL_PHASE_RECOVER:
            self._tick_recover(state)

        return state
