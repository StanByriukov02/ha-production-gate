#!/usr/bin/env python3
"""One-shot merge P5.17 dual physics subs (norm synth end-to-end)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.17",
    "verdict": "WARN",
    "findings": [
        "clifford_norm_synth_v0: f32 widen L2 + NR sqrt/rcp + RNE bf16 — matches sim on unit cases 0-3.",
        "sandwich gp_synth_en now muxes geo_prod EX2+EX3 AND norm — end-to-end synth chain.",
        "reverse still sim-only (grade map) — sandwich synth partial on reverse path.",
        "L2 bf16 norm not PGA rotor unit norm — LAW-5 unchanged.",
        "dual TB 9-case sim===synth with full synth path.",
    ],
    "falsifiers": [
        "norm_synth diverges on negative blade lanes",
        "reverse sim vs synth if reverse_synth lands",
        "NR sqrt/rcp on denormal/subnormal bf16",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "reverse still sim in sandwich",
        "norm_ex_pipe op path still sim",
        "NR precision not oracle-bit-exact beyond unit TB",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.17",
    "verdict": "WARN",
    "findings": [
        "P5_17_PASS: norm unit TB 4-case + sandwich dual 9-case + alu regression.",
        "f32_sqrt_synth + f32_rcp_synth synthesizable — no $sqrt in synth path.",
        "sandwich elaborates sim+synth norm + 4 geo_prod — area spike remains.",
        "P6 _MODE_RTL updated with clifford_norm_synth_v0.v.",
    ],
    "falsifiers": [
        "yosys norm_synth depth vs liberty slice",
        "verilator clifford_norm_v0 still in norm_ex_pipe",
    ],
    "receipt_gaps": [
        "norm_ex_pipe not muxed",
        "no yosys norm_synth smoke",
    ],
    "spikes": [
        "triple elaboration sandwich @ EX2/EX3/norm",
        "reverse comb in synth sandwich path",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.17", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p517 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_17_RECEIPT_v1.json"
    if p517.is_file():
        data = json.loads(p517.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p517.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
