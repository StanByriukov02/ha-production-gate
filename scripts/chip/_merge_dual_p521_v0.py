#!/usr/bin/env python3
"""One-shot merge P5.21 dual physics subs (generate-gate + area receipts)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.21",
    "verdict": "PASS",
    "findings": [
        "clifford_gp_datapath_gate_v0.vh: default dual elaboration preserves runtime gp_synth_en mux for MMIO switch.",
        "SIM_ONLY / SYNTH_ONLY ifdef builds isolate datapaths without changing algebra contracts.",
        "iverilog sim-only + synth-only + dual regression + sandwich dual TB 9-case all PASS.",
        "Area probe uses sandwich worst-case; dual cells > sim-only and > synth-only — elaboration penalty measurable.",
        "Sim path in area probe uses STA blackbox stubs (XOR/identity) — not sim-real $sqrt; documented honesty.",
    ],
    "falsifiers": [
        "area receipt cited as PD signoff or FPGA area closure",
        "sim-only build with gp_synth_en=1 claimed synth-correct without SYNTH_ONLY define",
        "dual elaboration removed but runtime mux broken for MMIO 0x3E",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "default iverilog still dual-elaborates — area savings require compile-time define",
        "norm sim path still uses real/bf16_ops when SIM elaborated",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.21",
    "verdict": "WARN",
    "findings": [
        "P5_21_PASS: area probe dual≈855k cells vs sim≈768 vs synth≈854k (yosys stat max).",
        "Gate enforces sim_only < dual AND synth_only < dual — dual elaboration penalty proven.",
        "Area probe honesty: yosys synth stat not mapped Nangate — separate from P5.20 liberty.",
        "P5.20 structural/liberty artifacts unchanged.",
        "Receipt documents -DCLIFFORD_GP_DATAPATH_SIM_ONLY / SYNTH_ONLY build flags.",
    ],
    "falsifiers": [
        "AREA_PROBE_PASS with dual <= sim_only cells",
        "iverilog_synth_only_elab FAIL while dual TB passes",
    ],
    "receipt_gaps": [
        "no full-ALU area probe yet (sandwich slice only)",
        "mapped Nangate area not compared across elaboration modes",
    ],
    "spikes": [
        "dual vs synth_only margin tiny (~768 cells) — synth dominates sandwich",
        "sim-real geo_prod still unreadable by yosys — blackbox proxy for area sim leg",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.21", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p521 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_21_RECEIPT_v1.json"
    if p521.is_file():
        data = json.loads(p521.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p521.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
