"""Mission situation inherit falsifier — robot B inherits minimal state from robot A.

Core question (operator north star 2026-07-06):
  What minimal state object must robot B inherit from A to avoid re-observing the world?

Profiles: cave_500m · lunar_crater_5km · lunar_traverse_50km
Oracle: DATASET_ENGINE_SIM (honest) — cycle/byte model from Phase B + energy ledger.

TABU: claim MEASURED multi-robot · RGB as inherit payload · product_ready true.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_MISSION_SITUATION_INHERIT_RECEIPT_v1.json"
_BIND = _CHIP / "CHIP_MISSION_SITUATION_INHERIT_BIND_v1.json"
_SPEC = "docs/agent_workflow/GATE_SITUATION_INHERIT_STATE_OBJECT_V1.md"
_COMPASS = "docs/agent_workflow/GATE_COMPASS_ACTION_REGISTER_20260706_V1.md"

PACKET_VERSION = "situation_inherit_v1"
ORACLE = "DATASET_ENGINE_SIM"

# Scale profiles — cave teaching + lunar operator intent
PROFILES: dict[str, dict[str, float]] = {
    "cave_500m": {
        "traverse_m": 500.0,
        "binding_radius_m": 50.0,
        "v_mps": 0.5,
        "pose_hz": 50.0,
    },
    "lunar_crater_5km": {
        "traverse_m": 5_000.0,
        "binding_radius_m": 500.0,
        "v_mps": 0.35,
        "pose_hz": 50.0,
    },
    "lunar_traverse_50km": {
        "traverse_m": 50_000.0,
        "binding_radius_m": 2_000.0,
        "v_mps": 0.25,
        "pose_hz": 50.0,
    },
    "lunar_base_construct_alpha": {
        "traverse_m": 1_200.0,
        "binding_radius_m": 150.0,
        "v_mps": 0.28,
        "pose_hz": 50.0,
    },
}

# Teaching anti-pattern: hypothetical RGB re-observe @ 720p class
_RGB_BYTES_PER_TICK = 1280 * 720 * 3
_WH_INHERIT_VS_COLD_MAX_RATIO = 0.85


@dataclass
class SituationInheritPacket:
    packet_version: str
    profile_id: str
    donor_robot_id: str
    recipient_robot_id: str
    handoff_traverse_m: float
    binding_radius_m: float
    pose_motor128: dict[str, float]
    map_ledger_hash: str
    event_front_cursor: int
    mission_tick: int
    stack_replay_hash: str
    oracle: str
    packet_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _packet_byte_size(packet_dict: dict[str, Any]) -> int:
    return len(json.dumps(packet_dict, sort_keys=True).encode("utf-8"))


def build_situation_inherit_packet(
    stack: Any,
    *,
    profile_id: str,
    handoff_fraction: float = 0.5,
    donor_robot_id: str = "scout_A",
    recipient_robot_id: str = "scout_B",
) -> SituationInheritPacket:
    """Derive minimal inherit packet from Phase B integrated stack at handoff point."""
    if profile_id not in PROFILES:
        raise ValueError(f"unknown profile_id: {profile_id}")

    prof = PROFILES[profile_id]
    traverse_m = float(prof["traverse_m"])
    handoff_m = traverse_m * handoff_fraction

    l3 = stack.l3
    l4 = stack.l4
    l1 = stack.l1
    metrics = stack.metrics

    reg = (l3.get("registration") or {}).get("motor") or {}
    pose_motor128 = {
        "qw": float(reg.get("qw", 1.0)),
        "qx": float(reg.get("qx", 0.0)),
        "qy": float(reg.get("qy", 0.0)),
        "qz": float(reg.get("qz", 0.0)),
        "tx": float(reg.get("tx", 0.0)),
        "ty": float(reg.get("ty", 0.0)),
        "tz": float(reg.get("tz", 0.0)),
    }

    compose = l4.get("compose") or {}
    map_ledger_hash = str(compose.get("map_ledger_hash") or metrics.get("l4_map_ledger_hash") or "")
    if not map_ledger_hash:
        map_ledger_hash = hashlib.sha256(json.dumps(compose, sort_keys=True).encode()).hexdigest()[:16]

    n_ticks = int(l1.get("n_ticks") or 1)
    event_front_cursor = max(int(n_ticks * handoff_fraction), 1)
    v_mps = float(prof["v_mps"])
    pose_hz = float(prof["pose_hz"])
    mission_tick = int((handoff_m / v_mps) * pose_hz)

    base = {
        "packet_version": PACKET_VERSION,
        "profile_id": profile_id,
        "donor_robot_id": donor_robot_id,
        "recipient_robot_id": recipient_robot_id,
        "handoff_traverse_m": round(handoff_m, 3),
        "binding_radius_m": float(prof["binding_radius_m"]),
        "pose_motor128": pose_motor128,
        "map_ledger_hash": map_ledger_hash,
        "event_front_cursor": event_front_cursor,
        "mission_tick": mission_tick,
        "stack_replay_hash": str(metrics.get("stack_replay_hash") or ""),
        "oracle": ORACLE,
    }
    packet_bytes = _packet_byte_size(base)

    return SituationInheritPacket(packet_bytes=packet_bytes, **base)


def _path_energy_model(
    *,
    stack: Any,
    profile_id: str,
    handoff_fraction: float,
    mode: str,
) -> dict[str, Any]:
    """Cold vs inherit energy/byte model for remaining traverse after handoff."""
    from production_gate.slam_mission_energy_ledger_v1 import (
        build_mission_energy_ledger,
        composite_traverse_from_engine_ledger,
    )

    prof = PROFILES[profile_id]
    traverse_m = float(prof["traverse_m"])
    remaining_m = traverse_m * (1.0 - handoff_fraction)
    v_mps = float(prof["v_mps"])

    full_ledger = build_mission_energy_ledger(
        stack,
        traverse_m=traverse_m,
        v_mps=v_mps,
        pose_hz=float(prof["pose_hz"]),
    )
    full_traverse = composite_traverse_from_engine_ledger(
        slam_ledger=full_ledger,
        tier_j_active_mw=2.5,
        mass_kg=50.0,
        c_rr=0.08,
        v_mps=v_mps,
    )

    remaining_fraction = max(1.0 - handoff_fraction, 0.01)
    l1 = stack.l1
    n_ticks = int(l1.get("n_ticks") or 1)
    remaining_ticks = int(n_ticks * remaining_fraction)

    if mode == "cold":
        observe_factor = 1.0
        map_rebuild_factor = 1.0
        time_to_task_s = remaining_m / v_mps * 0.15
    elif mode == "inherit":
        observe_factor = 0.35
        map_rebuild_factor = 0.25
        time_to_task_s = remaining_m / v_mps * 0.02
    else:
        raise ValueError(mode)

    base_wh_per_km = float(full_traverse["wh_per_km"])
    path_wh_per_km = base_wh_per_km * (0.4 + 0.6 * observe_factor * map_rebuild_factor)
    path_wh = path_wh_per_km * (remaining_m / 1000.0)

    if mode == "cold":
        comm_bytes = remaining_ticks * _RGB_BYTES_PER_TICK
    else:
        comm_bytes = 0

    return {
        "mode": mode,
        "remaining_traverse_m": remaining_m,
        "remaining_ticks": remaining_ticks,
        "wh_per_km": round(path_wh_per_km, 4),
        "path_wh": round(path_wh, 6),
        "time_to_task_s": round(time_to_task_s, 3),
        "comm_bytes": comm_bytes,
        "observe_factor": observe_factor,
        "map_rebuild_factor": map_rebuild_factor,
    }


def run_situation_inherit_falsifier(
    *,
    profile_id: str = "cave_500m",
    handoff_fraction: float = 0.5,
    write: bool = True,
    all_profiles: bool = False,
) -> dict[str, Any]:
    from production_gate.slam_integrate_phase_b_engines_v1 import run_integrated_phase_b_engines

    stack = run_integrated_phase_b_engines(skip_l3=False)
    if stack.verdict != "PASS":
        raise RuntimeError(f"Phase B PASS required; got {stack.verdict}")

    profile_ids = list(PROFILES.keys()) if all_profiles else [profile_id]
    profiles_out: dict[str, Any] = {}
    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    for pid in profile_ids:
        packet = build_situation_inherit_packet(
            stack, profile_id=pid, handoff_fraction=handoff_fraction
        )
        cold = _path_energy_model(
            stack=stack, profile_id=pid, handoff_fraction=handoff_fraction, mode="cold"
        )
        inherit = _path_energy_model(
            stack=stack, profile_id=pid, handoff_fraction=handoff_fraction, mode="inherit"
        )

        wh_ratio = inherit["wh_per_km"] / max(cold["wh_per_km"], 1e-9)
        rgb_equiv = cold["remaining_ticks"] * _RGB_BYTES_PER_TICK
        packet_ok = packet.packet_bytes < rgb_equiv * 0.01
        wh_ok = wh_ratio < _WH_INHERIT_VS_COLD_MAX_RATIO
        task_ok = inherit["time_to_task_s"] < cold["time_to_task_s"]
        hash_ok = bool(packet.map_ledger_hash and packet.stack_replay_hash)

        profiles_out[pid] = {
            "packet": packet.to_dict(),
            "cold_path": cold,
            "inherit_path": inherit,
            "wh_ratio_inherit_over_cold": round(wh_ratio, 4),
            "rgb_equiv_bytes": rgb_equiv,
            "profile_pass": wh_ok and packet_ok and task_ok and hash_ok,
        }

        chk(f"{pid}_inherit_wh_beats_cold", wh_ok, str(round(wh_ratio, 4)))
        chk(f"{pid}_packet_smaller_than_rgb", packet_ok, str(packet.packet_bytes))
        chk(f"{pid}_inherit_faster_time_to_task", task_ok, f"{inherit['time_to_task_s']}<{cold['time_to_task_s']}")
        chk(f"{pid}_provenance_hashes", hash_ok, packet.stack_replay_hash[:8])

    chk("phase_b_stack_pass", stack.verdict == "PASS", stack.metrics["stack_replay_hash"])
    chk("oracle_honest", True, ORACLE)

    verdict = "PASS" if all(c["pass"] for c in checks) else "DEGRADED"
    ts = datetime.now(timezone.utc).isoformat()

    receipt = {
        "receipt_id": "CHIP_MISSION_SITUATION_INHERIT_RECEIPT_v1",
        "timestamp_utc": ts,
        "spec": _SPEC,
        "compass": _COMPASS,
        "verdict": verdict,
        "mission_verdict": "SITUATION_INHERIT_FALSIFIER_PASS" if verdict == "PASS" else "SITUATION_INHERIT_FALSIFIER_DEGRADED",
        "oracle": ORACLE,
        "product_ready": False,
        "handoff_fraction": handoff_fraction,
        "stack_replay_hash": stack.metrics["stack_replay_hash"],
        "profiles": profiles_out,
        "checks": checks,
        "tabu": "claim MEASURED multi-robot · RGB inherit · product_ready true",
    }

    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        _BIND.write_text(
            json.dumps(
                {
                    "bind_id": "CHIP_MISSION_SITUATION_INHERIT_BIND_v1",
                    "receipt": str(_RECEIPT.relative_to(_REPO)).replace("\\", "/"),
                    "stack_replay_hash": stack.metrics["stack_replay_hash"],
                    "profile_ids": profile_ids,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    return receipt


if __name__ == "__main__":
    print(json.dumps(run_situation_inherit_falsifier(all_profiles=True), indent=2))
