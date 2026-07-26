"""motor7 (quat+trans I/O proxy) ↔ PGA8 motor128 gold bridge — INVENT L0.

Cl(3,0) spatial rotor map:
  s=qw, e12=-qz, e23=-qx, e31=-qy
See CLIFFORD_CODEC_CONTRACT_V0 §6 · LC2 z-rot probe.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8, _load_oracle

if TYPE_CHECKING:
    from dogfood_platform.slam_se3_motor_v1 import Motor, Vec3


def motor7_quat_to_pga8_rotor(m: "Motor") -> MotorPGA8:
    """Pure rotation motor7 → PGA8 even-grade rotor (no translation)."""
    return MotorPGA8.from_blades(s=m.qw, e12=-m.qz, e23=-m.qx, e31=-m.qy)


def pga8_rotor_to_motor7_quat(rotor: MotorPGA8) -> tuple[float, float, float, float]:
    """Inverse map for even-grade rotors (approximate — ignores tiny odd-grade noise)."""
    o = _load_oracle()
    c = rotor.coeffs
    qw = o.bf16_to_f32(c[0])
    qz = -o.bf16_to_f32(c[4])
    qx = -o.bf16_to_f32(c[5])
    qy = -o.bf16_to_f32(c[6])
    n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if n <= 0:
        return 1.0, 0.0, 0.0, 0.0
    return qw / n, qx / n, qy / n, qz / n


def motor7_point_to_pga8(x: float, y: float, z: float) -> MotorPGA8:
    return MotorPGA8.from_blades(e1=x, e2=y, e3=z)


def apply_pose_motor7(m: "Motor", p: "Vec3") -> "Vec3":
    return m.apply(p)


def apply_pose_pga8(rotor_m7: "Motor", p: "Vec3") -> "Vec3":
    """Rigid pose via PGA8 geo_prod chain (LAW) — translation in motor7 ignored for rotor-only."""
    rotor = motor7_quat_to_pga8_rotor(rotor_m7)
    return rotor.apply_point_m(p[0], p[1], p[2])


def compose_rotors_pga8(a: "Motor", b: "Motor") -> MotorPGA8:
    """Rotor composition via geo_prod (PGA), not matrix4 — portable engine path."""
    ra = motor7_quat_to_pga8_rotor(a)
    rb = motor7_quat_to_pga8_rotor(b)
    return ra.geo_prod(rb)


def z_rotation_motor7(theta_rad: float) -> Motor:
    from dogfood_platform.slam_se3_motor_v1 import motor_from_axis_angle

    return motor_from_axis_angle((0.0, 0.0, 1.0), theta_rad, (0.0, 0.0, 0.0))


def bridge_roundtrip_z_rot(theta_rad: float, *, tol: float = 0.01) -> tuple[bool, str]:
    m = z_rotation_motor7(theta_rad)
    rotor = motor7_quat_to_pga8_rotor(m)
    qw, qx, qy, qz = pga8_rotor_to_motor7_quat(rotor)
    err = abs(qw - m.qw) + abs(qx - m.qx) + abs(qy - m.qy) + abs(qz - m.qz)
    ok = err < tol
    return ok, f"quat_err={err:.6g}"


def lc2_pose_rmse_motor7_vs_pga8(theta_rad: float, landmarks: list["Vec3"]) -> tuple[float, float]:
    """RMSE: matrix4 apply vs PGA8 rigid_pose — should match for pure z-rot + points."""
    from dogfood_platform.slam_se3_motor_v1 import rmse_m

    m = z_rotation_motor7(theta_rad)
    mat_pts = [m.apply(p) for p in landmarks]
    pga_pts = [apply_pose_pga8(m, p) for p in landmarks]
    return rmse_m(mat_pts, pga_pts), rmse_m(pga_pts, mat_pts)
