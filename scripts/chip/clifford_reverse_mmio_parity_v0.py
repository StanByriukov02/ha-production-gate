"""Reverse MMIO parity — oracle vs Verilator iron crown."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_REVERSE_MMIO_PARITY_RECEIPT_v1.json"

_CASES = (
    "0000000000000000000000003f800000",
    "000000000000000000003f8000000000",
    "3f80000000000000000000003f800000",
    "00000000000000000000000000003f80",
    "00000000000000000000bf8000000000",
)


def evaluate_reverse_mmio_parity(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8
    from scripts.chip.clifford_verilator_mmio_build_v0 import verilator_mmio_exe

    built = verilator_mmio_exe(force_rebuild=True) is not None
    rows: list[dict[str, Any]] = []
    parity_ok = built
    for hx in _CASES:
        padded = hx.zfill(32)
        os.environ.pop("CLIFFORD_BACKEND", None)
        exp = MotorPGA8.from_hex(padded).reverse().hex()
        os.environ["CLIFFORD_BACKEND"] = "verilator"
        got = MotorPGA8.from_hex(padded).reverse().hex()
        ok = exp == got
        parity_ok = parity_ok and ok
        rows.append({"in_hex": padded, "oracle_hex": exp, "verilator_hex": got, "pass": ok})

    checks = [
        {"id": "verilator_mmio_built", "pass": built},
        {"id": "reverse_oracle_vs_verilator", "pass": parity_ok},
    ]
    verdict = "REVERSE_MMIO_PARITY_PASS" if parity_ok else "REVERSE_MMIO_PARITY_FAIL"
    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_REVERSE_MMIO_PARITY_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "cases": rows,
        "honesty": {
            "opcode": "CLIFFORD_OP_V_REVERSE 3'b101",
            "rigid_pose_next": "wire reverse in MotorPGA8.rigid_pose via verilator",
        },
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_reverse_mmio_parity()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "REVERSE_MMIO_PARITY_PASS" else 1)
