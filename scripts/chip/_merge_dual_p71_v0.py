#!/usr/bin/env python3
"""Merge P7.1 dual physics — PGA8 motor bridge + twin motion layer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

SUB_ALGEBRA = {
    "mode": "CLIFFORD_ALGEBRA_PHYS",
    "phase": "P7.1",
    "verdict": "WARN",
    "findings": [
        "MotorPGA8 canonical type at dogfood_platform/clifford_pga8_motor_v1.py — portable across twin/robot/device.",
        "motor7 quat map s=qw,e12=-qz,e23=-qx,e31=-qy gold-tested vs LC2 z-rotor.",
        "Pose via rigid_pose (geo_prod chain) — sandwich remains REFORM-only.",
        "Twin overlay points now route through MotorPGA8 API.",
        "matrix4 compose still motor7 study — rotor compose via geo_prod documented.",
    ],
    "falsifiers": [
        "twin pose uses sandwich",
        "motor7_parity true without RMSE gate",
        "PGA8 layer claims PHG/MLIR lowering done",
    ],
    "dogfood_coupled": "yes",
    "spikes": ["general SE3 compose not matrix4", "mlir lowering still PARK"],
}

SUB_IRON = {
    "mode": "CLIFFORD_IRON_RELIABILITY",
    "phase": "P7.1",
    "verdict": "WARN",
    "findings": [
        "P7.1 binds motion_engine in twin scene manifest when PASS.",
        "Prereq P6.4 cxx parity + LC2 iron pose probe.",
        "C++ rotor_from_quat exported for portable host builds.",
        "motor7_parity is host oracle agreement — not iron MMIO parity.",
    ],
    "falsifiers": [
        "P7_1_PASS without pga8_motion_layer.json",
        "scene bind missing motion_engine block",
    ],
    "receipt_gaps": [
        "SLAM reform still matrix4 compose internally",
        "full twin scene rebind receipt not auto-rerun",
    ],
    "spikes": [
        "robot chassis path not yet using MotorPGA8",
        "gpu twin PTX still PARK",
    ],
}

if __name__ == "__main__":
    r = merge_sub_reviews(phase="P7.1", sub_algebra=SUB_ALGEBRA, sub_iron=SUB_IRON, write=True)
    print(json.dumps({"verdict": r["verdict"], "receipt_id": r["receipt_id"]}, indent=2))

    p71 = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_PGA8_MOTOR_BRIDGE_P7_1_RECEIPT_v1.json"
    if p71.is_file():
        data = json.loads(p71.read_text(encoding="utf-8"))
        data.setdefault("honesty", {})["dual_physics"] = r["verdict"]
        data["honesty"]["dual_physics_receipt"] = r["receipt_id"]
        p71.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
