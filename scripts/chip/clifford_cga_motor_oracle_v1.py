"""CGA motor oracle v1 — dual quaternion on motor128 (T5 tier-D gold).

Layout (bf16 lanes 0..7):
  0..3  Qr = (w, x, y, z) rotation quaternion
  4..7  Qd = (w, x, y, z) dual part — SE(3) motor without matrix seam

Honesty: 32-blade full CGA multivector PARK; this is the **motor subalgebra** target for P2.1.
Cl(3,0) PGA geo_prod on same 8 lanes is a **different** law — do not confuse.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Iterable

BF16_ONE = 0x3F80


def bf16_to_f32(h: int) -> float:
    return struct.unpack(">f", struct.pack(">I", int(h) << 16))[0]


def f32_to_bf16(x: float) -> int:
    bits = struct.unpack(">I", struct.pack(">f", float(x)))[0]
    return (bits + 0x7FFF + ((bits >> 16) & 1)) >> 16


Quat = tuple[float, float, float, float]


def quat_mul(a: Quat, b: Quat) -> Quat:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def quat_add(a: Quat, b: Quat) -> Quat:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])


def quat_norm(a: Quat) -> Quat:
    n = math.sqrt(sum(c * c for c in a))
    if n <= 0:
        return (1.0, 0.0, 0.0, 0.0)
    return tuple(c / n for c in a)


@dataclass(frozen=True)
class DqMotor:
    qr: Quat
    qd: Quat

    @classmethod
    def identity(cls) -> DqMotor:
        return cls((1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))

    @classmethod
    def from_se3(cls, qw: float, qx: float, qy: float, qz: float, tx: float, ty: float, tz: float) -> DqMotor:
        qr = quat_norm((qw, qx, qy, qz))
        tq = (0.0, tx, ty, tz)
        qd = tuple(0.5 * c for c in quat_mul(tq, qr))
        return cls(qr, qd)

    @classmethod
    def from_motor7(cls, m: object) -> DqMotor:
        return cls.from_se3(m.qw, m.qx, m.qy, m.qz, m.tx, m.ty, m.tz)  # type: ignore[attr-defined]

    @classmethod
    def from_bf16_coeffs(cls, coeffs: Iterable[int]) -> DqMotor:
        c = list(coeffs)
        if len(c) != 8:
            raise ValueError("expected 8 bf16 lanes")
        qr = tuple(bf16_to_f32(c[i]) for i in range(4))
        qd = tuple(bf16_to_f32(c[i]) for i in range(4, 8))
        return cls(qr, qd)

    def to_bf16_coeffs(self) -> list[int]:
        out: list[int] = []
        for q in (self.qr, self.qd):
            for v in q:
                out.append(f32_to_bf16(v))
        return out

    def to_motor128_hex(self) -> str:
        c = self.to_bf16_coeffs()
        w = 0
        for i, h in enumerate(c):
            w |= (int(h) & 0xFFFF) << (16 * i)
        return f"{w:032x}"

    def geo_prod(self, other: DqMotor) -> DqMotor:
        """CGA motor product = dual quaternion multiply."""
        r = quat_mul(self.qr, other.qr)
        d = quat_add(quat_mul(self.qr, other.qd), quat_mul(self.qd, other.qr))
        return DqMotor(r, d)

    def apply_point(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """Point transform: p' = qr*p*qr* + 2*qd*qr* (dual quaternion rigid map)."""
        p = (0.0, x, y, z)
        qr_c = (self.qr[0], -self.qr[1], -self.qr[2], -self.qr[3])
        pr = quat_mul(quat_mul(self.qr, p), qr_c)
        tr = quat_mul(self.qd, qr_c)
        out = quat_add(pr, quat_mul(tr, (2.0, 0.0, 0.0, 0.0)))
        return (out[1], out[2], out[3])

    def rmse_vs_matrix(self, m7: object, points: list[tuple[float, float, float]]) -> float:
        from dogfood_platform.slam_se3_motor_v1 import rmse_m

        a = [self.apply_point(*p) for p in points]
        b = [m7.apply(p) for p in points]  # type: ignore[attr-defined]
        return rmse_m(a, b)

    def to_motor7(self) -> object:
        """Decode DQ motor → motor7 (f64 gold)."""
        from dogfood_platform.slam_se3_motor_v1 import Motor

        qw, qx, qy, qz = self.qr
        qr_c = (qw, -qx, -qy, -qz)
        tr = quat_mul(self.qd, qr_c)
        tx, ty, tz = 2.0 * tr[1], 2.0 * tr[2], 2.0 * tr[3]
        return Motor(qw, qx, qy, qz, tx, ty, tz)


def dq_geo_prod_coeffs(a: list[int], b: list[int]) -> list[int]:
    return DqMotor.from_bf16_coeffs(a).geo_prod(DqMotor.from_bf16_coeffs(b)).to_bf16_coeffs()


def cl30_pure_spatial_is_dq_identity_rot(a: list[int]) -> bool:
    """Falsifier helper: Cl(3,0) blade packing ≠ DQ packing for general motors."""
    _ = a
    return False
