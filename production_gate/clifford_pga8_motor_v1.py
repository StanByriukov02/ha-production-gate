"""Canonical PGA8 spatial motor128 — portable engine lever.

Host/runtime motor type for optional Clifford kinematics paths.
Default backend is the pure-Python oracle in this package.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_REPO = Path(__file__).resolve().parents[1]
_BLADE_NAMES = ("s", "e1", "e2", "e3", "e12", "e23", "e31", "e123")


def _load_oracle():
    from production_gate import clifford_pga8_oracle_v0 as mod

    return mod


@dataclass(frozen=True)
class MotorPGA8:
    """Cl(3,0) spatial PGA8 motor — 8×bf16 lanes (motor128 payload)."""

    coeffs: tuple[int, int, int, int, int, int, int, int]

    @classmethod
    def zero(cls) -> MotorPGA8:
        return cls((0,) * 8)

    @classmethod
    def from_hex(cls, hex_str: str) -> MotorPGA8:
        o = _load_oracle()
        c = o.unpack_motor(int(hex_str, 16))
        return cls(tuple(int(x) for x in c))

    @classmethod
    def from_blades(cls, **blades: float) -> MotorPGA8:
        o = _load_oracle()
        return cls(tuple(o.motor_from_blades(**blades)))

    def hex(self) -> str:
        o = _load_oracle()
        return o.motor_hex(list(self.coeffs))

    def as_list(self) -> list[int]:
        return list(self.coeffs)

    def geo_prod(self, other: MotorPGA8) -> MotorPGA8:
        return _dispatch_binary("geo_prod", self, other)

    def sandwich(self, other: MotorPGA8) -> MotorPGA8:
        return _dispatch_binary("sandwich", self, other)

    def reverse(self) -> MotorPGA8:
        backend = os.environ.get("CLIFFORD_BACKEND")
        if backend == "verilator":
            got = _verilator_cli("reverse", self.hex())
            if got:
                return MotorPGA8.from_hex(got)
        if backend == "cxx":
            got = _cxx_cli("reverse", self.hex())
            if got:
                return MotorPGA8.from_hex(got)
        o = _load_oracle()
        return MotorPGA8(tuple(o.reverse_coeffs(self.as_list())))

    def norm(self) -> MotorPGA8:
        return _dispatch_unary("norm", self)

    def rigid_pose(self, point: MotorPGA8) -> MotorPGA8:
        """Pose = gp(gp(R,p), reverse(R)) — LAW, not sandwich."""
        ab = self.geo_prod(point)
        return ab.geo_prod(self.reverse())

    def apply_point_m(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        o = _load_oracle()
        p = MotorPGA8.from_blades(e1=x, e2=y, e3=z)
        out = self.rigid_pose(p)
        return (
            o.bf16_to_f32(out.coeffs[1]),
            o.bf16_to_f32(out.coeffs[2]),
            o.bf16_to_f32(out.coeffs[3]),
        )


def _verilator_cli(cmd: str, a_hex: str, b_hex: str | None = None) -> str | None:
    # Verilator / FPGA host path lives outside this public surface.
    _ = (cmd, a_hex, b_hex)
    return None


def _dispatch_unary(op: str, a: MotorPGA8) -> MotorPGA8:
    backend = os.environ.get("CLIFFORD_BACKEND")
    if backend == "verilator":
        got = _verilator_cli(op, a.hex())
        if got:
            return MotorPGA8.from_hex(got)
    if backend == "cxx":
        got = _cxx_cli(op, a.hex())
        if got:
            return MotorPGA8.from_hex(got)
    o = _load_oracle()
    if op == "norm":
        return MotorPGA8(tuple(o.norm_coeffs(a.as_list())))
    raise ValueError(op)


def _dispatch_binary(op: str, a: MotorPGA8, b: MotorPGA8) -> MotorPGA8:
    backend = os.environ.get("CLIFFORD_BACKEND")
    if backend == "verilator":
        got = _verilator_cli(op, a.hex(), b.hex())
        if got:
            return MotorPGA8.from_hex(got)
    if backend == "cxx":
        got = _cxx_cli(op, a.hex(), b.hex())
        if got:
            return MotorPGA8.from_hex(got)
    o = _load_oracle()
    if op == "geo_prod":
        return MotorPGA8(tuple(o.geo_prod_coeffs(a.as_list(), b.as_list())))
    if op == "sandwich":
        return MotorPGA8(tuple(o.sandwich_coeffs(a.as_list(), b.as_list())))
    raise ValueError(op)


def _cxx_cli(cmd: str, a_hex: str, b_hex: str | None = None) -> str | None:
    from production_gate._clifford_soft_gp_build_v1 import find_exe, cmake_build_clifford_soft_gp

    try:
        build = cmake_build_clifford_soft_gp()
        exe = find_exe(build, "clifford_gp_cli")
        if not exe:
            return None
        line = f"{cmd} {a_hex}" if b_hex is None else f"{cmd} {a_hex} {b_hex}"
        proc = subprocess.run(
            [str(exe)],
            input=line + "\n",
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        import json

        resp = json.loads(proc.stdout.strip().splitlines()[-1])
        return resp.get("rd_hex")
    except Exception:
        return None


def pack_hex(coeffs: Iterable[int]) -> str:
    o = _load_oracle()
    return o.motor_hex([int(c) for c in coeffs])
