"""Crown stack gate — H1 mapped ALU + H2 mission clock + H3 Rust verilator iron."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_CROWN_STACK_GATE_RECEIPT_v1.json"

_H2 = _CHIP / "CHIP_CLIFFORD_MISSION_CLOCK_SIGNOFF_v1.json"
_H3 = _CHIP / "CHIP_CLIFFORD_DEVICE_RUST_H3_RECEIPT_v1.json"
_H1 = _CHIP / "CHIP_CLIFFORD_H1_MAPPED_ALU_PARITY_RECEIPT_v1.json"
_SLICE = _CHIP / "CHIP_CLIFFORD_WORLD_MOTION_MAPPED_MMIO_RECEIPT_v1.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_crown_stack(*, write: bool = True) -> dict[str, Any]:
    h2 = _load(_H2)
    h3 = _load(_H3)
    h1 = _load(_H1)
    slc = _load(_SLICE)

    h2_ok = h2.get("verdict") == "PASS" and h2.get("mission_clock_signoff_ok") is True
    h3_ok = h3.get("verdict") == "RUST_DEVICE_H3_PASS"
    slice_ok = (slc.get("mapped_netlist_slice") or {}).get("functional_parity_ok") is True

    steps = h1.get("steps") or {}
    h1_m2_ok = (steps.get("M2") or {}).get("alu_parity_ok") is True
    h1_m3_ok = (steps.get("M3") or {}).get("alu_parity_ok") is True
    h1_hybrid_ok = h1_m2_ok and all(
        (steps.get(s) or {}).get("verdict") in ("PASS", "SMOKE") for s in ("M0", "M1", "M2") if s in steps
    )

    checks = [
        {"id": "h2_mission_clock", "pass": h2_ok},
        {"id": "h3_rust_verilator_crown", "pass": h3_ok},
        {"id": "mapped_slice_functional", "pass": slice_ok},
        {"id": "h1_hybrid_alu_m0_m2", "pass": h1_hybrid_ok},
        {"id": "h1_full_mapped_m3_signoff", "pass": h1_m3_ok},
    ]
    core_ok = h2_ok and h3_ok and slice_ok and h1_hybrid_ok
    if core_ok and h1_m3_ok:
        verdict = "CROWN_STACK_PASS"
    elif core_ok:
        verdict = "CROWN_STACK_DEGRADED"
    else:
        verdict = "CROWN_STACK_FAIL"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_CROWN_STACK_GATE_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "honesty": {
            "clifford_alu_is_crown": True,
            "chip_is_carrier": True,
            "h1_hybrid_funcsim_interim": h1_hybrid_ok and not h1_m3_ok,
            "not_full_alu_mapped_mmio": not h1_m3_ok,
            "twin_visual_park_until_m3": not h1_m3_ok,
        },
        "sources": {
            "h2": str(_H2.relative_to(_REPO)).replace("\\", "/"),
            "h3": str(_H3.relative_to(_REPO)).replace("\\", "/"),
            "h1_ladder": str(_H1.relative_to(_REPO)).replace("\\", "/"),
            "mapped_slice": str(_SLICE.relative_to(_REPO)).replace("\\", "/"),
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_crown_stack()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] in ("CROWN_STACK_PASS", "CROWN_STACK_DEGRADED") else 1)
