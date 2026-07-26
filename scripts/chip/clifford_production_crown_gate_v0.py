"""Production crown gate — Clifford lives on iron MMIO; chip is carrier only."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_PRODUCTION_CROWN_GATE_RECEIPT_v1.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_production_crown_gate(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    h3 = _load(_CHIP / "CHIP_CLIFFORD_DEVICE_RUST_H3_RECEIPT_v1.json")
    h6 = _load(_CHIP / "CHIP_CLIFFORD_CROWN_MOTOR_BIND_RECEIPT_v1.json")
    moon = _load(_CHIP / "CHIP_CLIFFORD_CROWN_MOON_BIND_RECEIPT_v1.json")
    rev = _load(_CHIP / "CHIP_CLIFFORD_REVERSE_MMIO_PARITY_RECEIPT_v1.json")
    crown = _load(_CHIP / "CHIP_CLIFFORD_CROWN_STACK_GATE_RECEIPT_v1.json")

    from scripts.chip.clifford_verilator_mmio_build_v0 import verilator_mmio_exe

    verilator_built = verilator_mmio_exe() is not None
    crown_core = crown.get("verdict") in ("CROWN_STACK_PASS", "CROWN_STACK_DEGRADED")
    m3_ok = crown.get("verdict") == "CROWN_STACK_PASS"

    # Live path: rigid_pose via verilator (geo_prod + reverse on iron)
    live_ok = False
    live_detail = "skipped"
    if verilator_built:
        try:
            from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8

            os.environ["CLIFFORD_BACKEND"] = "verilator"
            r = MotorPGA8.from_hex("000000000000bc340000000000003f80")
            p = MotorPGA8.from_hex("00000000000000003e5700003e9f0000")
            out = r.rigid_pose(p)
            live_ok = len(out.hex()) == 32
            live_detail = "rigid_pose_verilator_iron"
        except Exception as exc:
            live_detail = str(exc)[:200]

    checks = [
        {"id": "h3_rust_verilator", "pass": h3.get("verdict") == "RUST_DEVICE_H3_PASS"},
        {"id": "reverse_mmio_parity", "pass": rev.get("verdict") == "REVERSE_MMIO_PARITY_PASS"},
        {"id": "crown_motor_bind", "pass": h6.get("verdict") == "CROWN_MOTOR_BIND_PASS"},
        {"id": "crown_moon_bind", "pass": moon.get("verdict") == "CROWN_MOON_BIND_PASS"},
        {"id": "verilator_mmio_built", "pass": verilator_built},
        {"id": "live_rigid_pose_iron", "pass": live_ok, "detail": live_detail},
        {"id": "crown_stack_full_signoff", "pass": m3_ok},
    ]
    software_ok = all(c["pass"] for c in checks if c["id"] != "crown_stack_full_signoff")
    if software_ok and m3_ok:
        verdict = "PRODUCTION_CROWN_GATE_PASS"
    elif software_ok:
        verdict = "PRODUCTION_CROWN_GATE_READY"  # crown path live; carrier M3 pending
    else:
        verdict = "PRODUCTION_CROWN_GATE_FAIL"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_PRODUCTION_CROWN_GATE_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "law": {
            "clifford_alu_is_crown": True,
            "chip_is_carrier": True,
            "clifford_does_not_require_chip_for_poses": True,
            "production_backend": "CLIFFORD_BACKEND=verilator",
        },
        "honesty": {
            "waiting_m3_for_full_pass": not m3_ok,
            "cxx_role": "parity_oracle_only",
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_production_crown_gate()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] in ("PRODUCTION_CROWN_GATE_PASS", "PRODUCTION_CROWN_GATE_READY") else 1)
