"""Audit mapped netlist cell types vs nangate45_sim_primitives_v0.v — iron gate."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PRIM = _REPO / "fixtures" / "chip" / "sta" / "nangate45_sim_primitives_v0.v"
_NETLISTS = (
    _REPO / "results" / "platform_bpass" / "chip" / "sta" / "clifford_sta_geo_prod_slice_mapped_v0.v",
    _REPO / "results" / "platform_bpass" / "chip" / "sta" / "clifford_sta_alu_slice_mapped_v0.v",
)
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_NANGATE45_SIM_PRIMITIVES_AUDIT_v1.json"


def _primitive_modules(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"^\s*module\s+(\w+)\b", text, flags=re.MULTILINE))


def _netlist_cell_types(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"\b([A-Z][A-Z0-9_]*_X\d+)\b", text))


def audit(*, write: bool = True) -> dict:
    if not _PRIM.is_file():
        return {"verdict": "FAIL", "reason": "primitives_missing"}
    prim = _primitive_modules(_PRIM)
    missing_by_netlist: dict[str, list[str]] = {}
    for netlist in _NETLISTS:
        if not netlist.is_file():
            missing_by_netlist[netlist.name] = ["NETLIST_MISSING"]
            continue
        cells = _netlist_cell_types(netlist)
        missing = sorted(c for c in cells if c not in prim)
        if missing:
            missing_by_netlist[netlist.name] = missing
    verdict = "PASS" if not missing_by_netlist else "FAIL"
    doc = {
        "receipt_id": "CHIP_CLIFFORD_NANGATE45_SIM_PRIMITIVES_AUDIT_v1",
        "verdict": verdict,
        "primitives": str(_PRIM.relative_to(_REPO)).replace("\\", "/"),
        "primitive_count": len(prim),
        "missing_by_netlist": missing_by_netlist,
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = audit()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 1)
