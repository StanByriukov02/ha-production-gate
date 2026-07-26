"""Robot factory slots registry — earth-primary rungs (R1/R4…)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_MOON = _REPO / "results" / "platform_bpass" / "moon"
_SLOTS = _MOON / "ROBOT_FACTORY_SLOTS_v1.json"
_CANON = "docs/HwatomOrgOS/05_OPERATOR_PLAST/_REGISTERS/ROBOT_FACTORY_IFT1_VISION_V1.md"


def load_slots() -> dict[str, Any]:
    if _SLOTS.is_file():
        return json.loads(_SLOTS.read_text(encoding="utf-8"))
    return {
        "registry_id": "ROBOT_FACTORY_SLOTS_v1",
        "track": "LUNAR_ROBOT_IFT1",
        "slots": {},
        "rung_status": {},
    }


def save_slots(data: dict[str, Any]) -> None:
    data["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    data["canon"] = _CANON
    _MOON.mkdir(parents=True, exist_ok=True)
    _SLOTS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def set_slot(
    data: dict[str, Any],
    *,
    slot_id: str,
    rung: str,
    value: Any,
    unit: str,
    tier: str,
    environment_id: str,
    bind: str | None = None,
    formula: str | None = None,
) -> None:
    data.setdefault("slots", {})[slot_id] = {
        "slot_id": slot_id,
        "rung": rung,
        "value": value,
        "unit": unit,
        "tier": tier,
        "environment_id": environment_id,
        "bind": bind,
        "formula": formula,
    }


def set_rung_status(data: dict[str, Any], rung: str, status: str, *, filled_slots: list[str]) -> None:
    data.setdefault("rung_status", {})[rung] = {
        "status": status,
        "filled_slots": filled_slots,
        "environment": "earth_lab_298k" if rung in ("R0", "R1", "R2", "R3", "R4", "R5", "R6", "R8") else "dual",
    }


def clear_factory_rungs(data: dict[str, Any], *, keep: frozenset[str]) -> None:
    """Drop slots/rung_status outside keep — phase test isolation."""
    slots = data.setdefault("slots", {})
    for slot_id in [k for k, v in slots.items() if v.get("rung") not in keep]:
        del slots[slot_id]
    rs = data.setdefault("rung_status", {})
    for rung in [r for r in rs if r not in keep]:
        del rs[rung]

