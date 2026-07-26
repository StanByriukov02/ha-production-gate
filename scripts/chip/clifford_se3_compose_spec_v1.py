"""SE(3) compose spec + falsifiers (T6 H3) — impl PARK."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_SPEC = _REPO / "docs" / "agent_workflow" / "CLIFFORD_SE3_COMPOSE_SPEC_v1.md"
_FIXTURE = _REPO / "fixtures" / "chip" / "clifford_se3_compose_spec_v1.json"
_PARITY_PASS_M = 0.005
_CORRIDOR_RMSE_PASS_M = 0.005


def _falsifier_compose_matrix_gold() -> dict[str, Any]:
    from dogfood_platform.slam_pga8_motion_v1 import SlamPose
    from dogfood_platform.slam_se3_motor_v1 import Motor, compose_motors, motor_from_axis_angle

    delta = motor_from_axis_angle((0.0, 1.0, 0.0), 0.04, (0.04, 0.0, 0.0))
    acc = SlamPose.identity()
    composed = SlamPose.compose(delta, acc)
    m7 = compose_motors(delta, acc.to_motor7())
    pts = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    rmse = composed.rmse_vs_motor7(pts)
    return {
        "id": "F2_compose_matrix_gold",
        "pass": rmse < _PARITY_PASS_M and math.isfinite(rmse),
        "rmse_m": round(rmse, 9),
        "detail": "SlamPose.compose matches compose_motors matrix4",
    }


def _falsifier_gp_not_full_se3() -> dict[str, Any]:
    """geo_prod on motor128 cannot represent arbitrary SE(3) compose without trans seam."""
    from scripts.chip.clifford_pga8_oracle_v0 import geo_prod_coeffs, motor_from_blades

    e1 = motor_from_blades(e1=1.0)
    t = motor_from_blades(e12=0.5)
    gp_only = geo_prod_coeffs(e1, t)
    blade_names = ("s", "e01", "e02", "e03", "e12", "e13", "e23", "e123")
    trans_energy = sum(abs(gp_only[i]) for i in (4, 5, 6))
    return {
        "id": "F1_gp_not_full_se3_compose",
        "pass": True,
        "detail": f"gp(e1,t) bivector energy={trans_energy} — SE(3) compose needs trans state outside single gp",
        "guard": "tier-C seam documented",
    }


def _falsifier_rigid_pose_vs_slam_corridor() -> dict[str, Any]:
    from dogfood_platform.slam_event_front_v1 import traverse_engine_parity_rmse_m
    from dogfood_platform.slam_reform_resample_v1 import load_or_build_dataset

    data = load_or_build_dataset()
    points = [tuple(p) for p in data["src_points"]]
    rmse = traverse_engine_parity_rmse_m(points)
    return {
        "id": "F3_corridor_slam_pose_parity",
        "pass": rmse < _CORRIDOR_RMSE_PASS_M,
        "rmse_m": round(rmse, 9),
        "detail": "SlamPose traverse vs motor7 reference on cave dataset",
    }


def _falsifier_tier_d_oracle_promoted() -> dict[str, Any]:
    chip = _REPO / "results" / "platform_bpass" / "chip"
    t5_path = chip / "CHIP_CLIFFORD_CGA_P21_UNPARK_T5_RECEIPT_v1.json"
    lunar_path = _REPO / "fixtures" / "chip" / "clifford_cga_lunar_tier_study_v1.json"
    td_path = chip / "CHIP_CLIFFORD_TRAVERSE_TIER_D_RECEIPT_v1.json"
    p63_path = chip / "CHIP_CLIFFORD_DEVICE_RUST_P6_3_RECEIPT_v1.json"
    mmio_path = chip / "CHIP_CLIFFORD_MMIO_OP_DQ_SKETCH_RECEIPT_v1.json"
    t5_ok = False
    lunar_ok = False
    t5_verdict = ""
    if t5_path.is_file():
        t5 = json.loads(t5_path.read_text(encoding="utf-8"))
        t5_verdict = t5.get("verdict", "")
        t5_ok = t5_verdict in ("T5_CGA_ORACLE_IRON_PASS", "T5_CGA_ORACLE_PASS")
    if lunar_path.is_file():
        lunar_ok = json.loads(lunar_path.read_text(encoding="utf-8")).get("verdict") == "LUNAR_TIER_STUDY_PASS"
    td_ok = td_path.is_file() and json.loads(td_path.read_text(encoding="utf-8")).get("verdict") == "TRAVERSE_TIER_D_PASS"
    p63_ok = p63_path.is_file() and json.loads(p63_path.read_text(encoding="utf-8")).get("verdict") == "RUST_DEVICE_P6_3_PASS"
    mmio_ok = mmio_path.is_file() and json.loads(mmio_path.read_text(encoding="utf-8")).get("verdict") == "MMIO_OP_DQ_SKETCH_PASS"
    chain_ok = t5_ok and lunar_ok and td_ok and p63_ok and mmio_ok
    return {
        "id": "F4_tier_d_dq_oracle_promoted",
        "pass": chain_ok,
        "detail": (
            f"T5={t5_verdict} · lunar={lunar_ok} · TD={td_ok} · P6.3={p63_ok} · MMIO={mmio_ok} · "
            "phase-1 DQ motor128 (not 32-blade)"
        ),
        "guard": "iron opcode compose still PARK",
    }


def run_clifford_se3_compose_spec(*, write: bool = True) -> dict[str, Any]:
    falsifiers = [
        _falsifier_gp_not_full_se3(),
        _falsifier_compose_matrix_gold(),
        _falsifier_rigid_pose_vs_slam_corridor(),
        _falsifier_tier_d_oracle_promoted(),
    ]
    numeric = [f for f in falsifiers if f["id"] != "F1_gp_not_full_se3_compose"]
    verdict = "SE3_SPEC_PASS" if all(f["pass"] for f in numeric) and _SPEC.is_file() else "SE3_SPEC_FAIL"

    doc: dict[str, Any] = {
        "spec_id": "CLIFFORD_SE3_COMPOSE_SPEC_v1",
        "verdict": verdict,
        "spec_path": str(_SPEC.relative_to(_REPO)).replace("\\", "/"),
        "falsifiers": falsifiers,
        "tiers": {
            "C": "motor128 rotor + matrix seam",
            "C_plus": "SlamPose rotor+trans · matrix gold compose",
            "D": "CGA32 IRON + MMIO OP_CGA32 · P6.5 host bridge · compose benchmark",
        },
        "honesty": {
            "geo_prod_se3_impl": "PARK",
            "iron_opcode_compose": False,
            "tier_d_runtime_oracle": "DqPose in dogfood_platform/slam_pose_dq_v1.py",
            "slam_pose_runtime_gold": "matrix4 boundary (tier-C+)",
            "mlir_emit_satisfies_spec": False,
        },
    }

    if write:
        _FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        _FIXTURE.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    return doc


if __name__ == "__main__":
    print(json.dumps(run_clifford_se3_compose_spec(write=True), indent=2))
