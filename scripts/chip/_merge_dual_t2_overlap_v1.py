#!/usr/bin/env python3
"""Merge T2_OVERLAP dual physics subs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "T2_OVERLAP",
    "verdict": "PASS",
    "findings": [
        "Overlap = A5 throughput (1 motor / 2φ steady) — scheduler sim only.",
        "clifford_alu_top_v0 unpipelined φ FSM — zero overlap in datapath.",
        "STA WNS independent — overlap_does_not_cut_comb_depth documented.",
        "PHI_OVERLAP_THROUGHPUT_HONESTY_PASS — modeled 4× us/compose vs unpipelined.",
    ],
    "falsifiers": [
        "overlap claimed to close sandwich WNS",
        "alu_top instantiates overlap scheduler",
        "steady retire cadence ≠ 1/2φ",
    ],
    "dogfood_coupled": "partial",
    "spikes": [
        "iron_modeled_overlap is scheduler arithmetic not wall-clock GP cloud",
        "future alu_top wire needs scoreboard against WAW",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "T2_OVERLAP",
    "verdict": "PASS",
    "findings": [
        "PHI_OVERLAP_T2_5_PASS + PHI_OVERLAP_THROUGHPUT_HONESTY_PASS receipts.",
        "Verilator steady 1 retire / 2φ · overlap absent from STA netlist.",
        "Benchmark iron_modeled 0.08 vs 0.02 us/compose — honesty labeled modeled.",
    ],
    "falsifiers": [
        "throughput_honesty gate FAIL",
        "overlap_en in alu_top RTL",
    ],
    "receipt_gaps": [
        "no measured full GP cloud concurrent macro bench",
    ],
    "spikes": [
        "slot_phi unused in scheduler — cadence only",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="T2_OVERLAP", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))
