"""Robot OS HAL v1 — L5 abstract interfaces for OS synthesis.

Interfaces: PoseSource · ActuationSink · EnergyLedger · MissionClock
proof_tier: HAL_SIM_SLICE (implementations) — not MEASURED · not iron LC-2 drivers.

TABU: claim drivers on real hardware · claim VI-2 bus MEASURED.
Canon cites: fixtures/twin/robot_brain_architecture_v1.json (L_bus_vi2 · L_actuation_lc2).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

HAL_PROOF_TIER = "HAL_SIM_SLICE"

# Teaching constants — sim slice only, not bench LC-2 FOC.
LC2_POD_COUNT = 6
LC2_PWM_HZ = 20_000
VI2_HASH_FIELD = "map_hash"


@dataclass(frozen=True)
class PoseSnapshot:
    carrier_id: str
    cursor_m: float
    map_hash: str
    segment_start_m: float
    segment_end_m: float
    vi2_hash_aligned: bool = False


@dataclass(frozen=True)
class ActuationCommand:
    command: str
    thrust_n: float = 0.0


@dataclass
class ActuationState:
    command: str
    pod_thrust_n: list[float] = field(default_factory=list)
    fan_rpm: list[float] = field(default_factory=list)
    driver_temp_c: list[float] = field(default_factory=list)
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "pod_thrust_n": list(self.pod_thrust_n),
            "fan_rpm": list(self.fan_rpm),
            "driver_temp_c": list(self.driver_temp_c),
            "accepted": self.accepted,
        }


@dataclass(frozen=True)
class EnergySnapshot:
    wh_spent: float
    wh_budget_remain: float
    wh_mission_m: float


@dataclass(frozen=True)
class MissionClockSnapshot:
    tick: int
    phi_macro_tick: int
    segment_ticks: int


class PoseSource(ABC):
    """Read traverse pose + VI-2 map hash from carrier-side state."""

    @abstractmethod
    def read_pose(self) -> PoseSnapshot:
        ...


class ActuationSink(ABC):
    """LC-2 actuation port — accept motion commands (sim teaching thrust proxy)."""

    @abstractmethod
    def accept_command(self, cmd: ActuationCommand) -> bool:
        ...

    @abstractmethod
    def read_actuation_state(self) -> ActuationState:
        ...


class EnergyLedger(ABC):
    """Mission Wh ledger — VI-2 wh_mission teaching gate."""

    @abstractmethod
    def read_energy(self) -> EnergySnapshot:
        ...

    @abstractmethod
    def record_tick_wh(self, delta_wh: float) -> None:
        ...


class MissionClock(ABC):
    """Macro mission tick aligned with live-state carrier.ticks."""

    @abstractmethod
    def read_clock(self) -> MissionClockSnapshot:
        ...

    @abstractmethod
    def advance(self) -> MissionClockSnapshot:
        ...


@dataclass
class RobotOsHalStack:
    """Bundle of HAL interfaces for kernel wiring."""

    pose: PoseSource
    actuation: ActuationSink
    energy: EnergyLedger
    clock: MissionClock
    proof_tier: str = HAL_PROOF_TIER
    carrier_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        pose = self.pose.read_pose()
        act = self.actuation.read_actuation_state()
        eng = self.energy.read_energy()
        clk = self.clock.read_clock()
        return {
            "proof_tier": self.proof_tier,
            "carrier_id": self.carrier_id,
            "pose": {
                "cursor_m": pose.cursor_m,
                "map_hash": pose.map_hash,
                "vi2_hash_aligned": pose.vi2_hash_aligned,
            },
            "actuation": act.to_dict(),
            "energy": {
                "wh_spent": eng.wh_spent,
                "wh_budget_remain": eng.wh_budget_remain,
                "wh_mission_m": eng.wh_mission_m,
            },
            "clock": {
                "tick": clk.tick,
                "phi_macro_tick": clk.phi_macro_tick,
                "segment_ticks": clk.segment_ticks,
            },
        }
