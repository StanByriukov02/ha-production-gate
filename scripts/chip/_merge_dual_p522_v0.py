#!/usr/bin/env python3
"""Merge P5.22 dual physics subs — mega-regression + P5 promote."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.22",
    "verdict": "WARN",
    "findings": [
        "P5.22 re-runs umbrella P5 with shared ALU_SIM_CORE manifest — algebra opcode semantics unchanged.",
        "CLIFFORD_OP_SEMANTICS_LAW_V1 re-asserted in P5.22 canon; sandwich≠pose · norm=L2 preserved.",
        "P5_FAIL superseded with lineage — atlas no longer lies red/green split without metadata.",
        "P5.21 generate-gate honesty unchanged: dual elaboration default, SIM_ONLY/SYNTH_ONLY compile flags.",
        "Vector oracle 9-case still gold; promote does not widen op set.",
    ],
    "falsifiers": [
        "P5_PASS without supersedes block while prior P5_FAIL on disk",
        "pose path uses sandwich after promote",
        "sim-only build claimed synth-correct with gp_synth_en=1",
    ],
    "dogfood_coupled": "yes",
    "spikes": [
        "motor7 bridge still VERIFY — promote does not bind twin PGA8",
        "algebra_scope_honesty null plane PARK inherited",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.22",
    "verdict": "WARN",
    "findings": [
        "P5.22 mega-regression: P5.3–P5.21 sub-hop receipts + fresh P4/P5/P6 sim.",
        "RTL manifest fixes MODMISSING from stale 9-file P4 gate.",
        "P6 prerequisite tightened: P5.21/P5.22/P5_PASS accepted.",
        "P5.20 liberty WNS~-206ns unchanged — not timing closure.",
        "cxx sandwich/norm still PARK; recovery hooks still monitor-only.",
    ],
    "falsifiers": [
        "P5_22_PASS with p4_verilator FAIL",
        "P5_PASS without verilator on full manifest",
        "P6_PASS with stale p5_prerequisite only P5_12",
    ],
    "receipt_gaps": [
        "full-ALU mapped area compare still open",
        "verilator not in P5.21 gate — covered here in P5.22",
        "MLIR/CIRCT rail still zero",
    ],
    "spikes": [
        "timing not signoff",
        "manifest drift if p5_21 duplicates _ALU_CORE without import",
        "dual vs synth_only area margin tiny",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.22", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p522 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_22_RECEIPT_v1.json"
    if p522.is_file():
        data = json.loads(p522.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p522.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
