#!/usr/bin/env python3
"""One-shot merge P5.15 dual physics subs (liberty timing hop)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.15",
    "verdict": "PASS",
    "findings": [
        "Manifest honesty lattice sound: slice_only, not_timing_signoff, structural_smoke_separate.",
        "STA top isolates geo_prod ex_pipe — correct algebra thermometer for comb depth.",
        "TCL: read_liberty → mapped netlist → link → SDC → report_checks → marker OK.",
        "Negative WNS treated as expected infrastructure outcome, not algebra failure.",
        "MCP_EX1_EX3_SETUP=4 on lat_a/lat_b→pipe_r aligns with EX pipeline budget.",
    ],
    "falsifiers": [
        "OPENSTA_LIBERTY_PASS promoted to full ALU signoff",
        "negative WNS cited as Cayley algebra error",
        "structural smoke relabeled as liberty closure",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "multicycle SDC net-pin heuristic vs RTL φ contract",
        "null-plane honesty gap carry-forward PARK",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.15",
    "verdict": "WARN",
    "findings": [
        "OpenSTA ran with authentic path report; wns_ns≈-17.22 disclosed in receipt.",
        "Mapped netlist has Nangate DFF_X1/INV_X1; lat_a/pipe_r nets survive abc.",
        "PASS means pipeline executed, not timing met — honesty fields consistent.",
        "Structural smoke runner separate — not conflated.",
        "sta_skip hole fixed: SKIP no longer counts as PASS.",
    ],
    "falsifiers": [
        "LIBERTY_TIMING_CHECKS_OK with zero analyzed paths",
        "dominant violation outside multicycle exception set",
        "cells=0 in receipt when netlist has thousands of gates",
    ],
    "receipt_gaps": [
        "tns_ns not parsed yet",
        "multicycle pin-set non-empty not asserted in receipt",
        "no content hash for liberty/netlist rerun provenance",
    ],
    "spikes": [
        "wns=-17.22 on reg2reg path outside MCP exception relief",
        "slice only — full ALU liberty PARK",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.15", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p515 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_15_RECEIPT_v1.json"
    if p515.is_file():
        data = json.loads(p515.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p515.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
