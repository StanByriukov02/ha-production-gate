"""Expedition degraded gate — honest PASS for all legs except M3 full mapped signoff."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_MOON = _REPO / "results" / "platform_bpass" / "moon"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_EXPEDITION_DEGRADED_GATE_RECEIPT_v1.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_expedition_degraded(*, write: bool = True) -> dict[str, Any]:
    crown = _load(_CHIP / "CHIP_CLIFFORD_CROWN_STACK_GATE_RECEIPT_v1.json")
    h6 = _load(_CHIP / "CHIP_CLIFFORD_CROWN_MOTOR_BIND_RECEIPT_v1.json")
    moon_bind = _load(_CHIP / "CHIP_CLIFFORD_CROWN_MOON_BIND_RECEIPT_v1.json")
    fpga = _load(_CHIP / "CHIP_CLIFFORD_FPGA_P8_READINESS_RECEIPT_v1.json")
    iron = _load(_CHIP / "CHIP_CLIFFORD_WORLD_MOTION_IRON_RECEIPT_v1.json")
    moon_iron = _load(_CHIP / "CHIP_CLIFFORD_MOON_MOTION_IRON_RECEIPT_v1.json")
    mapped = _load(_CHIP / "CHIP_CLIFFORD_WORLD_MOTION_MAPPED_MMIO_RECEIPT_v1.json")
    glue = _load(_CHIP / "CLIFFORD_PYTHON_GLUE_STATE_v1.json")
    engine = _load(_MOON / "ROBOT_IFT2_CLIFFORD_WORLD_ENGINE_RECEIPT_v1.json")

    crown_ok = crown.get("verdict") in ("CROWN_STACK_PASS", "CROWN_STACK_DEGRADED")
    m3_ok = crown.get("verdict") == "CROWN_STACK_PASS"
    checks = [
        {"id": "glue_gate", "pass": glue.get("glue_level") == "none"},
        {"id": "earth_iron", "pass": iron.get("verdict") == "PASS"},
        {"id": "moon_iron", "pass": moon_iron.get("verdict") == "PASS"},
        {"id": "mapped_mmio", "pass": mapped.get("verdict") in ("PASS", "DEGRADED")},
        {"id": "crown_stack_core", "pass": crown_ok},
        {"id": "h6_crown_motor", "pass": h6.get("verdict") == "CROWN_MOTOR_BIND_PASS"},
        {"id": "crown_moon_bind", "pass": moon_bind.get("verdict") == "CROWN_MOON_BIND_PASS"},
        {"id": "fpga_p8_inventory", "pass": fpga.get("verdict") == "FPGA_P8_PRE_SILICON_READY"},
        {"id": "world_engine", "pass": engine.get("verdict") == "PASS"},
        {"id": "m3_full_mapped_signoff", "pass": m3_ok},
    ]
    pre_m3_ok = all(c["pass"] for c in checks if c["id"] != "m3_full_mapped_signoff")
    if pre_m3_ok and m3_ok:
        verdict = "EXPEDITION_BATCH_PASS"
    elif pre_m3_ok:
        verdict = "EXPEDITION_BATCH_DEGRADED"
    else:
        verdict = "EXPEDITION_BATCH_FAIL"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_EXPEDITION_DEGRADED_GATE_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "honesty": {
            "waiting_m3": not m3_ok,
            "twin_visual_park": not m3_ok,
            "crown_stack": crown.get("verdict"),
            "expedition_runnable_degraded": pre_m3_ok,
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_expedition_degraded()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] in ("EXPEDITION_BATCH_PASS", "EXPEDITION_BATCH_DEGRADED") else 1)
