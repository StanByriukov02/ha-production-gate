"""SE(3) motor — unit quaternion + translation (PGA study path, stdlib only)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class Motor:
    """Rigid transform motor: unit quaternion (w,x,y,z) + translation (m)."""

    qw: float
    qx: float
    qy: float
    qz: float
    tx: float
    ty: float
    tz: float

    @property
    def param_count(self) -> int:
        return 7

    def as_matrix4(self) -> list[list[float]]:
        w, x, y, z = self.qw, self.qx, self.qy, self.qz
        r00 = 1 - 2 * (y * y + z * z)
        r01 = 2 * (x * y - z * w)
        r02 = 2 * (x * z + y * w)
        r10 = 2 * (x * y + z * w)
        r11 = 1 - 2 * (x * x + z * z)
        r12 = 2 * (y * z - x * w)
        r20 = 2 * (x * z - y * w)
        r21 = 2 * (y * z + x * w)
        r22 = 1 - 2 * (x * x + y * y)
        return [
            [r00, r01, r02, self.tx],
            [r10, r11, r12, self.ty],
            [r20, r21, r22, self.tz],
            [0.0, 0.0, 0.0, 1.0],
        ]

    def apply(self, p: Vec3) -> Vec3:
        m = self.as_matrix4()
        x, y, z = p
        return (
            m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
        )


def _normalize_quat(qw: float, qx: float, qy: float, qz: float) -> tuple[float, float, float, float]:
    n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if n <= 0:
        return 1.0, 0.0, 0.0, 0.0
    return qw / n, qx / n, qy / n, qz / n


def motor_from_axis_angle(axis: Vec3, angle_rad: float, translation: Vec3) -> Motor:
    ax, ay, az = axis
    n = math.sqrt(ax * ax + ay * ay + az * az)
    if n <= 0:
        qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
    else:
        ax, ay, az = ax / n, ay / n, az / n
        half = angle_rad / 2.0
        s = math.sin(half)
        qw, qx, qy, qz = math.cos(half), ax * s, ay * s, az * s
    qw, qx, qy, qz = _normalize_quat(qw, qx, qy, qz)
    return Motor(qw, qx, qy, qz, translation[0], translation[1], translation[2])


def motor_from_matrix4(m: list[list[float]]) -> Motor:
    r00, r01, r02, tx = m[0]
    r10, r11, r12, ty = m[1]
    r20, r21, r22, tz = m[2]
    trace = r00 + r11 + r22
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        qw = 0.25 * s
        qx = (r21 - r12) / s
        qy = (r02 - r20) / s
        qz = (r10 - r01) / s
    elif r00 > r11 and r00 > r22:
        s = math.sqrt(1.0 + r00 - r11 - r22) * 2
        qw = (r21 - r12) / s
        qx = 0.25 * s
        qy = (r01 + r10) / s
        qz = (r02 + r20) / s
    elif r11 > r22:
        s = math.sqrt(1.0 + r11 - r00 - r22) * 2
        qw = (r02 - r20) / s
        qx = (r01 + r10) / s
        qy = 0.25 * s
        qz = (r12 + r21) / s
    else:
        s = math.sqrt(1.0 + r22 - r00 - r11) * 2
        qw = (r10 - r01) / s
        qx = (r02 + r20) / s
        qy = (r12 + r21) / s
        qz = 0.25 * s
    qw, qx, qy, qz = _normalize_quat(qw, qx, qy, qz)
    return Motor(qw, qx, qy, qz, tx, ty, tz)


def compose_motors(a: Motor, b: Motor) -> Motor:
    """Apply b then a: p' = a(b(p))."""
    ma = a.as_matrix4()
    mb = b.as_matrix4()
    out = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            out[i][j] = sum(ma[i][k] * mb[k][j] for k in range(4))
    return motor_from_matrix4(out)


def centroid(points: Iterable[Vec3]) -> Vec3:
    pts = list(points)
    if not pts:
        return 0.0, 0.0, 0.0
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sz = sum(p[2] for p in pts)
    n = float(len(pts))
    return sx / n, sy / n, sz / n


def rmse_m(a: Iterable[Vec3], b: Iterable[Vec3]) -> float:
    pa = list(a)
    pb = list(b)
    if len(pa) != len(pb) or not pa:
        return float("inf")
    acc = 0.0
    for (x1, y1, z1), (x2, y2, z2) in zip(pa, pb):
        dx, dy, dz = x1 - x2, y1 - y2, z1 - z2
        acc += dx * dx + dy * dy + dz * dz
    return math.sqrt(acc / len(pa))
