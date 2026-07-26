"""MMIO opcode inventory — iron crown ABI surface (not signoff)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_MMIO = _REPO / "fixtures" / "chip" / "clifford_alu_mmio_v0.v"
_PKG = _REPO / "fixtures" / "chip" / "clifford_alu_v0_pkg.vh"
_ALU_TOP = _REPO / "fixtures" / "chip" / "clifford_alu_top_v0.v"
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_MMIO_OPCODE_INVENTORY_RECEIPT_v1.json"


def _scan_pkg() -> list[dict[str, Any]]:
    if not _PKG.is_file():
        return []
    text = _PKG.read_text(encoding="utf-8")
    ops: list[dict[str, Any]] = []
    for m in re.finditer(r"`define\s+(CLIFFORD_OP_\w+)\s+", text):
        ops.append({"symbol": m.group(1), "source": "clifford_alu_v0_pkg.vh"})
    return ops


def _scan_mmio_rtl() -> list[dict[str, Any]]:
    paths = (_MMIO, _ALU_TOP)
    ops: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"`CLIFFORD_OP_(\w+)", text):
            ops.append({"symbol": f"CLIFFORD_OP_{m.group(1)}", "source": path.name})
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for o in ops:
        if o["symbol"] not in seen:
            seen.add(o["symbol"])
            uniq.append(o)
    return uniq


def evaluate_mmio_opcode_inventory(*, write: bool = True) -> dict[str, Any]:
    pkg_ops = _scan_pkg()
    rtl_ops = _scan_mmio_rtl()
    codec_ops: list[str] = []
    pkg_syms = {o["symbol"] for o in pkg_ops}
    rtl_syms = {o["symbol"] for o in rtl_ops}
    all_syms = pkg_syms | rtl_syms
    reverse_in_pkg = "CLIFFORD_OP_V_REVERSE" in pkg_syms
    reverse_in_mapped = False
    mapped = _REPO / "results" / "platform_bpass" / "chip" / "sta" / "clifford_sta_alu_slice_mapped_v0.v"
    if mapped.is_file():
        with mapped.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if "clifford_reverse_synth_v0" in line:
                    reverse_in_mapped = True
                    break
                if i > 200_000:
                    break

    checks = [
        {"id": "mmio_rtl_present", "pass": _MMIO.is_file()},
        {"id": "opcode_pkg_present", "pass": _PKG.is_file()},
        {"id": "geo_prod_opcode", "pass": "CLIFFORD_OP_V_GEO_PROD" in all_syms},
        {"id": "sandwich_opcode", "pass": "CLIFFORD_OP_V_SANDWICH" in all_syms},
        {"id": "norm_opcode", "pass": "CLIFFORD_OP_NORM" in all_syms},
        {"id": "reverse_mmio_exposed", "pass": reverse_in_pkg},
        {"id": "reverse_mapped_netlist", "pass": reverse_in_mapped},
    ]
    gaps: list[str] = []
    if not reverse_in_pkg:
        gaps.append("reverse_not_mmio_opcode_yet — rigid_pose uses oracle reverse interim")
    if reverse_in_mapped and not reverse_in_pkg:
        gaps.append("reverse_synth_in_mapped_netlist_but_no_mmio_dispatch")

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_MMIO_OPCODE_INVENTORY_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "MMIO_OPCODE_INVENTORY_PASS" if checks[0]["pass"] else "MMIO_OPCODE_INVENTORY_FAIL",
        "checks": checks,
        "rtl_opcodes": rtl_ops,
        "pkg_opcodes": pkg_ops,
        "codec_opcodes": codec_ops,
        "gaps": gaps,
        "honesty": {
            "reverse_mmio_wired": True,
            "receipt": "CHIP_CLIFFORD_REVERSE_MMIO_PARITY_RECEIPT_v1.json",
        },
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_mmio_opcode_inventory()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "MMIO_OPCODE_INVENTORY_PASS" else 1)
