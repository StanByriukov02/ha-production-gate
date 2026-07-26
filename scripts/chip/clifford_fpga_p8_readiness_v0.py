"""P8 FPGA readiness — honest inventory gate (NOT signoff, NOT bitstream claim)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_FPGA_P8_READINESS_RECEIPT_v1.json"

_RTL_CORE = _REPO / "fixtures" / "chip" / "clifford_alu_mmio_v0.v"
_MAPPED_NETLIST = _CHIP / "sta" / "clifford_sta_alu_slice_mapped_hybrid_v0.v"
_MISSION_CLOCK = _CHIP / "CHIP_CLIFFORD_MISSION_CLOCK_SIGNOFF_v1.json"
_H3 = _CHIP / "CHIP_CLIFFORD_DEVICE_RUST_H3_RECEIPT_v1.json"
_PRIMITIVES = _REPO / "fixtures" / "chip" / "sta" / "nangate45_sim_primitives_v0.v"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_fpga_p8_readiness(*, write: bool = True) -> dict[str, Any]:
    mission = _load(_MISSION_CLOCK)
    h3 = _load(_H3)

    mission_ok = mission.get("verdict") == "PASS" and mission.get("mission_clock_signoff_ok") is True
    h3_ok = h3.get("verdict") == "RUST_DEVICE_H3_PASS"
    rtl_ok = _RTL_CORE.is_file() and _RTL_CORE.stat().st_size > 1000
    mapped_ok = _MAPPED_NETLIST.is_file() and _MAPPED_NETLIST.stat().st_size > 10_000
    prim_ok = _PRIMITIVES.is_file()

    # Vendor flow artifacts — must NOT exist as PASS claims yet.
    bitstream_claim = any(
        p.is_file() and "bitstream" in p.name.lower()
        for p in (_CHIP / "fpga").glob("**/*")
        if (_CHIP / "fpga").is_dir()
    )

    blockers: list[str] = []
    if not mission_ok:
        blockers.append("mission_clock_signoff_missing")
    if not rtl_ok:
        blockers.append("rtl_core_missing")
    if not mapped_ok:
        blockers.append("mapped_netlist_missing")
    if not prim_ok:
        blockers.append("sim_primitives_missing")
    blockers.extend(
        [
            "no_vendor_synthesis_flow",
            "no_place_route_closure",
            "no_bitstream_erf_gate",
            "wns_not_closed_for_100mhz",
            "mmio_hil_timing_unverified_on_silicon",
        ]
    )

    checks = [
        {"id": "rtl_core_present", "pass": rtl_ok},
        {"id": "mapped_netlist_present", "pass": mapped_ok},
        {"id": "sim_primitives_present", "pass": prim_ok},
        {"id": "mission_clock_signoff", "pass": mission_ok},
        {"id": "h3_mmio_host_ready", "pass": h3_ok},
        {"id": "no_false_bitstream_claim", "pass": not bitstream_claim},
    ]
    pre_silicon_ok = rtl_ok and mapped_ok and prim_ok and mission_ok and h3_ok
    verdict = "FPGA_P8_PRE_SILICON_READY" if pre_silicon_ok else "FPGA_P8_NOT_READY"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_FPGA_P8_READINESS_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "blockers": blockers,
        "honesty": {
            "not_fpga_signoff": True,
            "not_bitstream_ready": True,
            "not_100mhz_timing_closed": True,
            "chip_is_carrier_clifford_is_crown": True,
            "next_vendor_steps": ["yosys/nextpnr or vendor synth", "pin constraints", "MMIO HIL on dev board", "ERF gate"],
        },
        "artifacts": {
            "rtl_core": str(_RTL_CORE.relative_to(_REPO)).replace("\\", "/"),
            "mapped_netlist": str(_MAPPED_NETLIST.relative_to(_REPO)).replace("\\", "/"),
            "mission_clock": str(_MISSION_CLOCK.relative_to(_REPO)).replace("\\", "/"),
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_fpga_p8_readiness()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "FPGA_P8_PRE_SILICON_READY" else 1)
