#!/usr/bin/env python3
"""JSON stdin/stdout soft session for Rust clifford_device — oracle glue only."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _oracle():
    path = _REPO / "scripts" / "chip" / "clifford_pga8_oracle_v0.py"
    spec = importlib.util.spec_from_file_location("clifford_pga8_oracle_v0", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _motor512_lanes(h: str) -> list[int]:
    w = int(h, 16)
    return [(w >> (16 * i)) & 0xFFFF for i in range(32)]


def main() -> int:
    sys.path.insert(0, str(_REPO))
    req = json.loads(sys.stdin.read())
    cmd = req.get("cmd")
    if cmd == "dq_geo_prod":
        from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

        def _lanes(h: str) -> list[int]:
            w = int(h, 16)
            return [(w >> (16 * i)) & 0xFFFF for i in range(8)]

        a = DqMotor.from_bf16_coeffs(_lanes(req["rs1_hex"]))
        b = DqMotor.from_bf16_coeffs(_lanes(req["rs2_hex"]))
        out = {"rd_hex": a.geo_prod(b).to_motor128_hex()}
        sys.stdout.write(json.dumps(out))
        return 0
    if cmd == "cga32_geo_prod":
        from scripts.chip.clifford_cga32_oracle_v1 import Cga32Motor

        a = Cga32Motor.from_bf16_coeffs(_motor512_lanes(req["rs1_hex"]))
        b = Cga32Motor.from_bf16_coeffs(_motor512_lanes(req["rs2_hex"]))
        out = {"rd_hex": a.geo_prod(b).to_motor512_hex()}
        sys.stdout.write(json.dumps(out))
        return 0

    o = _oracle()
    if cmd == "geo_prod":
        rs1 = o.unpack_motor(int(req["rs1_hex"], 16))
        rs2 = o.unpack_motor(int(req["rs2_hex"], 16))
        out = {"rd_hex": o.geo_prod_hex(rs1, rs2)}
    elif cmd == "sandwich":
        rs1 = o.unpack_motor(int(req["rs1_hex"], 16))
        rs2 = o.unpack_motor(int(req["rs2_hex"], 16))
        out = {"rd_hex": o.sandwich_hex(rs1, rs2)}
    elif cmd == "norm":
        rs1 = o.unpack_motor(int(req["rs1_hex"], 16))
        out = {"rd_hex": o.norm_hex(rs1)}
    elif cmd == "reverse":
        rs1 = o.unpack_motor(int(req["rs1_hex"], 16))
        out = {"rd_hex": o.motor_hex(o.reverse_coeffs(rs1))}
    elif cmd == "rigid_pose":
        sys.path.insert(0, str(_REPO))
        from scripts.chip.clifford_algebra_mode_v0 import (
            AlgebraIntent,
            AlgebraMode,
            execute_chain,
            lower_intent,
        )

        def rev(h: str) -> str:
            m = o.unpack_motor(int(h, 16))
            return o.motor_hex(o.reverse_coeffs(m))

        steps = lower_intent(
            AlgebraMode.KINEMATIC,
            AlgebraIntent.RIGID_POSE,
            req["rotor_hex"],
            req["point_hex"],
            reverse_fn=rev,
        )
        out = {"rd_hex": execute_chain(steps, o)}
    else:
        out = {"error": f"unknown cmd {cmd}"}
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
