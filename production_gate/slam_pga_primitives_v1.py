"""PGA-style geometric primitives + plane-first registration (REFORM study path)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from production_gate.slam_se3_motor_v1 import Motor, Vec3, centroid, motor_from_matrix4, rmse_m


@dataclass(frozen=True)
class Plane:
    """Oriented plane: unit normal n · x + d = 0 (d = -n·p0)."""

    nx: float
    ny: float
    nz: float
    d: float
    label: str

    def normal(self) -> Vec3:
        return self.nx, self.ny, self.nz

    def sample_points(self, n: int, *, rng: random.Random, span: float = 4.0) -> list[Vec3]:
        """Sample points on plane patch (teaching sim)."""
        nvec = self.normal()
        # pick tangent basis
        if abs(nvec[2]) < 0.9:
            ax, ay, az = 0.0, 0.0, 1.0
        else:
            ax, ay, az = 1.0, 0.0, 0.0
        tx = ay * nvec[2] - az * nvec[1]
        ty = az * nvec[0] - ax * nvec[2]
        tz = ax * nvec[1] - ay * nvec[0]
        tlen = math.sqrt(tx * tx + ty * ty + tz * tz)
        tx, ty, tz = tx / tlen, ty / tlen, tz / tlen
        bx = ty * nvec[2] - tz * nvec[1]
        by = tz * nvec[0] - tx * nvec[2]
        bz = tx * nvec[1] - ty * nvec[0]
        # point on plane
        p0 = (-self.d * nvec[0], -self.d * nvec[1], -self.d * nvec[2])
        pts: list[Vec3] = []
        for _ in range(n):
            u = rng.uniform(-span, span)
            v = rng.uniform(-span, span)
            pts.append(
                (
                    p0[0] + u * tx + v * bx,
                    p0[1] + u * ty + v * by,
                    p0[2] + u * tz + v * bz,
                )
            )
        return pts


def _kabsch_rotation(src: list[Vec3], dst: list[Vec3]) -> list[list[float]]:
    """3D Kabsch via quaternion eigen (Arun 1987) — stdlib only."""
    if len(src) != len(dst) or not src:
        raise ValueError("kabsch needs paired points")
    cs = centroid(src)
    cd = centroid(dst)
    h = [[0.0] * 3 for _ in range(3)]
    for (sx, sy, sz), (dx, dy, dz) in zip(src, dst):
        px, py, pz = sx - cs[0], sy - cs[1], sz - cs[2]
        qx, qy, qz = dx - cd[0], dy - cd[1], dz - cd[2]
        h[0][0] += px * qx
        h[0][1] += px * qy
        h[0][2] += px * qz
        h[1][0] += py * qx
        h[1][1] += py * qy
        h[1][2] += py * qz
        h[2][0] += pz * qx
        h[2][1] += pz * qy
        h[2][2] += pz * qz

    sxx, sxy, sxz = h[0]
    syx, syy, syz = h[1]
    szx, szy, szz = h[2]
    k = [
        [sxx + syy + szz, szy - syz, sxz - szx, syx - sxy],
        [szy - syz, sxx - syy - szz, sxy + syx, sxz + szx],
        [sxz - szx, sxy + syx, -sxx + syy - szz, syz + szy],
        [syx - sxy, sxz + szx, syz + szy, -sxx - syy + szz],
    ]

    # Power iteration for dominant eigenvector of 4x4 symmetric k
    v = [1.0, 0.0, 0.0, 0.0]
    for _ in range(32):
        nv = [sum(k[i][j] * v[j] for j in range(4)) for i in range(4)]
        norm = math.sqrt(sum(x * x for x in nv))
        if norm <= 0:
            break
        v = [x / norm for x in nv]
    qw, qx, qy, qz = v
    n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    qw, qx, qy, qz = qw / n, qx / n, qy / n, qz / n
    r00 = 1 - 2 * (qy * qy + qz * qz)
    r01 = 2 * (qx * qy - qz * qw)
    r02 = 2 * (qx * qz + qy * qw)
    r10 = 2 * (qx * qy + qz * qw)
    r11 = 1 - 2 * (qx * qx + qz * qz)
    r12 = 2 * (qy * qz - qx * qw)
    r20 = 2 * (qx * qz - qy * qw)
    r21 = 2 * (qy * qz + qx * qw)
    r22 = 1 - 2 * (qx * qx + qy * qy)
    # Quaternion eigen method returns R^T for our H layout — transpose to active rotation.
    return [
        [r00, r10, r20],
        [r01, r11, r21],
        [r02, r12, r22],
    ]


def register_points_kabsch(src: list[Vec3], dst: list[Vec3]) -> Motor:
    """Matrix-ICP teaching baseline: point cloud only."""
    cs = centroid(src)
    cd = centroid(dst)
    src_c = [(p[0] - cs[0], p[1] - cs[1], p[2] - cs[2]) for p in src]
    dst_c = [(p[0] - cd[0], p[1] - cd[1], p[2] - cd[2]) for p in dst]
    r = _kabsch_rotation(src_c, dst_c)
    # t = cd - R*cs
    tx = cd[0] - (r[0][0] * cs[0] + r[0][1] * cs[1] + r[0][2] * cs[2])
    ty = cd[1] - (r[1][0] * cs[0] + r[1][1] * cs[1] + r[1][2] * cs[2])
    tz = cd[2] - (r[2][0] * cs[0] + r[2][1] * cs[1] + r[2][2] * cs[2])
    m4 = [
        [r[0][0], r[0][1], r[0][2], tx],
        [r[1][0], r[1][1], r[1][2], ty],
        [r[2][0], r[2][1], r[2][2], tz],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return motor_from_matrix4(m4)


def register_planes_primitive(
    src_planes: list[Plane],
    dst_planes: list[Plane],
    src_points: list[Vec3],
    dst_points: list[Vec3],
) -> Motor:
    """REFORM-class: align plane normals (Wahba) then centroids — primitive-first."""
    if len(src_planes) != len(dst_planes) or not src_planes:
        raise ValueError("plane pairs required")
    # Rotation from normal correspondences
    src_n = [p.normal() for p in src_planes]
    dst_n = [p.normal() for p in dst_planes]
    r = _kabsch_rotation(src_n, dst_n)
    cs = centroid(src_points)
    cd = centroid(dst_points)
    rcs = (
        r[0][0] * cs[0] + r[0][1] * cs[1] + r[0][2] * cs[2],
        r[1][0] * cs[0] + r[1][1] * cs[1] + r[1][2] * cs[2],
        r[2][0] * cs[0] + r[2][1] * cs[1] + r[2][2] * cs[2],
    )
    tx, ty, tz = cd[0] - rcs[0], cd[1] - rcs[1], cd[2] - rcs[2]
    m4 = [
        [r[0][0], r[0][1], r[0][2], tx],
        [r[1][0], r[1][1], r[1][2], ty],
        [r[2][0], r[2][1], r[2][2], tz],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return motor_from_matrix4(m4)


def register_reform_r0_two_stage(
    src_planes: list[Plane],
    dst_planes: list[Plane],
    src_points: list[Vec3],
    dst_points: list[Vec3],
) -> tuple[Motor, Motor, float]:
    """REFORM R0: primitive plane match → point resample refine (study path)."""
    coarse = register_planes_primitive(src_planes, dst_planes, src_points, dst_points)
    src_coarse = [coarse.apply(p) for p in src_points]
    refined = register_points_kabsch(src_coarse, dst_points)
    # Compose: refined ∘ coarse
    m4c = coarse.as_matrix4()
    m4r = refined.as_matrix4()
    out = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            out[i][j] = sum(m4r[i][k] * m4c[k][j] for k in range(4))
    composed = motor_from_matrix4(out)
    coarse_rmse = rmse_m(src_coarse, dst_points)
    return coarse, composed, coarse_rmse


def synthetic_cave_corridor(*, rng: random.Random) -> dict:
    """GPS-denied tunnel: parallel walls + floor planes + point samples."""
    planes = [
        Plane(1.0, 0.0, 0.0, -2.0, "left_wall"),
        Plane(-1.0, 0.0, 0.0, -2.0, "right_wall"),
        Plane(0.0, 0.0, 1.0, 0.0, "floor"),
    ]
    points: list[Vec3] = []
    for pl in planes:
        points.extend(pl.sample_points(80, rng=rng, span=5.0))
    return {"planes": planes, "points": points, "scene_id": "synthetic_cave_corridor"}
