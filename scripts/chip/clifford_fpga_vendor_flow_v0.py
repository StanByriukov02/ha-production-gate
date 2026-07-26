"""FPGA vendor flow — constraints stub + flow manifest (not P&R signoff)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FPGA = _CHIP / "fpga"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_FPGA_VENDOR_FLOW_RECEIPT_v1.json"
_YOSYS_OUT = _FPGA / "clifford_fpga_yosys_elab_v0.v"
_LPF = _FPGA / "clifford_carrier_bringup_v0.lpf"
_XDC = _FPGA / "clifford_carrier_bringup_v0.xdc"
_PINMAP = _REPO / "fixtures" / "chip" / "clifford_carrier_ulx3s_pinmap_v0.json"


def _load_pinmap() -> dict[str, Any]:
    if not _PINMAP.is_file():
        return {}
    return json.loads(_PINMAP.read_text(encoding="utf-8"))


def _write_constraints() -> None:
    _FPGA.mkdir(parents=True, exist_ok=True)
    pinmap = _load_pinmap()
    clk_site = pinmap.get("clock_source", {}).get("site", "A10")
    rst_site = pinmap.get("reset", {}).get("site", "R1")
    bridge = pinmap.get("mmio_host_bridge", {})

    locate_lines: list[str] = [
        f'LOCATE COMP "clk" SITE "{clk_site}" ;',
        f'LOCATE COMP "rst" SITE "{rst_site}" ;',
    ]
    for _key, spec in bridge.items():
        if _key == "note" or not isinstance(spec, dict):
            continue
        port = spec.get("port")
        site = spec.get("site")
        if port and site:
            locate_lines.append(f'LOCATE COMP "{port}" SITE "{site}" ;')

    lpf = f"""# Clifford carrier bring-up v0 — ULX3S ECP5 sketch (NOT signoff)
# Mission clock: 27.5 MHz study anchor (36.36 ns)
# Pin source: fixtures/chip/clifford_carrier_ulx3s_pinmap_v0.json
FREQUENCY PORT "clk" 27.5 MHz;

{chr(10).join(locate_lines)}
"""
    xdc_lines = [
        "# Clifford carrier bring-up v0 — Xilinx-style sketch (NOT signoff)",
        "# Study anchor 27.5 MHz — do NOT constrain at 100 MHz",
        'create_clock -period 36.364 [get_ports clk]',
        f'set_property PACKAGE_PIN {clk_site} [get_ports clk]',
        f'set_property PACKAGE_PIN {rst_site} [get_ports rst]',
    ]
    for _key, spec in bridge.items():
        if _key == "note" or not isinstance(spec, dict):
            continue
        port = spec.get("port")
        site = spec.get("site")
        if port and site:
            xdc_lines.append(f'set_property PACKAGE_PIN {site} [get_ports {{{port}}}]')
    xdc = "\n".join(xdc_lines) + "\n"
    _LPF.write_text(lpf, encoding="utf-8")
    _XDC.write_text(xdc, encoding="utf-8")


def evaluate_fpga_vendor_flow(*, write: bool = True) -> dict[str, Any]:
    _write_constraints()
    yosys_ok = _YOSYS_OUT.is_file() and _YOSYS_OUT.stat().st_size > 1000
    checks = [
        {"id": "yosys_netlist_present", "pass": yosys_ok},
        {"id": "lpf_stub", "pass": _LPF.is_file()},
        {"id": "xdc_stub", "pass": _XDC.is_file()},
        {"id": "pinmap_json", "pass": _PINMAP.is_file()},
    ]
    verdict = "FPGA_VENDOR_FLOW_STUB_READY" if all(c["pass"] for c in checks) else "FPGA_VENDOR_FLOW_STUB_FAIL"
    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_FPGA_VENDOR_FLOW_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "artifacts": {
            "yosys_netlist": str(_YOSYS_OUT.relative_to(_REPO)).replace("\\", "/"),
            "constraints_lpf": str(_LPF.relative_to(_REPO)).replace("\\", "/"),
            "constraints_xdc": str(_XDC.relative_to(_REPO)).replace("\\", "/"),
            "pinmap": str(_PINMAP.relative_to(_REPO)).replace("\\", "/"),
            "mmio_map": "docs/agent_workflow/CLIFFORD_CARRIER_DEV_BOARD_MMIO_MAP_V0.md",
        },
        "vendor_next_steps": [
            "nextpnr-ecp5 or Vivado synth on yosys netlist",
            "complete reg_wdata/rdata bus LOC from pinmap",
            "MMIO HIL on UART/JTAG bridge",
            "ERF gate before bitstream claim",
        ],
        "honesty": {
            "not_place_route": True,
            "not_bitstream": True,
            "mission_clock_mhz": 27.5,
        },
    }
    if write:
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_fpga_vendor_flow()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "FPGA_VENDOR_FLOW_STUB_READY" else 1)
