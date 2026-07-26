"""Mission envelope v1 — workspace constraints from fixture (no Python oracle).

TABU: hardcoded forbidden zone literals in code.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_ENVELOPE = _REPO / "fixtures" / "robot" / "mission_envelope_lunar_crater_v1.json"

_ENVELOPE_BY_PROFILE: dict[str, str] = {
    "lunar_crater_5km": "mission_envelope_lunar_crater_v1.json",
}


def _fixture_path(profile_id: str) -> Path:
    name = _ENVELOPE_BY_PROFILE.get(profile_id)
    if not name:
        raise ValueError(f"no mission envelope fixture for profile_id={profile_id}")
    return _REPO / "fixtures" / "robot" / name


@lru_cache(maxsize=8)
def load_mission_envelope(*, profile_id: str = "lunar_crater_5km") -> dict[str, Any]:
    path = _fixture_path(profile_id)
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def cursor_in_forbidden_zone(cursor_m: float, envelope: dict[str, Any]) -> tuple[bool, str | None]:
    for zone in envelope.get("forbidden_zones") or []:
        lo = float(zone.get("cursor_m_min", 0))
        hi = float(zone.get("cursor_m_max", 0))
        if lo <= float(cursor_m) <= hi:
            return True, str(zone.get("zone_id") or "forbidden")
    return False, None


def traverse_crosses_forbidden_zone(
    prev_cursor_m: float,
    curr_cursor_m: float,
    envelope: dict[str, Any],
) -> tuple[bool, str | None]:
    """True when traverse segment [prev, curr] overlaps a forbidden band."""
    lo_m = min(prev_cursor_m, curr_cursor_m)
    hi_m = max(prev_cursor_m, curr_cursor_m)
    for zone in envelope.get("forbidden_zones") or []:
        lo = float(zone.get("cursor_m_min", 0))
        hi = float(zone.get("cursor_m_max", 0))
        if max(lo_m, lo) <= min(hi_m, hi):
            return True, str(zone.get("zone_id") or "forbidden")
    return False, None


def command_allowed(command: str, envelope: dict[str, Any]) -> bool:
    allowed = envelope.get("allowed_commands") or []
    return str(command) in allowed
