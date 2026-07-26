#!/usr/bin/env python3
"""Merge P6.4 dual physics — cxx sandwich/norm oracle parity."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P6.4",
    "verdict": "WARN",
    "findings": [
        "sandwich = norm(gp(gp(a,b),reverse(a))) implemented in cxx — distinct from rigid_pose (no trailing norm).",
        "norm = L2 over all 8 bf16 blades with true sqrt — matches oracle LAW-5.",
        "9-case vector parity: 5 geo_prod + 2 sandwich + 2 norm — opcode dispatch per vectors JSON.",
        "sandwich(e1,e2) sign probe (-e2) and norm(2) scalar probe guard rotor-norm traps.",
        "pose parity gate still separate — sandwich NOT used for landmarks.",
    ],
    "falsifiers": [
        "cxx sandwich used in LC2 pose probe",
        "norm returns rotor-only magnitude",
        "sandwich aliases rigid_pose",
    ],
    "dogfood_coupled": "yes",
    "spikes": ["motor7 bridge still VERIFY", "algebra_mode REFORM uses sandwich under mode switch"],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P6.4",
    "verdict": "WARN",
    "findings": [
        "cxx parity reference is PYTHON_ORACLE — honesty cxx_is_not_iron in receipt.",
        "f64 accumulation + /fp:strict — oracle bit-exact target, not SV sim HALF_UP or synth NR.",
        "gp_cli + cxx_backend + device.rs route sandwich/norm when CLIFFORD_BACKEND=cxx.",
        "P6.1 geo + pose gates still prerequisites.",
    ],
    "falsifiers": [
        "P6_4_PASS without SOFT_GP_ALU_PARITY_PASS",
        "receipt claims iron signoff",
    ],
    "receipt_gaps": [
        "cxx vs synth norm NR path not compared",
        "cxx vs verilator sim sandwich not bit-exact gate",
    ],
    "spikes": [
        "three norm numeric domains remain",
        "device mixed-backend until cxx==soft enforced in CI",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P6.4", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p64 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_ALU_P6_4_RECEIPT_v1.json"
    if p64.is_file():
        data = json.loads(p64.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p64.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
