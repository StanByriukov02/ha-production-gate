"""Moon robot crown bind — cxx vs verilator on Shackleton traverse vectors."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_VEC = _REPO / "fixtures" / "chip" / "clifford_moon_motion_vectors_v1.json"
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_CROWN_MOON_BIND_RECEIPT_v1.json"
_POSE_TOL_M = 0.006


def _pose_rmse(a: list[tuple[float, float, float]], b: list[tuple[float, float, float]]) -> float:
    if len(a) != len(b) or not a:
        return float("inf")
    err = 0.0
    for (ax, ay, az), (bx, by, bz) in zip(a, b):
        err += (ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2
    return math.sqrt(err / len(a))


def evaluate_crown_moon_bind(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))
    from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8, _load_oracle
    from scripts.chip.clifford_verilator_mmio_build_v0 import verilator_mmio_exe

    n_ticks = int(os.environ.get("CLIFFORD_CROWN_MOON_TICKS", "3"))
    verilator_built = verilator_mmio_exe() is not None
    parity_ok = False
    rmse = float("inf")
    detail = "vectors_missing"
    if verilator_built and _VEC.is_file():
        o = _load_oracle()
        ticks = list(json.loads(_VEC.read_text(encoding="utf-8")).get("ticks") or [])[:n_ticks]
        cxx_poses: list[tuple[float, float, float]] = []
        ver_poses: list[tuple[float, float, float]] = []

        def _xyz(m: MotorPGA8) -> tuple[float, float, float]:
            return (
                o.bf16_to_f32(m.coeffs[1]),
                o.bf16_to_f32(m.coeffs[2]),
                o.bf16_to_f32(m.coeffs[3]),
            )

        for t in ticks:
            r_hex = str(t["rotor_hex"])
            p_hex = str(t["point_hex"])
            os.environ["CLIFFORD_BACKEND"] = "cxx"
            cxx_poses.append(_xyz(MotorPGA8.from_hex(r_hex).rigid_pose(MotorPGA8.from_hex(p_hex))))
            os.environ["CLIFFORD_BACKEND"] = "verilator"
            ver_poses.append(_xyz(MotorPGA8.from_hex(r_hex).rigid_pose(MotorPGA8.from_hex(p_hex))))
        rmse = _pose_rmse(cxx_poses, ver_poses)
        parity_ok = math.isfinite(rmse) and rmse < _POSE_TOL_M
        detail = f"rmse_m={rmse:.6f} ticks={n_ticks}"

    checks = [
        {"id": "verilator_mmio_built", "pass": verilator_built},
        {"id": "moon_verilator_cxx_pose_parity", "pass": parity_ok, "detail": detail},
    ]
    verdict = "CROWN_MOON_BIND_PASS" if parity_ok and verilator_built else "CROWN_MOON_BIND_FAIL"
    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_CROWN_MOON_BIND_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "pose_rmse_m": round(rmse, 6) if math.isfinite(rmse) else None,
        "ticks_compared": n_ticks,
        "honesty": {
            "scene": "moon_shackleton_traverse",
            "not_lunar_visual": True,
            "iron_crown_via_verilator": True,
        },
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_crown_moon_bind()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "CROWN_MOON_BIND_PASS" else 1)
