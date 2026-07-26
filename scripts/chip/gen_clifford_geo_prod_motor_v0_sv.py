"""Generate clifford_geo_prod_motor_v0.v — even×even rotor compose slice (T2 / T1.5)."""
from __future__ import annotations

from pathlib import Path

from scripts.chip.clifford_cayley_v0 import (
    EVEN_MOTOR_INDICES,
    cayley_terms,
    filter_terms,
    motor_motor_output_indices,
    stats_for_terms,
)

OUT = Path(__file__).resolve().parents[2] / "fixtures" / "chip" / "clifford_geo_prod_motor_v0.v"
SCOPE = "ROTOR_COMPOSE_ONLY · even×even · NOT pose/sandwich/odd operands"


def _blade_real(mvar: str, idx: int) -> str:
    return f"blade_real_{idx}({mvar})"


def _term_expr(i: int, j: int, sign: int, a: str = "a", b: str = "b") -> str:
    prod = f"({_blade_real(a, i)} * {_blade_real(b, j)})"
    return f"(-{prod})" if sign < 0 else prod


def motor_terms() -> dict[int, list[tuple[int, int, int]]]:
    full = cayley_terms()
    outs = motor_motor_output_indices()
    return filter_terms(full, input_indices=EVEN_MOTOR_INDICES, output_indices=outs)


def main() -> None:
    terms = motor_terms()
    stats = stats_for_terms(terms, "even_motor_closed")

    lines = [
        f"// Clifford geo_prod_motor v0 — {SCOPE}",
        "// Regenerate: python scripts/chip/gen_clifford_geo_prod_motor_v0_sv.py",
        "`include \"clifford_alu_v0_pkg.vh\"",
        "`include \"clifford_bf16_ops_v0.vh\"",
        "",
        "module clifford_geo_prod_motor_v0 (",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] a,",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] b,",
        "    output reg  [`CLIFFORD_MOTOR_W-1:0] r",
        ");",
        "",
        "  reg [15:0] out0, out1, out2, out3, out4, out5, out6, out7;",
        "",
        "  always @(*) begin",
    ]

    active = set(motor_motor_output_indices())
    for k in range(8):
        if k in active and terms[k]:
            acc = " + ".join(_term_expr(i, j, s) for i, j, s in terms[k])
            lines.append(f"    out{k} = real_to_bf16({acc});")
        else:
            lines.append(f"    out{k} = 16'h0;")

    concat_parts = [f"out{k}" for k in range(7, -1, -1)]
    lines.append(f"    r = {{ {', '.join(concat_parts)} }};")
    lines.append("  end")
    lines.append("endmodule")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} mul={stats.mul_terms} add={stats.add_terms}")


if __name__ == "__main__":
    main()
