"""Shared helpers for CGA32 SV generation."""
from __future__ import annotations

from scripts.chip.clifford_cga32_cayley_v1 import BLADE_COUNT, cayley_terms


def blade_slice(m: str, idx: int) -> str:
    lo = idx * 16
    return f"{m}[{lo + 15}:{lo}]"


def gen_cga_motor_bf16_ops_vh() -> str:
    lines = [
        "// CGA motor512 bf16 lane helpers — blades 0..31",
        "// Regenerate: python scripts/chip/gen_clifford_geo_prod_cga32_v0_sv.py",
        "`ifndef CLIFFORD_CGA_MOTOR_BF16_OPS_V0_VH",
        "`define CLIFFORD_CGA_MOTOR_BF16_OPS_V0_VH",
        "`include \"clifford_bf16_ops_v0.vh\"",
        "",
    ]
    for i in range(BLADE_COUNT):
        lo = i * 16
        hi = lo + 15
        lines.append(f"  function automatic [15:0] cga_blade_bf16_{i}(input [`CLIFFORD_CGA_MOTOR_W-1:0] m);")
        lines.append(f"    cga_blade_bf16_{i} = m[{hi}:{lo}];")
        lines.append("  endfunction")
        lines.append(f"  function automatic real cga_blade_real_{i}(input [`CLIFFORD_CGA_MOTOR_W-1:0] m);")
        lines.append(f"    cga_blade_real_{i} = bf16_to_real(cga_blade_bf16_{i}(m));")
        lines.append("  endfunction")
        lines.append("")
    lines.append("`endif")
    lines.append("")
    return "\n".join(lines)


def sim_geo_prod_body() -> list[str]:
    terms = cayley_terms()
    lines: list[str] = []
    for out in range(BLADE_COUNT):
        if not terms[out]:
            lines.append(f"    acc_{out} = 0.0;")
            continue
        parts = []
        for i, j, sign in terms[out]:
            prod = f"(cga_blade_real_{i}(a) * cga_blade_real_{j}(b))"
            parts.append(f"(-{prod})" if sign < 0 else prod)
        lines.append(f"    acc_{out} = {' + '.join(parts)};")
    return lines


def unique_ij_pairs() -> list[tuple[int, int]]:
    terms = cayley_terms()
    pairs: set[tuple[int, int]] = set()
    for out in range(BLADE_COUNT):
        for i, j, _ in terms[out]:
            pairs.add((i, j))
    return sorted(pairs)


def synth_mul_name(i: int, j: int) -> str:
    return f"mul_{i}_{j}"


def synth_acc_name(out: int, step: int) -> str:
    return f"acc_o{out}_{step}"
