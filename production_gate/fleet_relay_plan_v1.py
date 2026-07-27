"""Fleet relay plan v1 — N-hop segment + handoff anchors per profile.

Shared by coordinator, carrier sim, and runtime gates.
TABU: invent hops not grounded in CMC relay plan.
"""
from __future__ import annotations

from typing import Any

from production_gate.chip_mission_situation_inherit_v1 import PROFILES

RelayHop = dict[str, Any]


def relay_plan(profile_id: str) -> list[RelayHop]:
    """Handoff anchors — must match carrier_mission_cognition_v1._relay_plan."""
    if profile_id not in PROFILES:
        raise ValueError(f"unknown profile: {profile_id}")
    traverse_m = float(PROFILES[profile_id]["traverse_m"])
    if profile_id == "lunar_crater_5km":
        return [
            {
                "frac": 0.5,
                "donor": "scout_A",
                "recipient": "scout_B",
                "cursor_m": traverse_m * 0.5,
            },
        ]
    if profile_id == "lunar_traverse_50km":
        return [
            {
                "frac": 0.25,
                "donor": "scout_A",
                "recipient": "scout_B",
                "cursor_m": traverse_m * 0.25,
            },
            {
                "frac": 0.5,
                "donor": "scout_B",
                "recipient": "scout_C",
                "cursor_m": traverse_m * 0.5,
            },
            {
                "frac": 0.75,
                "donor": "scout_C",
                "recipient": "scout_D",
                "cursor_m": traverse_m * 0.75,
            },
        ]
    if profile_id == "lunar_base_construct_alpha":
        return [
            {
                "frac": 0.5,
                "donor": "survey_A",
                "recipient": "survey_B",
                "cursor_m": traverse_m * 0.5,
            },
        ]
    raise ValueError(f"relay plan not defined for {profile_id}")


def carrier_chain(profile_id: str) -> list[str]:
    hops = relay_plan(profile_id)
    ids = [hops[0]["donor"]]
    for hop in hops:
        ids.append(hop["recipient"])
    return ids


def segment_bounds(profile_id: str) -> list[tuple[float, float]]:
    """Per-carrier (start_m, end_m) aligned with relay_plan fractions."""
    prof = PROFILES[profile_id]
    traverse_m = float(prof["traverse_m"])
    hops = relay_plan(profile_id)
    fracs = [0.0] + [float(h["frac"]) for h in hops] + [1.0]
    chain = carrier_chain(profile_id)
    out: list[tuple[float, float]] = []
    for i, cid in enumerate(chain):
        start = traverse_m * fracs[i]
        end = traverse_m * fracs[i + 1]
        out.append((start, end))
    return out


def hop_for_donor(profile_id: str, donor_id: str) -> RelayHop | None:
    for hop in relay_plan(profile_id):
        if hop["donor"] == donor_id:
            return hop
    return None


def terminal_carrier(profile_id: str) -> str:
    return carrier_chain(profile_id)[-1]


def is_terminal(profile_id: str, carrier_id: str) -> bool:
    return carrier_id == terminal_carrier(profile_id)
