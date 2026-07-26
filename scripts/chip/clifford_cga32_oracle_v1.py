"""CGA phase-2 oracle — 32-blade motor512 · embeds DQ motor128."""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from scripts.chip.clifford_cga32_cayley_v1 import BLADE_COUNT, cayley_terms

_REPO = Path(__file__).resolve().parents[2]
_TABLE = _REPO / "fixtures" / "chip" / "clifford_cga32_mul_table_v1.json"

BF16_ONE = 0x3F80


def bf16_to_f32(h: int) -> float:
    return struct.unpack(">f", struct.pack(">I", int(h) << 16))[0]


def f32_to_bf16(x: float) -> int:
    bits = struct.unpack(">I", struct.pack(">f", float(x)))[0]
    return (bits + 0x7FFF + ((bits >> 16) & 1)) >> 16


@dataclass(frozen=True)
class Cga32Motor:
    """32-blade motor512 container (bf16 per blade)."""

    coeffs: tuple[int, ...]  # 32 bf16 values

    @classmethod
    def zero(cls) -> Cga32Motor:
        return cls(tuple(0 for _ in range(BLADE_COUNT)))

    @classmethod
    def from_bf16_coeffs(cls, coeffs: Iterable[int]) -> Cga32Motor:
        c = tuple(int(x) & 0xFFFF for x in coeffs)
        if len(c) != BLADE_COUNT:
            raise ValueError(f"expected {BLADE_COUNT} blades")
        return cls(c)

    @classmethod
    def from_dq_motor128(cls, motor128_hex: str) -> Cga32Motor:
        """Phase-2 embed: motor128 DQ lanes → blades 0..7 (motor subalgebra slot)."""
        from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

        dq = DqMotor.from_bf16_coeffs(_motor128_to_lane_coeffs(motor128_hex))
        c = [0] * BLADE_COUNT
        for i, h in enumerate(dq.to_bf16_coeffs()):
            c[i] = h
        return cls(tuple(c))

    def to_bf16_coeffs(self) -> list[int]:
        return list(self.coeffs)

    def to_motor512_hex(self) -> str:
        w = 0
        for i, h in enumerate(self.coeffs):
            w |= (int(h) & 0xFFFF) << (16 * i)
        return f"{w:0128x}"

    def geo_prod(self, other: Cga32Motor) -> Cga32Motor:
        terms = cayley_terms()
        acc = [0.0] * BLADE_COUNT
        for out in range(BLADE_COUNT):
            s = 0.0
            for i, j, sign in terms[out]:
                s += sign * bf16_to_f32(self.coeffs[i]) * bf16_to_f32(other.coeffs[j])
            acc[out] = s
        return Cga32Motor.from_bf16_coeffs(f32_to_bf16(x) for x in acc)

    def project_dq_motor128(self) -> str:
        """Project blades 0..7 back to motor128 hex (honesty: not full CGA inverse)."""
        from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

        dq = DqMotor.from_bf16_coeffs(self.coeffs[:8])
        return dq.to_motor128_hex()


def _motor128_to_lane_coeffs(hex128: str) -> list[int]:
    h = hex128.lower().replace("0x", "").zfill(32)
    return [int(h[32 - 4 * (i + 1) : 32 - 4 * i], 16) for i in range(8)]


def cga32_geo_prod_hex(a_hex: str, b_hex: str) -> str:
    return Cga32Motor.from_dq_motor128(a_hex).geo_prod(Cga32Motor.from_dq_motor128(b_hex)).to_motor512_hex()


def write_mul_table_fixture(*, write: bool = True) -> dict:
    from scripts.chip.clifford_cga32_cayley_v1 import export_mul_table

    doc = export_mul_table()
    if write:
        _TABLE.parent.mkdir(parents=True, exist_ok=True)
        _TABLE.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def run_cga32_oracle_parity() -> dict:
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    id_a = DqMotor.identity()
    t_b = DqMotor.from_se3(1.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0)
    gold = id_a.geo_prod(t_b).to_motor128_hex()

    a32 = Cga32Motor.from_dq_motor128(id_a.to_motor128_hex())
    b32 = Cga32Motor.from_dq_motor128(t_b.to_motor128_hex())
    got = a32.geo_prod(b32).project_dq_motor128()

    return {
        "verdict": "CGA32_ORACLE_PARITY_PASS" if got == gold else "CGA32_ORACLE_PARITY_FAIL",
        "gold_motor128": gold,
        "got_motor128": got,
        "mul_table": str(_TABLE.relative_to(_REPO)).replace("\\", "/"),
    }
