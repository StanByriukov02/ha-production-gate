#!/usr/bin/env python3
"""One-shot merge P5.13 dual physics subs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.13",
    "verdict": "WARN",
    "findings": [
        "Operand invariant holds: lat_a/lat_b frozen @ ex1; lat_ab captures muxed geo_prod @ ex2 only.",
        "ab_mux = gp_synth_en ? synth : sim on same Cayley basis — algebra thermometer unchanged.",
        "sandwich = V_SANDWICH not rigid pose — TABU respected; EX3 ara/norm still sim-real.",
        "Partial synth path: first geo_prod synth, second geo_prod + norm sim — compose semantics gap named.",
        "Dual TB single e1^2 case — degenerate/near-null falsifiers not exercised.",
    ],
    "falsifiers": [
        "synth vs sim lat_ab divergence on non-unit rotors",
        "toggle gp_synth_en between ex1 and ex2",
        "sandwich vs pose on LC2 rigid frame",
        "PGA null-plane norm vs Euclidean norm @ EX3",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "motor7-PGA8 bridge VERIFY",
        "EX3 sim chain after synth lat_ab",
        "dual TB vector coverage thin",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.13",
    "verdict": "WARN",
    "findings": [
        "P5_13_PASS receipt matches scoped checks; both u_ab_sim and u_ab_synth elaborated.",
        "gp_synth_en wired top→sandwich; geo_prod ex_pipe unchanged — MMIO 0x3E still gp-only.",
        "Dual TB PASS (one vector); unit + alu 9-case regression green.",
        "EX3 u_ara/u_norm sim — STA/yosys sandwich path still mixed synth+sim.",
        "ex2_eval tied off unused — same as P5.11 ex_pipes.",
    ],
    "falsifiers": [
        "expand sandwich dual TB to full 9-case oracle parity",
        "OpenSTA sandwich lat_ab partial with liberty",
        "verilator norm real lat_acc_partial",
        "area/power of dual geo_prod @ EX2",
    ],
    "receipt_gaps": [
        "honesty.dual_physics was pending until subs merged",
        "EX3 synth ara/norm out of scope",
        "no yosys sandwich-ex2-only smoke in P5.13 gate",
    ],
    "spikes": [
        "EX3 sim geo_prod after synth lat_ab",
        "dual elaboration area @ EX2",
        "dual TB single vector",
        "norm STA stub unchanged",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.13", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    # Patch P5.13 gate receipt dual_physics field
    p513 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_13_RECEIPT_v1.json"
    if p513.is_file():
        data = json.loads(p513.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p513.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        bind = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_13_BIND_v1.json"
        if bind.is_file():
            bind_data = json.loads(bind.read_text(encoding="utf-8"))
            bind_data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
            bind_data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
            bind.write_text(json.dumps(bind_data, indent=2) + "\n", encoding="utf-8")
