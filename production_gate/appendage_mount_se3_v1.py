"""Appendage mount SE(3) v1 — motor compose mount_xyz + mount_rpy → world EE.

Closes deferred AC_MOUNT_SE3_RPY (teaching tier · Python motor port).
TABU: claim field-calibrated mount · claim Rust crown mount truth.
"""
from __future__ import annotations

import math
from typing import Any

PROOF_TIER = "APPENDAGE_MOUNT_SE3_SLICE"
ORACLE = "SLAM_SE3_MOTOR_PORT"


def motor_from_rpy_xyz(rpy: list[float], xyz: list[float]) -> Any:
    from production_gate.slam_se3_motor_v1 import Motor

    roll, pitch, yaw = (float(rpy[0]), float(rpy[1]), float(rpy[2])) if len(rpy) >= 3 else (0.0, 0.0, 0.0)
    tx, ty, tz = (float(xyz[0]), float(xyz[1]), float(xyz[2])) if len(xyz) >= 3 else (0.0, 0.0, 0.0)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz) or 1.0
    return Motor(qw / n, qx / n, qy / n, qz / n, tx, ty, tz)


def mount_ee_world_translate(ee_local: dict[str, Any], mount_xyz: list[float]) -> dict[str, float]:
    mx, my, mz = [float(v) for v in (mount_xyz or [0.0, 0.0, 0.0])]
    return {
        "x": float(ee_local.get("x") or 0.0) + mx,
        "y": float(ee_local.get("y") or 0.0) + my,
        "z": float(ee_local.get("z") or 0.0) + mz,
    }


def mount_ee_world_se3(
    ee_local: dict[str, Any],
    *,
    mount_xyz: list[float],
    mount_rpy: list[float],
) -> dict[str, float]:
    mount = motor_from_rpy_xyz(mount_rpy, mount_xyz)
    lx = float(ee_local.get("x") or 0.0)
    ly = float(ee_local.get("y") or 0.0)
    lz = float(ee_local.get("z") or 0.0)
    wx, wy, wz = mount.apply((lx, ly, lz))
    return {"x": wx, "y": wy, "z": wz}


def mount_ee_world(
    ee_local: dict[str, Any],
    mount: dict[str, Any],
    *,
    use_se3: bool = True,
) -> dict[str, float]:
    xyz = list(mount.get("mount_xyz") or [0.0, 0.0, 0.0])
    rpy = list(mount.get("mount_rpy") or [0.0, 0.0, 0.0])
    if use_se3 and any(abs(v) > 1e-12 for v in rpy):
        return mount_ee_world_se3(ee_local, mount_xyz=xyz, mount_rpy=rpy)
    if use_se3:
        return mount_ee_world_se3(ee_local, mount_xyz=xyz, mount_rpy=rpy)
    return mount_ee_world_translate(ee_local, xyz)


def run_mount_se3_smoke() -> dict[str, Any]:
    ee = {"x": 0.5, "y": 0.0, "z": 0.0}
    xyz = [0.1, 0.0, 0.2]
    rpy_zero = [0.0, 0.0, 0.0]
    rpy_yaw = [0.0, 0.0, 0.4]

    tr0 = mount_ee_world_translate(ee, xyz)
    se0 = mount_ee_world_se3(ee, mount_xyz=xyz, mount_rpy=rpy_zero)
    se_yaw = mount_ee_world_se3(ee, mount_xyz=xyz, mount_rpy=rpy_yaw)
    tr_yaw = mount_ee_world_translate(ee, xyz)

    identity_err = math.sqrt(
        sum((float(se0[k]) - float(tr0[k])) ** 2 for k in ("x", "y", "z"))
    )
    diverge_dy = abs(float(se_yaw["y"]) - float(tr_yaw["y"]))

    checks = {
        "F_identity_parity": identity_err < 1e-9,
        "F_rpy_diverge": diverge_dy > 0.01,
        "F_se_yaw_finite": math.isfinite(float(se_yaw["x"])),
        "F_mount_z": abs(float(se0["z"]) - 0.2) < 1e-9,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "APPENDAGE_MOUNT_SE3_SLICE_PASS" if not fail else "APPENDAGE_MOUNT_SE3_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "identity_err_m": identity_err,
        "diverge_dy_m": diverge_dy,
        "se_yaw": se_yaw,
    }
