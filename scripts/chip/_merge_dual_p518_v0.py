#!/usr/bin/env python3
"""One-shot merge P5.18 dual physics subs (reverse synth)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.18",
    "verdict": "PASS",
    "findings": [
        "clifford_reverse_synth_v0 implements REV_SIGN grade map: blades 0-3 pass, 4-7 bf16_negate.",
        "Matches oracle reverse_coeffs sign pattern for Cl(3,0) spatial grades.",
        "sandwich gp_synth_en muxes reverse — full sandwich microprogram synth under one flag.",
        "dual TB 9-case sim===synth with complete synth chain.",
        "LAW-1 microprogram unchanged: norm(gp(gp(a,b),reverse(a))).",
    ],
    "falsifiers": [
        "bf16_negate vs real_to_bf16(-x) on subnormal blades",
        "sandwich vs pose LC2 falsifier unchanged",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "norm_ex_pipe NORM op still sim",
        "bf16 sign-flip edge vs real negate",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.18",
    "verdict": "WARN",
    "findings": [
        "P5_18_PASS: reverse unit 5-case + sandwich dual 9-case + alu regression.",
        "reverse_synth is pure combinational bf16 — yosys-friendly.",
        "sandwich still dual-elaborates sim+synth paths — area spike.",
        "P6 _MODE_RTL includes clifford_reverse_synth_v0.v.",
    ],
    "falsifiers": [
        "generate-gate sim paths before area claims",
        "verilator norm_ex_pipe still real",
    ],
    "receipt_gaps": [
        "norm_ex_pipe synth not in scope",
        "no yosys sandwich full-chain smoke",
    ],
    "spikes": [
        "5-path dual elaboration sandwich when gp_synth_en unused",
        "reverse grade map assumes bf16_negate = real negate for smoke",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.18", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p518 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_18_RECEIPT_v1.json"
    if p518.is_file():
        data = json.loads(p518.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p518.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
