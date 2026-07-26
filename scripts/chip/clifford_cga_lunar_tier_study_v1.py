"""T5 lunar tier-C vs tier-D compose study — promotion gate #2 (P2.1)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

_REPO = Path(__file__).resolve().parents[2]
_OUT = _REPO / "fixtures" / "chip" / "clifford_cga_lunar_tier_study_v1.json"
_PARITY_PASS_M = 0.005

# Regolith joint workspace probe (body frame · m) — not cave SLAM cloud
_LUNAR_PROBE_M: list[tuple[float, float, float]] = [
    (0.8, 0.0, 0.0),
    (0.4, 0.2, 0.1),
    (-0.2, 0.0, 0.3),
    (0.0, 0.0, 0.5),
    (0.15, -0.15, 0.25),
]


def _compose_chain(
    deltas: Iterable[Any],
    points: list[tuple[float, float, float]],
) -> dict[str, float]:
    from dogfood_platform.slam_pga8_motion_v1 import SlamPose
    from dogfood_platform.slam_se3_motor_v1 import Motor, compose_motors
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    pose_c = SlamPose.identity()
    dq_acc = DqMotor.identity()
    m7_acc = Motor(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    max_c = 0.0
    max_d = 0.0

    for delta in deltas:
        pose_c = SlamPose.compose(delta, pose_c)
        dq_acc = DqMotor.from_motor7(delta).geo_prod(dq_acc)
        m7_acc = compose_motors(delta, m7_acc)
        max_c = max(max_c, pose_c.rmse_vs_motor7(points))
        max_d = max(max_d, dq_acc.rmse_vs_matrix(m7_acc, points))

    return {"max_tier_c_rmse_m": max_c, "max_tier_d_rmse_m": max_d}


def _deltas_lunar_slow_joint(n_steps: int = 48) -> list[Any]:
    from dogfood_platform.slam_se3_motor_v1 import motor_from_axis_angle

    step = (math.pi / 6) / n_steps
    return [motor_from_axis_angle((0.0, 0.0, 1.0), step, (0.0, 0.0, 0.0)) for _ in range(n_steps)]


def _deltas_lunar_fast_vibe(n_steps: int = 32) -> list[Any]:
    from dogfood_platform.slam_se3_motor_v1 import motor_from_axis_angle

    deltas: list[Any] = []
    prev = 0.05
    for i in range(1, n_steps + 1):
        t = i / n_steps
        angle = 0.05 + 0.02 * math.sin(2.0 * math.pi * t * 4.0)
        deltas.append(motor_from_axis_angle((0.0, 0.0, 1.0), angle - prev, (0.0, 0.0, 0.0)))
        prev = angle
    return deltas


def run_cga_lunar_tier_study(*, write: bool = True) -> dict[str, Any]:
    import sys

    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))

    points = list(_LUNAR_PROBE_M)
    scopes: dict[str, Any] = {}

    for scope_id, n_steps, deltas_fn in (
        ("lunar_slow_joint", 48, _deltas_lunar_slow_joint),
        ("lunar_fast_vibe", 32, _deltas_lunar_fast_vibe),
    ):
        metrics = _compose_chain(deltas_fn(n_steps), points)
        scopes[scope_id] = {
            "scope_id": scope_id,
            "tag": "lunar",
            "n_steps": n_steps,
            "probe_points": len(points),
            **{k: round(v, 9) for k, v in metrics.items()},
            "pass": metrics["max_tier_c_rmse_m"] < _PARITY_PASS_M
            and metrics["max_tier_d_rmse_m"] < _PARITY_PASS_M,
            "tier_d_beats_tier_c": metrics["max_tier_d_rmse_m"]
            <= metrics["max_tier_c_rmse_m"] * 1.05 + 1e-9,
        }

    all_pass = all(s["pass"] for s in scopes.values())
    verdict = "LUNAR_TIER_STUDY_PASS" if all_pass else "LUNAR_TIER_STUDY_FAIL"

    doc: dict[str, Any] = {
        "study_id": "clifford_cga_lunar_tier_study_v1",
        "verdict": verdict,
        "parity_pass_m": _PARITY_PASS_M,
        "scopes": scopes,
        "honesty": {
            "mission": "Shackleton lunar joint + vibe (T3 scope matrix)",
            "not_full_32blade_cga": True,
            "motor_subalgebra_dq": "phase-1 P2.1 — full R_3_0_1 GP is phase-2 track",
            "cave_study_separate": "clifford_cga_tier_study_v1.json",
        },
    }

    if write:
        _OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    print(json.dumps(run_cga_lunar_tier_study(write=True), indent=2))
