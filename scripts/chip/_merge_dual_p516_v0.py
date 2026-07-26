#!/usr/bin/env python3
"""One-shot merge P5.16 dual physics subs (9-case sandwich dual TB)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.16",
    "verdict": "WARN",
    "findings": [
        "9-case rs1/rs2 matrix byte-matches clifford_alu_tb_v0 — expansion honest.",
        "Dual TB asserts r_sim===r_synth only — no oracle rd cross-check.",
        "7/9 rows are geo_prod/norm fixtures through sandwich pipe — stress matrix.",
        "Sandwich cases 5/8 oracle enforced in alu_tb regression, not dual TB.",
        "honesty.oracle_rd_not_checked documented in gate.",
    ],
    "falsifiers": [
        "dual PASS while both sim and synth wrong identically",
        "P5_16 promoted without alu_9case regression",
        "bf16 tie divergence geo_prod vs synth on cases 0-4 inside sandwich",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "equivalence-only thermometer",
        "matrix borrows non-sandwich operands",
        "norm single path — partial dual surface",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.16",
    "verdict": "WARN",
    "findings": [
        "Gate fail-closed: SKIPPED iverilog -> FAIL.",
        "N_CASES=9 verified vs alu_tb operands.",
        "Pass tokens aligned: cases=9 dual + alu regression.",
        "gp_synth_en toggles geo_prod only; reverse/norm shared.",
        "pytest executed 9-case dual PASS on host.",
    ],
    "falsifiers": [
        "shared wrong geo_prod passes dual",
        "inline vectors drift from canon JSON",
    ],
    "receipt_gaps": [
        "dual_physics pending until merge",
        "no programmatic bind to vectors JSON",
    ],
    "spikes": [
        "equivalence not correctness alone",
        "norm path not muxed in dual",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.16", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p516 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_16_RECEIPT_v1.json"
    if p516.is_file():
        data = json.loads(p516.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p516.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
