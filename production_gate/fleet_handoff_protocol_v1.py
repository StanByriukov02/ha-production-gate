"""Fleet handoff protocol v1 — L4 · ack/nack · content hash.

TABU: telepathy · handoff without hash · silent mismatch.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

PROTOCOL_VERSION = "fleet_handoff_v1"


@dataclass
class HandoffPacket:
    protocol_version: str
    handoff_id: str
    donor_id: str
    recipient_id: str
    profile_id: str
    map_hash: str
    cursor_m: float
    segment_end_m: float
    stack_replay_hash: str
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def content_hash(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "content_hash"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def build_handoff_packet(
    *,
    handoff_id: str,
    donor_id: str,
    recipient_id: str,
    profile_id: str,
    map_hash: str,
    cursor_m: float,
    segment_end_m: float,
    stack_replay_hash: str,
) -> HandoffPacket:
    base = {
        "protocol_version": PROTOCOL_VERSION,
        "handoff_id": handoff_id,
        "donor_id": donor_id,
        "recipient_id": recipient_id,
        "profile_id": profile_id,
        "map_hash": map_hash,
        "cursor_m": cursor_m,
        "segment_end_m": segment_end_m,
        "stack_replay_hash": stack_replay_hash,
    }
    return HandoffPacket(content_hash=content_hash(base), **base)


def validate_packet(packet: dict[str, Any]) -> tuple[bool, str]:
    if packet.get("protocol_version") != PROTOCOL_VERSION:
        return False, "bad_protocol_version"
    expect = content_hash(packet)
    if packet.get("content_hash") != expect:
        return False, "content_hash_mismatch"
    required = (
        "handoff_id",
        "donor_id",
        "recipient_id",
        "profile_id",
        "map_hash",
        "cursor_m",
        "stack_replay_hash",
    )
    for key in required:
        if key not in packet:
            return False, f"missing_{key}"
    return True, "ok"


def ack_entry(handoff_id: str, *, recipient_id: str) -> dict[str, Any]:
    return {"handoff_id": handoff_id, "event": "ack", "recipient_id": recipient_id}


def nack_entry(handoff_id: str, *, reason: str) -> dict[str, Any]:
    return {"handoff_id": handoff_id, "event": "nack", "reason": reason}
