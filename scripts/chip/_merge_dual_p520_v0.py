#!/usr/bin/env python3
"""One-shot merge P5.20 dual physics subs (full ALU liberty slice)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P5.20",
    "verdict": "PASS",
    "findings": [
        "SDC ported from clifford_alu_macro_cycle_v0.sdc — MCP 4/3 EX1→EX3 and MCP 2/1 partial chains per pipe.",
        "Register-pin MCP on mapped bit-blasted nets (lat_a[i]→pipe_r[i] D pins) — not hier-pin template from RTL-only SDC.",
        "gp_synth_en=1 via clifford_sta_alu_liberty_top_v0 — times synth datapath not sim blackbox stubs.",
        "norm STA netlist uses clifford_norm_synth_v0 (not identity stub) — aligns liberty with P5.19 synth truth.",
        "Negative WNS (~-206ns) is comb-depth thermometer on sandwich+norm — NOT algebra failure, NOT timing closure.",
        "lat_acc_partial MCP groups documented but dead in mapped norm path — sim staging honesty preserved.",
    ],
    "falsifiers": [
        "P5_20_PASS promoted to FPGA signoff or timing closure claim",
        "negative WNS cited as Cayley/LAW violation",
        "structural smoke relabeled as liberty closure",
        "MCP 4/3 on lat_a→pipe_r absent while gate claims macro_cycle contract",
    ],
    "dogfood_coupled": "no",
    "spikes": [
        "triple parallel ex_pipes without latched_op case analysis — STA worst-cases all pipes",
        "sandwich path dominates WNS (2×geo_prod_synth+reverse+norm comb)",
        "norm_synth full comb @ EX3 vs sim partial staging",
    ],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P5.20",
    "verdict": "WARN",
    "findings": [
        "P5_20_PASS: yosys map 13143 cells / 1617 DFF · opensta read_liberty + report_checks + 10 MCP groups.",
        "Cell count from netlist instance parse (not yosys stdout regex) — fixes P5.15 cells=576 trust gap.",
        "Provenance: liberty_sha256, rtl file hashes, git_sha, tool versions in receipt.",
        "sta_skip≠PASS enforced · multicycle_groups_applied>0 asserted.",
        "Structural smoke runner untouched — separate receipt layer from liberty hop.",
        "P5.15 geo_prod slice manifest unchanged — two liberty thermometers coexist.",
    ],
    "falsifiers": [
        "LIBERTY_TIMING_CHECKS_OK with multicycle_groups_applied=0",
        "cells < 5000 floor with full ALU top",
        "opensta_run=false rolling to gate PASS",
    ],
    "receipt_gaps": [
        "tns_ns not parsed",
        "no mapped netlist content hash in provenance yet",
        "rd_reg WB path not MCP-scoped (default 1-cycle only)",
    ],
    "spikes": [
        "wns≈-206ns on sandwich norm path — expected deep comb",
        "yosys runtime ~22s now but may spike on RTL edits",
        "OpenSTA MCP resolution required register-pin walk — net direction==out useless post-abc",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P5.20", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p520 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P5_20_RECEIPT_v1.json"
    if p520.is_file():
        data = json.loads(p520.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p520.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
