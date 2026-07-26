"""Live fleet state bus v1 — L3 · single JSON truth for coordinator + N carriers.



TABU: claim robot OS · claim MEASURED fleet · invent metrics not in state file.

"""

from __future__ import annotations



import json

import os

import time

from copy import deepcopy

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Callable



_REPO = Path(__file__).resolve().parents[1]

RUNTIME = _REPO / "results" / "runtime"

DEFAULT_STATE = RUNTIME / "live_fleet_state_v1.json"



STATE_ID = "live_fleet_state_v1"





def _utc() -> str:

    return datetime.now(timezone.utc).isoformat()





def empty_state(

    *,

    mission_id: str = "M-lunar-relay-teaching",

    profile_id: str = "lunar_crater_5km",

    carrier_ids: tuple[str, ...] = ("scout_A", "scout_B"),

) -> dict[str, Any]:
    from dogfood_platform.manipulator_integrator_port_v1 import default_carrier_manipulator_fields

    manip_defaults = default_carrier_manipulator_fields()

    return {

        "state_id": STATE_ID,

        "version": 0,

        "mission_id": mission_id,

        "profile_id": profile_id,

        "coordinator": {

            "phase": "init",

            "verdict": None,

            "fail_reason": None,

            "active_handoff_id": None,

            "hop_index": 0,

            "total_hops": 0,

            "carrier_order": list(carrier_ids),

            "active_carrier_id": None,

            "terminal_carrier_id": carrier_ids[-1] if carrier_ids else None,

        },

        "carriers": {

            cid: {

                "carrier_id": cid,

                "phase": "idle",

                "command": "idle",

                "segment_start_m": 0.0,

                "segment_end_m": 0.0,

                "cursor_m": 0.0,

                "ticks": 0,

                "map_hash": "",

                "handoff_packet": None,

                **manip_defaults,

            }

            for cid in carrier_ids

        },

        "situation_pool": {

            "valid": False,

            "map_hash": "",

            "cursor_m": 0.0,

            "donor_id": "",

        },

        "handoff_log": [],

        "updated_utc": _utc(),

    }





def ensure_carrier_slots(state: dict[str, Any], carrier_ids: tuple[str, ...]) -> dict[str, Any]:

    """Grow or shrink carrier map to match requested ids without dropping unrelated keys."""

    carriers = state.setdefault("carriers", {})

    for cid in carrier_ids:

        if cid not in carriers:

            carriers[cid] = {

                "carrier_id": cid,

                "phase": "idle",

                "command": "idle",

                "segment_start_m": 0.0,

                "segment_end_m": 0.0,

                "cursor_m": 0.0,

                "ticks": 0,

                "map_hash": "",

                "handoff_packet": None,

                **manip_defaults,

            }

    coord = state.setdefault("coordinator", {})

    coord["carrier_order"] = list(carrier_ids)

    coord["terminal_carrier_id"] = carrier_ids[-1] if carrier_ids else None

    return state





def read_state(path: Path = DEFAULT_STATE) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    last_err: Exception | None = None
    for attempt in range(40):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (PermissionError, OSError) as exc:
            last_err = exc
            time.sleep(0.02 * (attempt + 1))
    raise RuntimeError(f"read_state failed after retries: {path}") from last_err





def write_state(state: dict[str, Any], path: Path = DEFAULT_STATE) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)

    state["updated_utc"] = _utc()

    tmp = path.with_suffix(".tmp")

    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    os.replace(tmp, path)





def update_state(

    mutator: Callable[[dict[str, Any]], dict[str, Any]],

    *,

    path: Path = DEFAULT_STATE,

    retries: int = 80,

    carrier_ids: tuple[str, ...] | None = None,

) -> dict[str, Any]:

    path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(retries):

        base = read_state(path) if path.is_file() else empty_state(

            carrier_ids=carrier_ids or ("scout_A", "scout_B")

        )

        if carrier_ids:

            ensure_carrier_slots(base, carrier_ids)

        draft = deepcopy(base)

        out = mutator(draft)

        out["version"] = int(base.get("version", 0)) + 1

        out["updated_utc"] = _utc()

        tmp = path.with_suffix(f".tmp.{os.getpid()}")

        try:

            tmp.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

            os.replace(tmp, path)

            return out

        except OSError:

            if tmp.is_file():

                tmp.unlink(missing_ok=True)

            time.sleep(0.02 * (attempt + 1))

    raise RuntimeError(f"live state update failed after {retries} retries: {path}")


