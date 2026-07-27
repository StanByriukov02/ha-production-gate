"""PGA8 spatial Cl(3,0) oracle v0 — vector generation glue only (not iron GP).

Used to mint JSON test vectors and verify receipt consistency.
Iron truth remains SystemVerilog clifford_geo_prod_v0.
"""
from __future__ import annotations

import struct
from typing import Iterable

from production_gate.clifford_cayley_v0 import BLADES, BLADE_NAMES, METRIC_SQ, blade_mul

BF16_ONE = 0x3F80
BF16_NEG_ONE = 0xBF80


def bf16_to_f32(h: int) -> float:
    return struct.unpack(">f", struct.pack(">I", int(h) << 16))[0]


def f32_to_bf16(x: float) -> int:
    bits = struct.unpack(">I", struct.pack(">f", float(x)))[0]
    return (bits + 0x7FFF + ((bits >> 16) & 1)) >> 16


def pack_motor(coeffs: Iterable[int]) -> int:
    w = 0
    for i, c in enumerate(coeffs):
        w |= (int(c) & 0xFFFF) << (16 * i)
    return w


def unpack_motor(word: int) -> list[int]:
    return [(word >> (16 * i)) & 0xFFFF for i in range(8)]


def motor_from_blades(**blades: float) -> list[int]:
    coeffs = [0] * 8
    for name, val in blades.items():
        idx = BLADE_NAMES.index(name)
        coeffs[idx] = f32_to_bf16(val)
    return coeffs


def geo_prod_coeffs(a: list[int], b: list[int]) -> list[int]:
    out = [0.0] * 8
    for i in range(8):
        ai = a[i]
        if not ai:
            continue
        ra = bf16_to_f32(ai)
        for j in range(8):
            bj = b[j]
            if not bj:
                continue
            rb = bf16_to_f32(bj)
            sign, blade = blade_mul(BLADES[i], BLADES[j])
            k = BLADES.index(blade)
            out[k] += sign * ra * rb
    return [f32_to_bf16(x) for x in out]


def motor_hex(coeffs: list[int]) -> str:
    return f"{pack_motor(coeffs):032x}"


def geo_prod_hex(rs1: list[int], rs2: list[int]) -> str:
    return motor_hex(geo_prod_coeffs(rs1, rs2))


REV_SIGN = (1, 1, 1, 1, -1, -1, -1, -1)


def reverse_coeffs(a: list[int]) -> list[int]:
    out = []
    for i, c in enumerate(a):
        if not c:
            out.append(0)
            continue
        val = REV_SIGN[i] * bf16_to_f32(c)
        out.append(f32_to_bf16(val))
    return out


def norm_coeffs(a: list[int]) -> list[int]:
    import math

    acc = sum(bf16_to_f32(c) ** 2 for c in a if c)
    if acc == 0.0:
        return [0] * 8
    inv = 1.0 / math.sqrt(acc)
    return [f32_to_bf16(bf16_to_f32(c) * inv) if c else 0 for c in a]


def sandwich_coeffs(a: list[int], b: list[int]) -> list[int]:
    ab = geo_prod_coeffs(a, b)
    rev_a = reverse_coeffs(a)
    ara = geo_prod_coeffs(ab, rev_a)
    return norm_coeffs(ara)


def sandwich_hex(rs1: list[int], rs2: list[int]) -> str:
    return motor_hex(sandwich_coeffs(rs1, rs2))


def norm_hex(rs1: list[int]) -> str:
    return motor_hex(norm_coeffs(rs1))
