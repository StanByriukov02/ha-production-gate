"""LieIntegratorPort v1 — SE(3) twist → exp-map step (plug-in surface).

Good backend: compose_motors + motor_from_axis_angle (manifold retraction).
Bad backend: Euclidean quaternion addition (classic drift inject).

TABU: claim Newton-X symplectic platform · claim production multibody sim.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

from dogfood_platform.slam_se3_motor_v1 import Motor, compose_motors, motor_from_axis_angle

PROOF_TIER = "LIE_INTEGRATOR_PORT_SLICE"
BACKEND_LIE_EXP = "lie_exp_map_v1"
BACKEND_LIE_SYMPLECTIC_SPLIT = "lie_symplectic_split_v1"
BACKEND_LIE_RUST_CGA = "lie_rust_cga_exp_v1"
BACKEND_EUCLIDEAN_BAD = "lie_euclidean_bad_inject_v1"
BACKEND_LIE_SPHERE_ORBIT = "lie_sphere_orbit_v1"
CONTRACT_PATH = "fixtures/robot/lie_integrator_port_v0.json"

MANIFOLD_QUAT_TOL = 1e-4
MANIFOLD_ROT_TOL = 1e-3
BAD_DRIFT_MIN = 0.02
CONSTRAINT_TOL_GOOD = 0.05
CONSTRAINT_TOL_BAD = 0.12
PENDULUM_ENERGY_DRIFT_MAX_SYMP = 0.35
MULTIBODY_G5_DRIFT_MAX = 0.45


@dataclass(frozen=True)
class Twist:
    omega_rad: tuple[float, float, float]
    linear_m: tuple[float, float, float]

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> Twist:
        o = row.get("omega_rad") or (0.0, 0.0, 0.0)
        v = row.get("linear_m") or (0.0, 0.0, 0.0)
        return cls(
            (float(o[0]), float(o[1]), float(o[2])),
            (float(v[0]), float(v[1]), float(v[2])),
        )


@dataclass(frozen=True)
class LieStepResult:
    pose: Motor
    source_id: str
    quat_norm: float
    rotation_frobenius_err: float
    on_manifold: bool

    def pose_dict(self) -> dict[str, float]:
        p = self.pose
        return {
            "qw": round(p.qw, 6),
            "qx": round(p.qx, 6),
            "qy": round(p.qy, 6),
            "qz": round(p.qz, 6),
            "tx": round(p.tx, 6),
            "ty": round(p.ty, 6),
            "tz": round(p.tz, 6),
        }

    def to_row(self) -> dict[str, Any]:
        return {
            "pose_motor": self.pose_dict(),
            "source_id": self.source_id,
            "quat_norm": round(self.quat_norm, 8),
            "rotation_frobenius_err": round(self.rotation_frobenius_err, 8),
            "on_manifold": self.on_manifold,
        }


class LieIntegratorPort(Protocol):
    def step(self, pose: Motor, twist: Twist, *, dt: float = 1.0) -> LieStepResult: ...


def motor_from_dict(row: dict[str, Any]) -> Motor:
    return Motor(
        float(row.get("qw", 1.0)),
        float(row.get("qx", 0.0)),
        float(row.get("qy", 0.0)),
        float(row.get("qz", 0.0)),
        float(row.get("tx", 0.0)),
        float(row.get("ty", 0.0)),
        float(row.get("tz", 0.0)),
    )


def motor_quat_norm(m: Motor) -> float:
    return math.sqrt(m.qw * m.qw + m.qx * m.qx + m.qy * m.qy + m.qz * m.qz)


def motor_rotation_frobenius_err(m: Motor) -> float:
    mat = m.as_matrix4()
    r00, r01, r02 = mat[0][0], mat[0][1], mat[0][2]
    r10, r11, r12 = mat[1][0], mat[1][1], mat[1][2]
    r20, r21, r22 = mat[2][0], mat[2][1], mat[2][2]
    # R^T R - I (3x3)
    e00 = r00 * r00 + r10 * r10 + r20 * r20 - 1.0
    e01 = r00 * r01 + r10 * r11 + r20 * r21
    e02 = r00 * r02 + r10 * r12 + r20 * r22
    e11 = r01 * r01 + r11 * r11 + r21 * r21 - 1.0
    e12 = r01 * r02 + r11 * r12 + r21 * r22
    e22 = r02 * r02 + r12 * r12 + r22 * r22 - 1.0
    return math.sqrt(e00 * e00 + e01 * e01 + e02 * e02 + e11 * e11 + e12 * e12 + e22 * e22)


def manifold_metrics(m: Motor) -> tuple[float, float, bool]:
    qn = motor_quat_norm(m)
    rot_err = motor_rotation_frobenius_err(m)
    on = abs(qn - 1.0) <= MANIFOLD_QUAT_TOL and rot_err <= MANIFOLD_ROT_TOL
    return qn, rot_err, on


def _wrap_result(pose: Motor, source_id: str) -> LieStepResult:
    qn, rot_err, on = manifold_metrics(pose)
    return LieStepResult(pose=pose, source_id=source_id, quat_norm=qn, rotation_frobenius_err=rot_err, on_manifold=on)


class LieExpMapBackend:
    """R_new = R ⊗ exp(Φ·dt) — axis-angle exp + translation via motor compose."""

    source_id = BACKEND_LIE_EXP

    def step(self, pose: Motor, twist: Twist, *, dt: float = 1.0) -> LieStepResult:
        ox, oy, oz = twist.omega_rad
        lx, ly, lz = twist.linear_m
        omega_mag = math.sqrt(ox * ox + oy * oy + oz * oz)
        if omega_mag > 1e-12:
            axis = (ox / omega_mag, oy / omega_mag, oz / omega_mag)
            delta_r = motor_from_axis_angle(axis, omega_mag * dt, (0.0, 0.0, 0.0))
        else:
            delta_r = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))
        delta_t = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (lx * dt, ly * dt, lz * dt))
        delta = compose_motors(delta_t, delta_r)
        new_pose = compose_motors(pose, delta)
        return _wrap_result(new_pose, self.source_id)


class LieSymplecticSplitBackend:
    """Störmer–Verlet split: half rotation · full translation · half rotation."""

    source_id = BACKEND_LIE_SYMPLECTIC_SPLIT

    def step(self, pose: Motor, twist: Twist, *, dt: float = 1.0) -> LieStepResult:
        ox, oy, oz = twist.omega_rad
        lx, ly, lz = twist.linear_m
        omega_mag = math.sqrt(ox * ox + oy * oy + oz * oz)
        if omega_mag > 1e-12:
            axis = (ox / omega_mag, oy / omega_mag, oz / omega_mag)
            delta_half = motor_from_axis_angle(axis, omega_mag * dt * 0.5, (0.0, 0.0, 0.0))
        else:
            delta_half = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))
        mid = compose_motors(pose, delta_half)
        delta_t = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (lx * dt, ly * dt, lz * dt))
        mid2 = compose_motors(mid, delta_t)
        new_pose = compose_motors(mid2, delta_half)
        return _wrap_result(new_pose, self.source_id)


class LieRustCgaBackend:
    """Rust cga_rotor3 exp-map step via subprocess — not Python oracle."""

    source_id = BACKEND_LIE_RUST_CGA

    def step(self, pose: Motor, twist: Twist, *, dt: float = 1.0) -> LieStepResult:
        from dogfood_platform.lie_integrator_backend_native_v1 import run_lie_integrator_step_native

        row = run_lie_integrator_step_native(
            pose=pose_dict_from_motor(pose),
            omega_rad=twist.omega_rad,
            linear_m=twist.linear_m,
            dt=dt,
            build=True,
        )
        out_pose = motor_from_dict(row["pose"])
        return LieStepResult(
            pose=out_pose,
            source_id=self.source_id,
            quat_norm=float(row["quat_norm"]),
            rotation_frobenius_err=float(row["rotation_frobenius_err"]),
            on_manifold=bool(row["on_manifold"]),
        )


def motor_dict_from_motor(m: Motor) -> dict[str, float]:
    return {
        "qw": m.qw,
        "qx": m.qx,
        "qy": m.qy,
        "qz": m.qz,
        "tx": m.tx,
        "ty": m.ty,
        "tz": m.tz,
    }


def pose_dict_from_motor(m: Motor) -> dict[str, float]:
    return motor_dict_from_motor(m)


def _distance3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _motor_origin(m: Motor) -> tuple[float, float, float]:
    return (m.tx, m.ty, m.tz)


def _project_to_sphere(
    body: Motor,
    center: tuple[float, float, float],
    radius: float,
) -> Motor:
    ox, oy, oz = _motor_origin(body)
    cx, cy, cz = center
    dx, dy, dz = ox - cx, oy - cy, oz - cz
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    if dist < 1e-12:
        return Motor(body.qw, body.qx, body.qy, body.qz, cx + radius, cy, cz)
    s = radius / dist
    return Motor(body.qw, body.qx, body.qy, body.qz, cx + dx * s, cy + dy * s, cz + dz * s)


class LieSphereOrbitBackend:
    """Constraint-by-construction: rotate on SO(3) then project translation to sphere."""

    source_id = BACKEND_LIE_SPHERE_ORBIT

    def __init__(self, *, center: tuple[float, float, float] = (0.0, 0.0, 0.0), radius: float = 2.0) -> None:
        self.center = center
        self.radius = radius

    def step(self, pose: Motor, twist: Twist, *, dt: float = 1.0) -> LieStepResult:
        rot_only = LieExpMapBackend().step(
            Motor(pose.qw, pose.qx, pose.qy, pose.qz, 0.0, 0.0, 0.0),
            Twist(omega_rad=twist.omega_rad, linear_m=(0.0, 0.0, 0.0)),
            dt=dt,
        )
        body = Motor(rot_only.pose.qw, rot_only.pose.qx, rot_only.pose.qy, rot_only.pose.qz, pose.tx, pose.ty, pose.tz)
        projected = _project_to_sphere(body, self.center, self.radius)
        return _wrap_result(projected, self.source_id)


class EuclideanBadInjectBackend:
    """Falsifier — linear add on quaternion components (PhysX/MuJoCo crutch pattern)."""

    source_id = BACKEND_EUCLIDEAN_BAD

    def step(self, pose: Motor, twist: Twist, *, dt: float = 1.0) -> LieStepResult:
        ox, oy, oz = twist.omega_rad
        lx, ly, lz = twist.linear_m
        bad = Motor(
            pose.qw + ox * dt * 0.02,
            pose.qx + ox * dt,
            pose.qy + oy * dt,
            pose.qz + oz * dt,
            pose.tx + lx * dt,
            pose.ty + ly * dt,
            pose.tz + lz * dt,
        )
        return _wrap_result(bad, self.source_id)


def integrate_chain(
    backend: LieIntegratorPort,
    *,
    steps: int,
    twist: Twist,
    dt: float = 1.0,
    pose0: Motor | None = None,
) -> list[LieStepResult]:
    pose = pose0 or Motor(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    out: list[LieStepResult] = []
    for _ in range(steps):
        row = backend.step(pose, twist, dt=dt)
        out.append(row)
        pose = row.pose
    return out


def validate_lie_integrator_falsifiers(
    good: LieStepResult,
    bad: LieStepResult,
    *,
    steps: int,
) -> dict[str, Any]:
    checks = {
        "F_good_on_manifold": good.on_manifold,
        "F_good_quat_unit": abs(good.quat_norm - 1.0) <= MANIFOLD_QUAT_TOL,
        "F_bad_off_manifold": not bad.on_manifold,
        "F_bad_quat_drift": abs(bad.quat_norm - 1.0) >= BAD_DRIFT_MIN,
        "F_sources_distinct": good.source_id != bad.source_id,
        "F_chain_steps": steps >= 8,
    }
    fail = [k for k, v in checks.items() if not v]
    return {"checks": checks, "fail": fail, "pass": len(fail) == 0}


def _pendulum_energy(angle: float, angle_dot: float, *, length: float = 0.5, mass: float = 1.0, g: float = 9.81) -> float:
    height = -length * math.cos(angle)
    return 0.5 * mass * length * length * angle_dot * angle_dot + mass * g * height


def _symplectic_pendulum_chain(steps: int, *, dt: float = 0.01) -> float:
    """1D pendulum Störmer–Verlet — bounded energy drift metric."""
    angle = 0.4
    angle_dot = 0.0
    length = 0.5
    mass = 1.0
    g = 9.81
    e0 = _pendulum_energy(angle, angle_dot, length=length, mass=mass, g=g)
    max_rel = 0.0
    for _ in range(steps):
        torque = -mass * g * length * math.sin(angle)
        alpha = torque / (mass * length * length)
        angle_dot += alpha * dt * 0.5
        angle += angle_dot * dt
        torque = -mass * g * length * math.sin(angle)
        alpha = torque / (mass * length * length)
        angle_dot += alpha * dt * 0.5
        e = _pendulum_energy(angle, angle_dot, length=length, mass=mass, g=g)
        if abs(e0) > 1e-12:
            max_rel = max(max_rel, abs((e - e0) / e0))
    return max_rel


def _euler_pendulum_chain(steps: int, *, dt: float = 0.01) -> float:
    angle = 0.4
    angle_dot = 0.0
    length = 0.5
    mass = 1.0
    g = 9.81
    e0 = _pendulum_energy(angle, angle_dot, length=length, mass=mass, g=g)
    max_rel = 0.0
    for _ in range(steps):
        torque = -mass * g * length * math.sin(angle)
        alpha = torque / (mass * length * length)
        angle_dot += alpha * dt
        angle += angle_dot * dt
        e = _pendulum_energy(angle, angle_dot, length=length, mass=mass, g=g)
        if abs(e0) > 1e-12:
            max_rel = max(max_rel, abs((e - e0) / e0))
    return max_rel


def run_constraint_integrity_falsifier(*, steps: int = 40, dt: float = 0.08) -> dict[str, Any]:
    """Rope-on-sphere: good projects radius · bad Euclidean inject drifts."""
    center = (0.0, 0.0, 0.0)
    radius = 2.0
    twist = Twist(omega_rad=(0.0, 0.0, 0.35), linear_m=(0.04, 0.02, 0.01))
    good0 = Motor(1.0, 0.0, 0.0, 0.0, radius, 0.0, 0.0)
    bad0 = Motor(1.0, 0.0, 0.0, 0.0, radius, 0.0, 0.0)
    good_backend = LieSphereOrbitBackend(center=center, radius=radius)
    bad_backend = EuclideanBadInjectBackend()
    good_pose = good0
    bad_pose = bad0
    good_err = 0.0
    bad_err = 0.0
    for _ in range(steps):
        good_pose = good_backend.step(good_pose, twist, dt=dt).pose
        bad_pose = bad_backend.step(bad_pose, twist, dt=dt).pose
        good_err = abs(_distance3(_motor_origin(good_pose), center) - radius)
        bad_err = abs(_distance3(_motor_origin(bad_pose), center) - radius)
    checks = {
        "F_good_constraint_bounded": good_err <= CONSTRAINT_TOL_GOOD,
        "F_bad_constraint_drift": bad_err >= CONSTRAINT_TOL_BAD,
        "F_good_on_manifold": manifold_metrics(good_pose)[2],
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "receipt_id": "LIE_CONSTRAINT_INTEGRITY_RECEIPT_v1",
        "verdict": "LIE_CONSTRAINT_PASS" if len(fail) == 0 else "LIE_CONSTRAINT_FAIL",
        "steps": steps,
        "radius_m": radius,
        "good_constraint_err": round(good_err, 6),
        "bad_constraint_err": round(bad_err, 6),
        "checks": checks,
        "fail": fail,
        "pass": len(fail) == 0,
    }


def run_symplectic_energy_falsifier(*, steps: int = 400, dt: float = 0.01) -> dict[str, Any]:
    sym_drift = _symplectic_pendulum_chain(steps, dt=dt)
    euler_drift = _euler_pendulum_chain(steps, dt=dt)
    checks = {
        "F_symplectic_bounded": sym_drift <= PENDULUM_ENERGY_DRIFT_MAX_SYMP,
        "F_euler_worse_than_symplectic": euler_drift > sym_drift * 10.0,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "receipt_id": "LIE_SYMPLECTIC_ENERGY_RECEIPT_v1",
        "verdict": "LIE_SYMPLECTIC_ENERGY_PASS" if len(fail) == 0 else "LIE_SYMPLECTIC_ENERGY_FAIL",
        "symplectic_max_rel_drift": round(sym_drift, 6),
        "euler_max_rel_drift": round(euler_drift, 6),
        "checks": checks,
        "fail": fail,
        "pass": len(fail) == 0,
    }


def run_multibody_g5_falsifier(*, steps: int = 400, dt: float = 0.01, rust_build: bool = True) -> dict[str, Any]:
    """2-link double pendulum symplectic energy — Rust subprocess G5 slice."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    bin_name = "lie_multibody_step"
    exe = bin_name + (".exe" if sys.platform == "win32" else "")
    bin_path = repo / "target" / "release" / exe
    if rust_build and not bin_path.is_file():
        subprocess.run(
            ["cargo", "build", "-p", "universe_kinematic", "--bin", bin_name, "--release"],
            cwd=repo,
            check=True,
        )
    payload = {
        "steps": steps,
        "dt": dt,
        "theta1": 0.35,
        "theta2": 0.65,
        "theta1_dot": 0.0,
        "theta2_dot": 0.0,
    }
    err: str | None = None
    row: dict[str, Any] | None = None
    try:
        proc = subprocess.run(
            [str(bin_path)],
            input=json.dumps(payload),
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        row = json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
    drift = float(((row or {}).get("report") or {}).get("max_rel_drift") or 999.0)
    verdict = str((row or {}).get("verdict") or "")
    checks = {
        "F_multibody_subprocess": row is not None,
        "F_multibody_energy_bounded": drift <= MULTIBODY_G5_DRIFT_MAX,
        "F_multibody_verdict": verdict == "LIE_MULTIBODY_G5_PASS",
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "receipt_id": "LIE_MULTIBODY_G5_RECEIPT_v1",
        "verdict": "LIE_MULTIBODY_G5_PASS" if len(fail) == 0 else "LIE_MULTIBODY_G5_FAIL",
        "steps": steps,
        "dt": dt,
        "max_rel_drift": round(drift, 6),
        "rust_row": row,
        "rust_error": err,
        "checks": checks,
        "fail": fail,
        "pass": len(fail) == 0,
        "honesty": {"not_newton_x_platform": True, "two_link_planar_only": True},
    }


def run_lie_integrator_harness_v2(*, rust_build: bool = True) -> dict[str, Any]:
    dual = run_lie_integrator_dual_run()
    sym = run_symplectic_energy_falsifier()
    constraint = run_constraint_integrity_falsifier()
    multibody = run_multibody_g5_falsifier(rust_build=rust_build)
    twist = Twist(omega_rad=(0.1, 0.05, 0.03), linear_m=(0.2, 0.0, 0.0))
    pose0 = Motor(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    py_row = LieSymplecticSplitBackend().step(pose0, twist, dt=0.1)
    rust_ok = False
    rust_row: dict[str, Any] | None = None
    rust_err: str | None = None
    try:
        rust_backend = LieRustCgaBackend()
        if rust_build:
            rust_result = rust_backend.step(pose0, twist, dt=0.1)
            rust_row = rust_result.to_row()
            rust_ok = rust_result.on_manifold
    except Exception as exc:  # noqa: BLE001 — honesty receipt on build fail
        rust_err = str(exc)
    checks = {
        "F_dual_run": dual.get("verdict") == "LIE_INTEGRATOR_PORT_PASS",
        "F_symplectic_energy": sym.get("verdict") == "LIE_SYMPLECTIC_ENERGY_PASS",
        "F_constraint_integrity": constraint.get("verdict") == "LIE_CONSTRAINT_PASS",
        "F_multibody_g5": multibody.get("verdict") == "LIE_MULTIBODY_G5_PASS",
        "F_symplectic_split_manifold": py_row.on_manifold,
        "F_rust_backend": rust_ok,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "receipt_id": "LIE_INTEGRATOR_HARNESS_V2_RECEIPT_v1",
        "verdict": "LIE_INTEGRATOR_HARNESS_PASS" if len(fail) == 0 else "LIE_INTEGRATOR_HARNESS_FAIL",
        "proof_tier": PROOF_TIER,
        "dual_run": dual,
        "symplectic_energy": sym,
        "constraint_integrity": constraint,
        "multibody_g5": multibody,
        "symplectic_split_tail": py_row.to_row(),
        "rust_tail": rust_row,
        "rust_error": rust_err,
        "checks": checks,
        "fail": fail,
        "pass": len(fail) == 0,
        "honesty": {
            "not_newton_x_platform": True,
            "rust_is_subprocess": True,
            "symplectic_is_host_pendulum": True,
        },
    }


def run_lie_integrator_dual_run(*, write: bool = False) -> dict[str, Any]:
    twist = Twist(omega_rad=(0.35, 0.12, 0.08), linear_m=(0.5, 0.0, 0.0))
    steps = 24
    good_chain = integrate_chain(LieExpMapBackend(), steps=steps, twist=twist, dt=0.1)
    bad_chain = integrate_chain(EuclideanBadInjectBackend(), steps=steps, twist=twist, dt=0.1)
    good = good_chain[-1]
    bad = bad_chain[-1]
    fals = validate_lie_integrator_falsifiers(good, bad, steps=steps)
    return {
        "receipt_id": "LIE_INTEGRATOR_DUAL_RUN_RECEIPT_v1",
        "verdict": "LIE_INTEGRATOR_PORT_PASS" if fals["pass"] else "LIE_INTEGRATOR_PORT_FAIL",
        "proof_tier": PROOF_TIER,
        "contract": CONTRACT_PATH,
        "steps": steps,
        "twist": {"omega_rad": twist.omega_rad, "linear_m": twist.linear_m},
        "good_tail": good.to_row(),
        "bad_tail": bad.to_row(),
        "falsifiers": fals,
        "honesty": {
            "not_newton_x_platform": True,
            "not_symplectic_crown": True,
            "not_measured": True,
            "bad_is_euclidean_inject": True,
        },
        "tabu": "claim Newton-X built · claim symplectic multibody · normalize crutch as prod",
    }


LUNAR_LIE_DEFAULT_PROFILES = frozenset({"lunar_crater_5km"})


def init_lie_integrator_bind(
    state: dict[str, Any],
    *,
    enabled: bool = True,
    backend: str = BACKEND_LIE_SYMPLECTIC_SPLIT,
) -> dict[str, Any]:
    state["lie_integrator"] = {
        "enabled": bool(enabled),
        "backend": str(backend),
        "contract": CONTRACT_PATH,
        "proof_tier": PROOF_TIER,
    }
    return state


def ensure_lie_integrator_bind(state: dict[str, Any], *, profile_id: str) -> dict[str, Any]:
    """Idempotent lunar dogfood default — symplectic Lie traverse unless operator set lie_integrator."""
    if "lie_integrator" in state:
        return state["lie_integrator"]
    if profile_id not in LUNAR_LIE_DEFAULT_PROFILES:
        return {}
    return init_lie_integrator_bind(state, enabled=True, backend=BACKEND_LIE_SYMPLECTIC_SPLIT)


def resolve_lie_integrator_port(state: dict[str, Any]) -> LieIntegratorPort:
    cfg = state.get("lie_integrator") or {}
    backend = str(cfg.get("backend") or BACKEND_LIE_SYMPLECTIC_SPLIT)
    if backend == BACKEND_EUCLIDEAN_BAD:
        return EuclideanBadInjectBackend()
    if backend == BACKEND_LIE_SYMPLECTIC_SPLIT:
        return LieSymplecticSplitBackend()
    if backend == BACKEND_LIE_RUST_CGA:
        return LieRustCgaBackend()
    if backend == BACKEND_LIE_SPHERE_ORBIT:
        radius = float(cfg.get("constraint_radius_m") or 2.0)
        return LieSphereOrbitBackend(radius=radius)
    return LieExpMapBackend()


def relative_pose_from_carrier(
    carrier: dict[str, Any],
    *,
    segment_start_m: float,
) -> Motor:
    row = carrier.get("lie_pose_motor")
    if isinstance(row, dict) and row.get("qw") is not None:
        return motor_from_dict(row)
    tx = float(carrier.get("cursor_m", segment_start_m)) - float(segment_start_m)
    return Motor(1.0, 0.0, 0.0, 0.0, tx, 0.0, 0.0)


def lie_integrator_enabled(state: dict[str, Any]) -> bool:
    return bool((state.get("lie_integrator") or {}).get("enabled"))


def lie_tick_snapshot(state: dict[str, Any], carrier_id: str) -> dict[str, Any]:
    """Post-kernel Lie pose row for coupling cell / chip ACT_IN state_bus."""
    if not lie_integrator_enabled(state):
        return {"lie_kernel_active": False}
    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    pose = carrier.get("lie_pose_motor")
    seg_start = float(carrier.get("segment_start_m") or 0.0)
    cursor = float(carrier.get("cursor_m") or 0.0)
    if not isinstance(pose, dict) or pose.get("qw") is None:
        return {
            "lie_kernel_active": True,
            "lie_integrator_backend": carrier.get("lie_integrator_backend"),
            "lie_pose_present": False,
            "cursor_m": cursor,
            "segment_start_m": seg_start,
            "match_lie_pose": None,
        }
    tx = float(pose.get("tx") or 0.0)
    expected = seg_start + tx
    return {
        "lie_kernel_active": True,
        "lie_integrator_backend": carrier.get("lie_integrator_backend"),
        "lie_on_manifold": carrier.get("lie_on_manifold"),
        "lie_quat_norm": carrier.get("lie_quat_norm"),
        "lie_pose_present": True,
        "lie_pose_tx_m": round(tx, 6),
        "cursor_m": round(cursor, 6),
        "segment_start_m": seg_start,
        "lie_expected_cursor_m": round(expected, 6),
        "match_lie_pose": abs(expected - cursor) < 0.01,
    }


def advance_traverse_segment_lie(
    state: dict[str, Any],
    carrier: dict[str, Any],
    *,
    step_m: float,
    omega_rad: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> LieStepResult:
    """One kernel tick — Lie step along segment +X, cursor from relative tx."""
    port = resolve_lie_integrator_port(state)
    seg_start = float(carrier.get("segment_start_m", 0.0))
    pose = relative_pose_from_carrier(carrier, segment_start_m=seg_start)
    twist = Twist(omega_rad=omega_rad, linear_m=(step_m, 0.0, 0.0))
    result = port.step(pose, twist, dt=1.0)
    carrier["lie_pose_motor"] = result.pose_dict()
    carrier["lie_integrator_backend"] = result.source_id
    carrier["lie_quat_norm"] = round(result.quat_norm, 6)
    carrier["lie_on_manifold"] = result.on_manifold
    carrier["cursor_m"] = seg_start + result.pose.tx
    return result


if __name__ == "__main__":
    import json
    import sys

    r = run_lie_integrator_dual_run()
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["verdict"] == "LIE_INTEGRATOR_PORT_PASS" else 1)
