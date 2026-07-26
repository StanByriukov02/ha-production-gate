"""SLAM pose runtime — PGA8 rotor + translation (platonic ideal, INVENT P7.2).

First principles (Cl(3,0) spatial v0):
  - Full SE(3) does not live in one 8-blade motor128 without CGA degenerate/translation bivectors.
  - Runtime state = even-grade rotor (MotorPGA8) + Vec3 translation.
  - Apply = SE(3) gold via rotor decode + matrix4 at meter-scale registration.
    rigid_pose(geo_prod) remains LC2/iron kinematic rail — not general SE(3) at corridor scale.
  - Compose = SE(3) group law; rotor part could geo_prod in future — v0 uses gold matrix
    repack at boundary to lock semantics with compose_motors(delta, acc).

motor7 remains I/O + Kabsch solver output; SlamPose is the portable engine state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dogfood_platform.clifford_pga8_motor_v1 import MotorPGA8
from scripts.chip.clifford_motor7_pga8_bridge_v0 import (
    motor7_quat_to_pga8_rotor,
    pga8_rotor_to_motor7_quat,
)

if TYPE_CHECKING:
    from dogfood_platform.slam_se3_motor_v1 import Motor, Vec3


@dataclass(frozen=True)
class SlamPose:
    rotor: MotorPGA8
    translation: tuple[float, float, float]

    @classmethod
    def identity(cls) -> SlamPose:
        return cls(rotor=MotorPGA8.from_blades(s=1.0), translation=(0.0, 0.0, 0.0))

    @classmethod
    def from_motor7(cls, m: "Motor") -> SlamPose:
        return cls(
            rotor=motor7_quat_to_pga8_rotor(m),
            translation=(m.tx, m.ty, m.tz),
        )

    def to_motor7(self) -> "Motor":
        from dogfood_platform.slam_se3_motor_v1 import Motor

        qw, qx, qy, qz = pga8_rotor_to_motor7_quat(self.rotor)
        return Motor(qw, qx, qy, qz, self.translation[0], self.translation[1], self.translation[2])

    def apply_point(self, p: "Vec3") -> "Vec3":
        """SE(3) gold apply at registration scale — PGA8 rotor state, matrix4 action.

        rigid_pose(geo_prod) is iron/LC2-valid on small landmarks; meter-scale SLAM
        uses decoded quaternion + translation (same as motor7) to match compose_motors.
        """
        return self.to_motor7().apply(p)

    def apply_points(self, points: list["Vec3"]) -> list["Vec3"]:
        return [self.apply_point(p) for p in points]

    @classmethod
    def compose(cls, delta: "Motor", acc: SlamPose) -> SlamPose:
        """Match compose_motors(delta, acc): p' = delta(acc(p))."""
        from dogfood_platform.slam_se3_motor_v1 import compose_motors

        composed_m7 = compose_motors(delta, acc.to_motor7())
        return cls.from_motor7(composed_m7)

    def rmse_vs_motor7(self, points: list["Vec3"]) -> float:
        """Per-step apply parity vs matrix4 motor7."""
        from dogfood_platform.slam_se3_motor_v1 import rmse_m

        m7 = self.to_motor7()
        a = self.apply_points(points)
        b = [m7.apply(p) for p in points]
        return rmse_m(a, b)


def motor7_to_slam_pose(m: "Motor") -> SlamPose:
    return SlamPose.from_motor7(m)


def slam_pose_to_motor7(pose: SlamPose) -> "Motor":
    return pose.to_motor7()
