#!/usr/bin/env python3
"""Merge P7.2 dual physics — SLAM REFORM PGA8 engine path."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P7.2",
    "verdict": "WARN",
    "findings": [
        "SlamPose = MotorPGA8 rotor + Vec3 — platonic ideal for Cl(3,0) spatial v0.",
        "SlamPose apply = SE(3) gold via rotor decode — rigid_pose geo_prod not general SE(3) at meter scale.",
        "SE(3) compose locked to compose_motors semantics via gold matrix repack.",
        "Kabsch/plane-first stay f64 at solver boundary — motor7 I/O proxy.",
        "Parallel benchmark proves PGA8 engine path matches matrix within gate.",
    ],
    "falsifiers": [
        "compose order swap undetected",
        "sandwich in pose warp",
        "PGA8 path breaks reform vs ICP guard band",
    ],
    "dogfood_coupled": "yes",
    "spikes": ["geo_prod full SE3 compose still PARK", "plane warp still matrix4"],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P7.2",
    "verdict": "WARN",
    "findings": [
        "P7.2 re-runs registration on fixed dataset — not stale R1 alone.",
        "bf16 apply seam documented; solver remains f64.",
        "reform vs ICP re-proved on PGA8 path.",
        "STUDY_SIM honesty — not iron MMIO.",
    ],
    "falsifiers": [
        "P7_2_PASS with path_delta > 5mm",
        "claims iron signoff",
    ],
    "receipt_gaps": [
        "event_front still matrix4 traverse",
        "device cxx silent fallback unasserted",
    ],
    "spikes": [
        "bf16 ULP near noise floor margin",
        "rigid_pose 2x GP per point cost on device path",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P7.2", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p72 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_SLAM_REFORM_P7_2_RECEIPT_v1.json"
    if p72.is_file():
        data = json.loads(p72.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p72.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
