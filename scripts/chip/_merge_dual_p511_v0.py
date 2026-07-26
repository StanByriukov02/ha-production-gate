#!/usr/bin/env python3
"""One-shot merge P5.11 dual physics subs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.11",
    "verdict": "WARN",
    "findings": [
        "Operand invariant enforced: lat_a/lat_b @ ex1_latch only; blades read frozen regs through ex3.",
        "geo_prod EX2 staging sound: lat_low @ex2, high comb @ex3, {comb_high_mux, lat_low}.",
        "sandwich = V_SANDWICH not rigid pose — TABU respected.",
        "norm Euclidean vs PGA R3,0,1* null-plane gap unnamed in P5.11 receipt.",
        "STA norm XOR stub — structural smoke only.",
    ],
    "falsifiers": [
        "non-unit rotor sandwich vs pose",
        "PGA e0 norm divergence",
        "bf16 mag->0 inv_mag",
        "toggle a/b between ex1 and ex3",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "motor7-PGA8 bridge VERIFY",
        "norm metric honesty gap",
        "dual TB Cayley not co-located",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.11",
    "verdict": "WARN",
    "findings": [
        "EX2 synth bypass fixed; high blades comb @ ex3 (lat_high landed P5.12 after review).",
        "P5_11_PASS receipt matches scoped checks; timing structural-only.",
        "SDC EX2 partial present; sandwich sim geo_prod at EX2.",
        "OpenSTA shell blackbox — not timing closure.",
    ],
    "falsifiers": [
        "dual TB single e1^2 case only",
        "OpenSTA with liberty WNS",
        "sandwich synth divergence",
        "norm verilator parity",
    ],
    "receipt_gaps": [
        "scope omits lat_high timing at review time",
        "SDC pin linkage partial in OpenSTA shell",
        "dual_physics was pending until subs merged",
    ],
    "spikes": [
        "high blades comb @ ex3",
        "ex2_eval unused in ex_pipes",
        "OpenSTA W363/W471 on shell",
        "sandwich sim geo_prod",
        "norm STA stub",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.11", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))
