"""Clifford bind for lunar robot OS — seeds live state from Phase B + motor128.

proof_tier: ENGINE_SIM — not iron MMIO · not MEASURED.
TABU: hardcoded stack_replay_hash in fleet/kernel.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dogfood_platform.chip_mission_situation_inherit_v1 import build_situation_inherit_packet
from dogfood_platform.fleet_relay_plan_v1 import carrier_chain
from dogfood_platform.slam_integrate_phase_b_engines_v1 import run_integrated_phase_b_engines

_REPO = Path(__file__).resolve().parents[1]
_CACHE_PATH = _REPO / "results" / "runtime" / "clifford_bind_cache_v1.json"

PROOF_TIER = "ENGINE_SIM"


def _bind_from_phase_b(*, profile_id: str) -> dict[str, Any]:
    stack = run_integrated_phase_b_engines()
    if stack.verdict != "PASS":
        raise RuntimeError(f"phase_b_stack FAIL: {stack.verdict}")
    pkt = build_situation_inherit_packet(
        stack,
        profile_id=profile_id,
        handoff_fraction=0.0,
        donor_robot_id="clifford_seed",
        recipient_robot_id=carrier_chain(profile_id)[0],
    )
    return {
        "proof_tier": PROOF_TIER,
        "profile_id": profile_id,
        "stack_replay_hash": pkt.stack_replay_hash,
        "map_ledger_hash": pkt.map_ledger_hash,
        "pose_motor128": pkt.pose_motor128,
        "event_front_cursor": pkt.event_front_cursor,
        "mission_tick": pkt.mission_tick,
        "phi_macro_tick": int(pkt.mission_tick) % 8,
        "phase_b_verdict": stack.verdict,
        "oracle": pkt.oracle,
    }


def _load_cache(profile_id: str) -> dict[str, Any] | None:
    if not _CACHE_PATH.is_file():
        return None
    cached = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    if cached.get("profile_id") != profile_id:
        return None
    if not cached.get("stack_replay_hash"):
        return None
    return cached


def _write_cache(bind: dict[str, Any]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(bind, indent=2) + "\n", encoding="utf-8")


def ensure_clifford_bind_cache(*, profile_id: str, force_refresh: bool = False) -> dict[str, Any]:
    """Run Phase B once per profile; reuse disk cache for fleet multi-process startup."""
    if not force_refresh:
        hit = _load_cache(profile_id)
        if hit is not None:
            return hit
    bind = _bind_from_phase_b(profile_id=profile_id)
    _write_cache(bind)
    return bind


def build_clifford_bind(*, profile_id: str = "lunar_crater_5km", force_refresh: bool = False) -> dict[str, Any]:
    return ensure_clifford_bind_cache(profile_id=profile_id, force_refresh=force_refresh)


def apply_clifford_bind(state: dict[str, Any], *, profile_id: str) -> dict[str, Any]:
    existing = state.get("clifford_bind") or {}
    if (
        existing.get("profile_id") == profile_id
        and existing.get("stack_replay_hash")
        and existing.get("map_ledger_hash")
    ):
        bind = existing
    else:
        bind = build_clifford_bind(profile_id=profile_id)
        state["clifford_bind"] = bind
    chain = carrier_chain(profile_id)
    if not chain:
        return state
    lead = chain[0]
    c = state["carriers"].get(lead)
    if not c:
        return state
    map_hash = str(bind["map_ledger_hash"])
    c["map_hash"] = map_hash
    c["clifford"] = {
        "pose_motor128": bind["pose_motor128"],
        "stack_replay_hash": bind["stack_replay_hash"],
        "phi_macro_tick": bind["phi_macro_tick"],
        "proof_tier": PROOF_TIER,
    }
    from dogfood_platform.lie_integrator_port_v1 import ensure_lie_integrator_bind

    ensure_lie_integrator_bind(state, profile_id=profile_id)
    return state


def stack_replay_hash_from_state(state: dict[str, Any]) -> str:
    bind = state.get("clifford_bind") or {}
    h = str(bind.get("stack_replay_hash") or "")
    if h:
        return h
    lead_cliff = (state.get("carriers") or {}).get("scout_A", {}).get("clifford") or {}
    return str(lead_cliff.get("stack_replay_hash") or "")
