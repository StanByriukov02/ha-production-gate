"""Robot OS HAL sim v1 — L5 SIM implementations wired to live_fleet_state_v1.

Binds PoseSource · ActuationSink · EnergyLedger · MissionClock to carrier fields:
  cursor_m · map_hash · ticks

proof_tier: HAL_SIM_SLICE — WORLD_PHYSICS_SIM teaching proxy, not iron LC-2 FOC.
TABU: claim drivers on real hardware · claim MEASURED actuation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from production_gate.fleet_live_state_v1 import DEFAULT_STATE, read_state
from production_gate.robot_os_hal_v1 import (
    HAL_PROOF_TIER,
    LC2_POD_COUNT,
    LC2_PWM_HZ,
    ActuationCommand,
    ActuationSink,
    ActuationState,
    EnergyLedger,
    EnergySnapshot,
    MissionClock,
    MissionClockSnapshot,
    PoseSnapshot,
    PoseSource,
    RobotOsHalStack,
)
from production_gate.robot_os_kernel_v1 import HalHooks, RobotOsKernel, SEGMENT_TICKS
from production_gate.robot_os_sched_policy_v1 import default_wh_budget, segment_wh_proxy

# Teaching hover thrust for ≤20 kg scout — sim envelope, not propulsion PASS.
_SCOUT_MASS_KG = 20.0
_G0 = 9.80665
_HOVER_THRUST_N = _SCOUT_MASS_KG * _G0 * 1.05
_CRUISE_THRUST_N = _HOVER_THRUST_N * 0.35
_FAN_RPM_IDLE = 0.0
_FAN_RPM_HOVER = 18_000.0
_FAN_RPM_CRUISE = 24_000.0
_DRIVER_TEMP_BASE_C = 32.0


def _carrier_slot(state: dict[str, Any], carrier_id: str) -> dict[str, Any]:
    c = (state.get("carriers") or {}).get(carrier_id)
    if not c:
        raise KeyError(f"unknown carrier: {carrier_id}")
    return c


def _vi2_hash_aligned(state: dict[str, Any], carrier: dict[str, Any]) -> bool:
    carrier_hash = str(carrier.get("map_hash") or "")
    if not carrier_hash:
        return False
    pool = state.get("situation_pool") or {}
    pool_hash = str(pool.get("map_hash") or "")
    if pool_hash and pool_hash == carrier_hash:
        return True
    pkt = carrier.get("handoff_packet") or {}
    pkt_hash = str(pkt.get("map_hash") or "")
    return bool(pkt_hash and pkt_hash == carrier_hash)


@dataclass
class FleetStatePoseSource(PoseSource):
    carrier_id: str
    state: dict[str, Any]

    def read_pose(self) -> PoseSnapshot:
        c = _carrier_slot(self.state, self.carrier_id)
        return PoseSnapshot(
            carrier_id=self.carrier_id,
            cursor_m=float(c.get("cursor_m", 0.0)),
            map_hash=str(c.get("map_hash") or ""),
            segment_start_m=float(c.get("segment_start_m", 0.0)),
            segment_end_m=float(c.get("segment_end_m", 0.0)),
            vi2_hash_aligned=_vi2_hash_aligned(self.state, c),
        )


@dataclass
class FleetStateActuationSink(ActuationSink):
    carrier_id: str
    state: dict[str, Any]
    _last: ActuationState = field(default_factory=lambda: ActuationState(command="idle"))

    def _thrust_for_command(self, command: str) -> float:
        if command == "traverse":
            return _CRUISE_THRUST_N
        if command in ("hover", "armed"):
            return _HOVER_THRUST_N
        return 0.0

    def _fan_rpm_for_command(self, command: str) -> float:
        if command == "traverse":
            return _FAN_RPM_CRUISE
        if command in ("hover", "armed"):
            return _FAN_RPM_HOVER
        return _FAN_RPM_IDLE

    def accept_command(self, cmd: ActuationCommand) -> bool:
        c = _carrier_slot(self.state, self.carrier_id)
        live_cmd = str(c.get("command") or "idle")
        thrust = cmd.thrust_n if cmd.thrust_n > 0 else self._thrust_for_command(cmd.command)
        per_pod = thrust / LC2_POD_COUNT
        rpm = self._fan_rpm_for_command(cmd.command)
        temp_delta = 2.5 if cmd.command == "traverse" else 0.5
        ticks = int(c.get("ticks", 0))
        accepted = cmd.command in ("idle", "traverse", "recover", "hover") or live_cmd == cmd.command
        self._last = ActuationState(
            command=cmd.command,
            pod_thrust_n=[round(per_pod, 3)] * LC2_POD_COUNT,
            fan_rpm=[round(rpm, 1)] * LC2_POD_COUNT,
            driver_temp_c=[round(_DRIVER_TEMP_BASE_C + temp_delta + ticks * 0.1, 2)] * LC2_POD_COUNT,
            accepted=accepted,
        )
        return accepted

    def read_actuation_state(self) -> ActuationState:
        if self._last.command == "idle" and not self._last.pod_thrust_n:
            c = _carrier_slot(self.state, self.carrier_id)
            live = str(c.get("command") or "idle")
            self.accept_command(ActuationCommand(command=live))
        return self._last


@dataclass
class FleetStateEnergyLedger(EnergyLedger):
    carrier_id: str
    state: dict[str, Any]
    wh_spent: float = 0.0

    def _budget_wh(self) -> float:
        profile_id = str(self.state.get("profile_id", "lunar_crater_5km"))
        return default_wh_budget(profile_id)

    def _segment_wh_per_tick(self) -> float:
        c = _carrier_slot(self.state, self.carrier_id)
        profile_id = str(self.state.get("profile_id", "lunar_crater_5km"))
        seg_m = abs(float(c.get("segment_end_m", 0)) - float(c.get("segment_start_m", 0)))
        total = segment_wh_proxy(profile_id, seg_m)
        return total / max(SEGMENT_TICKS, 1)

    def read_energy(self) -> EnergySnapshot:
        budget = self._budget_wh()
        c = _carrier_slot(self.state, self.carrier_id)
        cursor_m = float(c.get("cursor_m", 0.0))
        return EnergySnapshot(
            wh_spent=round(self.wh_spent, 6),
            wh_budget_remain=round(max(budget - self.wh_spent, 0.0), 6),
            wh_mission_m=round(cursor_m, 3),
        )

    def record_tick_wh(self, delta_wh: float) -> None:
        if delta_wh <= 0:
            delta_wh = self._segment_wh_per_tick()
        self.wh_spent = round(self.wh_spent + delta_wh, 6)


@dataclass
class FleetStateMissionClock(MissionClock):
    carrier_id: str
    state: dict[str, Any]

    def read_clock(self) -> MissionClockSnapshot:
        c = _carrier_slot(self.state, self.carrier_id)
        tick = int(c.get("ticks", 0))
        return MissionClockSnapshot(
            tick=tick,
            phi_macro_tick=tick % 8,
            segment_ticks=SEGMENT_TICKS,
        )

    def advance(self) -> MissionClockSnapshot:
        return self.read_clock()


def build_sim_hal_stack(
    carrier_id: str,
    state: dict[str, Any],
) -> RobotOsHalStack:
    """Construct HAL sim stack bound to an in-memory fleet state dict."""
    return RobotOsHalStack(
        pose=FleetStatePoseSource(carrier_id, state),
        actuation=FleetStateActuationSink(carrier_id, state),
        energy=FleetStateEnergyLedger(carrier_id, state),
        clock=FleetStateMissionClock(carrier_id, state),
        proof_tier=HAL_PROOF_TIER,
        carrier_id=carrier_id,
    )


def load_sim_hal_stack(
    carrier_id: str,
    *,
    state_path: Path = DEFAULT_STATE,
) -> RobotOsHalStack:
    """Load HAL sim stack from on-disk live fleet state."""
    return build_sim_hal_stack(carrier_id, read_state(state_path))


def wire_sim_hal_to_kernel(
    kernel: RobotOsKernel,
    hal: RobotOsHalStack,
    state: dict[str, Any],
) -> HalHooks:
    """Return HalHooks that drive sim HAL on kernel traverse ticks."""

    def on_tick_before(cid: str, carrier: dict[str, Any]) -> None:
        from production_gate.robot_os_governed_actuation_v1 import (
            apply_governance_before_actuation,
            governance_enabled,
        )
        from production_gate.robot_os_policy_only_actuation_v1 import (
            apply_policy_only_before_actuation,
            policy_only_enabled,
        )

        if policy_only_enabled(state):
            apply_policy_only_before_actuation(state, cid, hal)
            return
        if governance_enabled(state):
            apply_governance_before_actuation(state, cid, hal)
            return
        cmd = str(carrier.get("command") or "idle")
        hal.actuation.accept_command(ActuationCommand(command=cmd))

    def on_tick_after(cid: str, carrier: dict[str, Any]) -> None:
        hal.energy.record_tick_wh(0.0)
        pose = hal.pose.read_pose()
        if float(carrier.get("cursor_m", 0.0)) != pose.cursor_m:
            raise RuntimeError(f"HAL pose drift: {pose.cursor_m} != {carrier.get('cursor_m')}")
        from production_gate.manipulator_integrator_port_v1 import (
            manipulator_integrator_enabled,
            manipulator_tick_snapshot,
        )

        if manipulator_integrator_enabled(state):
            snap = manipulator_tick_snapshot(state, cid)
            if snap.get("manipulator_kernel_active") and not snap.get("ee_pose_motor_present"):
                if str(carrier.get("manipulator_command") or "idle") != "idle":
                    raise RuntimeError("manipulator active but ee_pose_motor missing after tick")

    def on_phase_enter(cid: str, phase: str, carrier: dict[str, Any]) -> None:
        hal.actuation.accept_command(ActuationCommand(command=phase if phase != "handoff" else "idle"))

    return HalHooks(
        on_tick_before=on_tick_before,
        on_tick_after=on_tick_after,
        on_phase_enter=on_phase_enter,
    )


def attach_sim_hal_to_kernel(
    kernel: RobotOsKernel,
    state: dict[str, Any],
) -> RobotOsHalStack:
    """Build sim HAL for kernel.carrier_id and wire into kernel.hal."""
    hal = build_sim_hal_stack(kernel.carrier_id, state)
    kernel.hal = wire_sim_hal_to_kernel(kernel, hal, state)
    return hal


def hal_sim_metadata() -> dict[str, Any]:
    """Static bind metadata for manifest / receipt synthesis."""
    return {
        "proof_tier": HAL_PROOF_TIER,
        "oracle": "WORLD_PHYSICS_SIM",
        "lc2_pwm_hz": LC2_PWM_HZ,
        "lc2_pod_count": LC2_POD_COUNT,
        "live_state_fields": [
            "cursor_m",
            "map_hash",
            "ticks",
            "joint_positions_rad",
            "joint_velocities_rad_s",
            "ee_pose",
            "ee_pose_motor",
            "manipulator_phase",
            "manipulator_command",
            "manipulator_mutex",
        ],
        "tabu": [
            "claim LC-2 FOC drivers on real hardware",
            "claim MEASURED actuation",
            "claim VI-2 bus MEASURED",
        ],
    }
