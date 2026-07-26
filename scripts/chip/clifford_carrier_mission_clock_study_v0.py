"""P2.2 — carrier mission clock study @ study anchor (not 100 MHz theater)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_TWIN = _REPO / "fixtures" / "twin"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_CARRIER_MISSION_CLOCK_STUDY_RECEIPT_v1.json"
_STA_BIND = _CHIP / "CHIP_CLIFFORD_WORLD_MOTION_STA_BIND_RECEIPT_v1.json"
_CLOCK = _TWIN / "dogfood_twin_iron_clock_feed_v1.json"
_MMIO_MAP = _REPO / "docs/agent_workflow/CLIFFORD_CARRIER_DEV_BOARD_MMIO_MAP_V0.md"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_carrier_mission_clock_study(*, write: bool = True) -> dict[str, Any]:
    sta = _load(_STA_BIND)
    clock = _load(_CLOCK)
    sta_m = sta.get("sta_mapped") or {}

    anchor_mhz = float(clock.get("study_anchor_mhz") or sta_m.get("study_anchor_mhz") or 27.5)
    ceiling_mhz = float(clock.get("bringup_mhz_ceiling") or sta_m.get("bringup_mhz_ceiling") or 0.0)
    wns_ns = float(sta_m.get("wns_ns") or clock.get("wns_ns") or 0.0)
    phi_period_ns = float(clock.get("phi_period_ns") or sta_m.get("phi_period_ns") or (1000.0 / anchor_mhz))

    mission_mhz = anchor_mhz
    checks = [
        {"id": "sta_bind_pass", "pass": sta.get("verdict") == "PASS"},
        {"id": "iron_clock_feed", "pass": clock.get("verdict") == "IRON_CLOCK_FEED_READY"},
        {"id": "study_anchor_25_30_band", "pass": 25.0 <= anchor_mhz <= 30.0},
        {"id": "wns_thermometer_present", "pass": wns_ns != 0.0},
        {"id": "mmio_map_sketch", "pass": _MMIO_MAP.is_file()},
        {"id": "not_timing_closed_100mhz", "pass": sta_m.get("timing_closed") is not True},
    ]
    verdict = "CARRIER_MISSION_CLOCK_STUDY_PASS" if all(c["pass"] for c in checks) else "CARRIER_MISSION_CLOCK_STUDY_FAIL"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_CARRIER_MISSION_CLOCK_STUDY_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "mission_clock": {
            "study_anchor_mhz": anchor_mhz,
            "study_anchor_band": clock.get("study_anchor_band", "25-30"),
            "bringup_mhz_ceiling": ceiling_mhz,
            "mission_target_mhz": mission_mhz,
            "phi_period_ns": round(phi_period_ns, 3),
            "wns_ns": wns_ns,
            "binding": sta_m.get("binding") or clock.get("binding"),
            "macro_compose_ns": clock.get("macro_compose_ns"),
        },
        "carrier": {
            "mapped_netlist": sta_m.get("mapped_netlist"),
            "yosys_cells": sta_m.get("yosys_cells"),
            "yosys_dff": sta_m.get("yosys_dff"),
            "mmio_map_doc": str(_MMIO_MAP.relative_to(_REPO)).replace("\\", "/"),
        },
        "honesty": {
            "chip_is_carrier": True,
            "clifford_alu_is_crown": True,
            "not_fpga_signoff": True,
            "not_100mhz_claim": anchor_mhz < 50.0,
            "wns_negative_expected": wns_ns < 0,
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_carrier_mission_clock_study()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "CARRIER_MISSION_CLOCK_STUDY_PASS" else 1)
