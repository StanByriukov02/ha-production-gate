"""MMIO HIL host gate — Verilator session vs oracle (dev-board prep, sim HIL)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_MMIO_HIL_HOST_GATE_RECEIPT_v1.json"
_MMIO_MAP = _REPO / "docs/agent_workflow/CLIFFORD_CARRIER_DEV_BOARD_MMIO_MAP_V0.md"


def _oracle_verilator_unary(op: str, hx: str) -> tuple[str, str, bool]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8

    padded = hx.zfill(32)
    os.environ.pop("CLIFFORD_BACKEND", None)
    m = MotorPGA8.from_hex(padded)
    if op == "reverse":
        exp = m.reverse().hex()
    elif op == "norm":
        exp = m.norm().hex()
    else:
        raise ValueError(op)
    os.environ["CLIFFORD_BACKEND"] = "verilator"
    got = MotorPGA8.from_hex(padded)
    if op == "reverse":
        got_hex = got.reverse().hex()
    else:
        got_hex = got.norm().hex()
    return exp, got_hex, exp == got_hex


def _oracle_verilator_binary(op: str, a: str, b: str) -> tuple[str, str, bool]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8

    pa, pb = a.zfill(32), b.zfill(32)
    os.environ.pop("CLIFFORD_BACKEND", None)
    ma, mb = MotorPGA8.from_hex(pa), MotorPGA8.from_hex(pb)
    if op == "geo_prod":
        exp = ma.geo_prod(mb).hex()
    elif op == "sandwich":
        exp = ma.sandwich(mb).hex()
    else:
        raise ValueError(op)
    os.environ["CLIFFORD_BACKEND"] = "verilator"
    got_ma, got_mb = MotorPGA8.from_hex(pa), MotorPGA8.from_hex(pb)
    if op == "geo_prod":
        got_hex = got_ma.geo_prod(got_mb).hex()
    else:
        got_hex = got_ma.sandwich(got_mb).hex()
    return exp, got_hex, exp == got_hex


def evaluate_mmio_hil_host_gate(*, write: bool = True) -> dict[str, Any]:
    from scripts.chip.clifford_verilator_mmio_build_v0 import verilator_mmio_exe

    built = verilator_mmio_exe() is not None
    cases = [
        ("reverse", "0000000000000000000000003f800000", None),
        ("norm", "000000000000000000003f8000000000", None),
        (
            "geo_prod",
            "0000000000000000000000003f800000",
            "000000000000000000003f8000000000",
        ),
        (
            "sandwich",
            "3f80000000000000000000003f800000",
            "0000000000000000000000003f800000",
        ),
    ]
    rows: list[dict[str, Any]] = []
    all_ok = built
    for case in cases:
        op, a, b = case
        if b is None:
            exp, got, ok = _oracle_verilator_unary(op, a)
            rows.append({"op": op, "a": a.zfill(32), "oracle": exp, "verilator": got, "pass": ok})
        else:
            exp, got, ok = _oracle_verilator_binary(op, a, b)
            rows.append(
                {
                    "op": op,
                    "a": a.zfill(32),
                    "b": b.zfill(32),
                    "oracle": exp,
                    "verilator": got,
                    "pass": ok,
                }
            )
        all_ok = all_ok and ok

    core_ops = {"reverse", "geo_prod"}
    core_ok = all(r["pass"] for r in rows if r["op"] in core_ops)
    ext_ok = all(r["pass"] for r in rows if r["op"] not in core_ops)
    all_ops_ok = all(r["pass"] for r in rows)

    checks = [
        {"id": "verilator_mmio_built", "pass": built},
        {"id": "mmio_map_doc", "pass": _MMIO_MAP.is_file()},
        {"id": "hil_core_ops", "pass": core_ok, "detail": "reverse+geo_prod"},
        {"id": "hil_extended_ops", "pass": ext_ok, "detail": "norm+sandwich"},
        {"id": "hil_all_ops", "pass": all_ops_ok, "detail": "reverse+geo_prod+norm+sandwich"},
    ]
    verdict = "MMIO_HIL_HOST_GATE_PASS" if built and all_ops_ok else "MMIO_HIL_HOST_GATE_FAIL"
    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_MMIO_HIL_HOST_GATE_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "cases": rows,
        "host_binary": "results/platform_bpass/chip/verilator/clifford_mmio_session/Vclifford_alu_mmio_v0",
        "mmio_map": str(_MMIO_MAP.relative_to(_REPO)).replace("\\", "/"),
        "honesty": {
            "sim_hil_only": True,
            "not_dev_board_measured": True,
            "chip_is_carrier": True,
            "clifford_alu_is_crown": True,
            "norm_sandwich_open": not ext_ok,
        },
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_mmio_hil_host_gate()
    print(json.dumps({k: v for k, v in out.items() if k != "cases"}, indent=2))
    raise SystemExit(0 if out["verdict"] == "MMIO_HIL_HOST_GATE_PASS" else 1)
