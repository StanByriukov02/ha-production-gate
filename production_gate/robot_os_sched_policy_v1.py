"""Robot OS scheduler policy v1 — priority queue + Wh budget gate.

Uses chip_mission_situation_inherit PROFILES for segment energy proxy.
proof_tier: SIM_KERNEL_SLICE — not MEASURED · not full robot OS.
TABU: hardcoded Wh/map/hash literals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from production_gate.chip_mission_situation_inherit_v1 import PROFILES

PROOF_TIER = "SIM_KERNEL_SLICE"

# Lower number = higher priority.
COMMAND_PRIORITY: dict[str, int] = {
    "recover": 0,
    "handoff": 1,
    "charge": 1,
    "traverse": 2,
    "idle": 3,
}

DEFAULT_WH_BUDGET: dict[str, float] = {
    "cave_500m": 120.0,
    "lunar_crater_5km": 800.0,
    "lunar_traverse_50km": 6_000.0,
    "lunar_base_construct_alpha": 1_200.0,
}


def command_priority(command: str) -> int:
    return COMMAND_PRIORITY.get(command, 99)


def segment_wh_proxy(profile_id: str, segment_m: float) -> float:
    """Teaching Wh proxy from profile scale — SIM_KERNEL_SLICE, not bench measured."""
    if profile_id not in PROFILES:
        raise ValueError(f"unknown profile_id: {profile_id}")
    prof = PROFILES[profile_id]
    traverse_m = float(prof["traverse_m"])
    scale = max(traverse_m / 5_000.0, 0.1)
    wh_per_km = 8.0 + 4.0 * scale
    return wh_per_km * (max(segment_m, 0.0) / 1000.0)


def wh_budget_gate(
    profile_id: str,
    segment_m: float,
    budget_wh: float,
) -> tuple[bool, str, float]:
    need = segment_wh_proxy(profile_id, segment_m)
    if need > budget_wh:
        return False, "wh_budget_exceeded", need
    return True, "ok", need


def default_wh_budget(profile_id: str) -> float:
    if profile_id not in DEFAULT_WH_BUDGET:
        raise ValueError(f"unknown profile_id: {profile_id}")
    return DEFAULT_WH_BUDGET[profile_id]


@dataclass
class CommandQueue:
    """In-kernel command queue; live-state command is always highest pending source."""

    items: list[str] = field(default_factory=list)

    def enqueue(self, command: str) -> None:
        if command not in COMMAND_PRIORITY:
            return
        if command not in self.items:
            self.items.append(command)

    def pull_from_live(self, live_command: str | None) -> None:
        if live_command and live_command != "idle":
            self.enqueue(live_command)

    def select(
        self,
        *,
        profile_id: str,
        segment_m: float,
        budget_wh: float,
        live_command: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Return (command, reject_reason). reject_reason set when Wh gate blocks traverse."""
        self.pull_from_live(live_command)
        if not self.items:
            return None, None

        ranked = sorted(self.items, key=command_priority)
        for cmd in ranked:
            if cmd == "traverse":
                ok, reason, _ = wh_budget_gate(profile_id, segment_m, budget_wh)
                if not ok:
                    self.items = [c for c in self.items if c != "traverse"]
                    return "recover", reason
            self.items.remove(cmd)
            return cmd, None
        return None, None
