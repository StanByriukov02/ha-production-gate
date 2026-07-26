"""Chip carrier tier V3 gate — FPGA synth + mission clock + mapped signoff (carrier floor)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_chip_carrier_tier_v3(*, write: bool = True) -> dict[str, Any]:
    yosys = _load(_CHIP / "CHIP_CLIFFORD_FPGA_YOSYS_ELAB_RECEIPT_v1.json")
    mission = _load(_CHIP / "CHIP_CLIFFORD_CARRIER_MISSION_CLOCK_STUDY_RECEIPT_v1.json")
    p8 = _load(_CHIP / "CHIP_CLIFFORD_FPGA_P8_READINESS_RECEIPT_v1.json")
    m3 = _load(_CHIP / "CHIP_CLIFFORD_H1_MAPPED_ALU_PARITY_RECEIPT_v1.json")
    mapped = _load(_CHIP / "CHIP_CLIFFORD_WORLD_MOTION_MAPPED_MMIO_RECEIPT_v1.json")
    prod = _load(_CHIP / "CHIP_CLIFFORD_PRODUCTION_CROWN_GATE_RECEIPT_v1.json")

    m3_step = (m3.get("steps") or {}).get("M3") or {}
    checks = [
        {"id": "m3_mapped_carrier_signoff", "pass": m3_step.get("verdict") == "PASS"},
        {"id": "mapped_mmio_functional", "pass": mapped.get("verdict") == "PASS"},
        {"id": "yosys_carrier_elab", "pass": yosys.get("verdict") == "FPGA_YOSYS_ELAB_PASS"},
        {"id": "mission_clock_study", "pass": mission.get("verdict") == "CARRIER_MISSION_CLOCK_STUDY_PASS"},
        {"id": "p8_pre_silicon_inventory", "pass": p8.get("verdict") == "FPGA_P8_PRE_SILICON_READY"},
        {"id": "crown_production_pass", "pass": prod.get("verdict") == "PRODUCTION_CROWN_GATE_PASS"},
    ]
    verdict = "CHIP_CARRIER_TIER_V3_READY" if all(c["pass"] for c in checks) else "CHIP_CARRIER_TIER_V3_BUILDING"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_CHIP_CARRIER_TIER_V3_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "tier": "V3_carrier",
        "checks": checks,
        "next_tier": "V4: vendor P&R · MMIO HIL · measured silicon (PARK)",
        "honesty": {
            "chip_is_carrier": True,
            "clifford_alu_is_crown": True,
            "not_bitstream": True,
            "not_fpga_signoff": True,
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        (_CHIP / "CHIP_CLIFFORD_CHIP_CARRIER_TIER_V3_RECEIPT_v1.json").write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8"
        )
    return doc


if __name__ == "__main__":
    out = evaluate_chip_carrier_tier_v3()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "CHIP_CARRIER_TIER_V3_READY" else 1)
