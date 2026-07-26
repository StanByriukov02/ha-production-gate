#!/usr/bin/env python3
"""One-shot merge P5.14 dual physics subs (composer-2.5 algebra + opus iron)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.14",
    "verdict": "WARN",
    "findings": [
        "RTL microprogram matches LAW-1: norm(gp(gp(a,b),reverse(a))) — lat_a/lat_b frozen EX1→EX3.",
        "gp_synth_en muxes EX2 ab_mux and EX3 ara_mux; rev_a from held lat_a not live bus.",
        "PGA8 blade lanes align oracle + vectors — one thermometer.",
        "Dual TB (1,e1)+(e1,e2) hex match p3_smoke and sandwich_e1_e2 expected_rd.",
        "LAW-3: V_SANDWICH algebra/REFORM only — pose is 2×V_GEO_PROD.",
        "clifford_norm_v0 sim-only is honest PARK for this hop — not algebra defect.",
    ],
    "falsifiers": [
        "LC2 pose: gp chain RMSE≈0.26mm vs sandwich≈0.92m @ 45°",
        "sandwich(e1,e2) oracle -e2 after norm_synth lands",
        "near-degenerate rotor bf16 beyond dual TB cases=2",
        "motor7↔PGA8 compose bridge VERIFY",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "motor7↔PGA8 bridge VERIFY",
        "dual_tb_coverage=2 — 9-case synth path not re-proven",
        "norm_synth PARK — full synth sandwich incomplete",
        "NORM is L2 bf16 scale not rotor unit norm",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.14",
    "verdict": "WARN",
    "findings": [
        "P5_13_PASS prerequisite confirmed; EX3 ara mux added on EX2 ab mux.",
        "Operand invariant holds: lat_a/lat_b @ ex1, lat_ab @ ex2, rev_a from lat_a.",
        "gp_synth_en=1 routes output through sim-only norm ($sqrt real) — not end-to-end synth.",
        "Dual TB 2 trivial unit-blade cases — norm common-mode cannot catch norm divergence.",
        "4 geo_prod instances elaborated — ~2× dead logic, mux discards each cycle.",
        "ex2_eval dead (unused_ex2_eval) — FSM contract drift latent.",
    ],
    "falsifiers": [
        "mixed-sign multi-blade rotor dual TB",
        "f32 -0.0 vs real zero partial product drift",
        "verilator norm+reverse on dual cases",
        "comb depth lat_ab→ara_synth→norm node count",
    ],
    "receipt_gaps": [
        "honesty.dual_physics pending until this merge",
        "no verilator_parity field on P5.14 gate",
        "dual TB trivial coverage not flagged in receipt",
        "2× geo_prod area unquantified",
    ],
    "spikes": [
        "norm non-synth blocks end-to-end FPGA path",
        "sim+synth side-by-side doubles geo_prod — needs generate gating for area claims",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.14", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p514 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_14_RECEIPT_v1.json"
    if p514.is_file():
        data = json.loads(p514.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p514.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        bind = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_14_BIND_v1.json"
        if bind.is_file():
            bind_data = json.loads(bind.read_text(encoding="utf-8"))
            bind_data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
            bind_data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
            bind.write_text(json.dumps(bind_data, indent=2) + "\n", encoding="utf-8")
