#!/usr/bin/env python3
"""Merge T2_CLOSURE dual physics after T2.10 gp1 blade split."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "T2_CLOSURE",
    "verdict": "PASS",
    "findings": [
        "gp1 split into low/high blades @ ex2_eval/ex2_latch — same algebra as geo_prod_ex_pipe pattern.",
        "Cumulative WNS ladder: therm −207 → T2.8 −179 → T2.10 −167 ns.",
        "T2.14 gp2 blades + norm @ wb_eval: Δ+2.9 ns · best −164 ns (partial · gate floor +10 not met).",
        "iverilog 9-case sim===synth PASS after φ pulse TB update.",
    ],
    "falsifiers": [
        "dual TB diverges after blade split",
        "timing_closure claimed",
        "gp2 blade split @ ex3",
        "norm acc_low on ara_mux @ ex3_eval",
        "norm comb wb_eval slip without pipeline retime",
    ],
    "dogfood_coupled": "yes",
    "spikes": [
        "binding tail u_norm_synth — −164 ns best (T2.14 partial)",
        "macro-cycle slip norm to wb_eval needs contract change",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "T2_CLOSURE",
    "verdict": "WARN",
    "findings": [
        "STA_T2_SANDWICH_EX2_STAGED_PASS · delta +12.5 ns vs T2.8 · +40.5 ns vs thermometer.",
        "SDC lat_ab_low/lat_ab_high MCP live · yosys 16180 cells.",
        "closure still OPEN at −167 ns.",
    ],
    "falsifiers": [
        "wns_delta < 10 ns on gp1 blade split",
        "opensta MCP parse error on sandwich regs",
    ],
    "receipt_gaps": ["gp2 blade split not yet receipted"],
    "spikes": ["required period still ~177 ns"],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="T2_CLOSURE", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))
