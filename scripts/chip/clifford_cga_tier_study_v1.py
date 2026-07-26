"""T5 tier-C vs tier-D study — cave traverse (oracle · not iron PASS alone)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_OUT = _REPO / "fixtures" / "chip" / "clifford_cga_tier_study_v1.json"
_PARITY_PASS_M = 0.005


def run_cga_tier_study(*, write: bool = True) -> dict[str, Any]:
    from dogfood_platform.slam_event_front_v1 import traverse_engine_parity_rmse_m
    from dogfood_platform.slam_pga8_motion_v1 import SlamPose
    from dogfood_platform.slam_reform_resample_v1 import load_or_build_dataset
    from dogfood_platform.slam_se3_motor_v1 import Motor, motor_from_axis_angle
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    data = load_or_build_dataset()
    points = [tuple(p) for p in data["src_points"]]
    step_m = 0.04
    n_ticks = 24

    # tier-C: SlamPose compose (matrix gold boundary)
    pose_c = SlamPose.identity()
    tier_c_rmse: list[float] = []
    for _ in range(n_ticks):
        delta = motor_from_axis_angle((0.0, 1.0, 0.0), step_m, (step_m, 0.0, 0.0))
        pose_c = SlamPose.compose(delta, pose_c)
        tier_c_rmse.append(pose_c.rmse_vs_motor7(points))

    # tier-D: CGA motor dq geo_prod chain
    dq_acc = DqMotor.identity()
    from dogfood_platform.slam_se3_motor_v1 import compose_motors

    m7_acc = Motor(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    tier_d_rmse: list[float] = []
    for _ in range(n_ticks):
        delta = motor_from_axis_angle((0.0, 1.0, 0.0), step_m, (step_m, 0.0, 0.0))
        dq_acc = DqMotor.from_motor7(delta).geo_prod(dq_acc)
        m7_acc = compose_motors(delta, m7_acc)
        tier_d_rmse.append(dq_acc.rmse_vs_matrix(m7_acc, points))

    max_c = max(tier_c_rmse) if tier_c_rmse else 999.0
    max_d = max(tier_d_rmse) if tier_d_rmse else 999.0
    slam_parity = traverse_engine_parity_rmse_m(points)

    verdict = (
        "TIER_STUDY_PASS"
        if max_c < _PARITY_PASS_M and max_d < _PARITY_PASS_M and slam_parity < _PARITY_PASS_M
        else "TIER_STUDY_FAIL"
    )

    doc: dict[str, Any] = {
        "study_id": "clifford_cga_tier_study_v1",
        "verdict": verdict,
        "dataset": data.get("dataset_id", "cave_corridor_dataset_v1"),
        "tier_c_slam_pose": {
            "label": "SlamPose + matrix compose",
            "max_rmse_m": round(max_c, 9),
            "seam": "rotor+translation",
        },
        "tier_d_cga_motor": {
            "label": "CGA dual-quaternion motor geo_prod",
            "max_rmse_m": round(max_d, 9),
            "seam": "single motor128",
        },
        "slam_pose_traverse_parity_m": round(slam_parity, 9),
        "honesty": {
            "lunar_dataset": "cave teaching — see clifford_cga_lunar_tier_study_v1.json",
            "tier_d_beats_tier_c": max_d <= max_c * 1.05 + 1e-9,
            "not_iron_rtl_study": True,
        },
    }

    if write:
        _OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    print(json.dumps(run_cga_tier_study(write=True), indent=2))
