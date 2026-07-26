#!/usr/bin/env python3
"""One-shot merge P5.19 dual physics subs (norm ex_pipe synth)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.19",
    "verdict": "PASS",
    "findings": [
        "norm ex_pipe gp_synth_en muxes staged sim ($sqrt real + lat_acc_partial) vs clifford_norm_synth_v0.",
        "dual TB norm(2) and norm(e1) sim===synth within bf16 RNE tolerance.",
        "NORM op now synth-eligible under MMIO gp_synth_en — completes ex_pipe synth ladder.",
        "LAW-1 unchanged: norm scales all 8 blades by 1/||a||₂.",
    ],
    "falsifiers": [
        "synth ignores EX2 partial acc — φ staging contract differs from sim path",
        "f32 NR sqrt/rcp vs real $sqrt on edge magnitudes",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "norm_synth full comb @ EX3 vs sim partial staging",
        "sandwich norm still separate from norm_ex_pipe",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.19",
    "verdict": "WARN",
    "findings": [
        "P5_19_PASS: norm dual 2-case + unit TB + alu 9-case regression.",
        "norm_synth is heavy combinational (f32 widen + NR sqrt/rcp) — area/timing spike.",
        "sim branch still dual-elaborates real + synth when gp_synth_en unused.",
        "P6 _MODE_RTL should include clifford_norm_synth_v0.v for verilator parity.",
    ],
    "falsifiers": [
        "generate-gate sim paths before area claims",
        "full ALU liberty slice not yet mapped",
    ],
    "receipt_gaps": [
        "no yosys norm_ex_pipe smoke",
        "liberty timing only geo_prod slice (P5.15)",
    ],
    "spikes": [
        "norm_ex_pipe triple elaboration sim+synth+mux",
        "lat_acc_partial dead when gp_synth_en=1",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.19", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p519 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_19_RECEIPT_v1.json"
    if p519.is_file():
        data = json.loads(p519.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p519.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
