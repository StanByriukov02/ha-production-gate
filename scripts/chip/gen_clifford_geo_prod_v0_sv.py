"""Generate clifford_geo_prod_v0.v from Cl(3,0) Cayley table (PGA spatial 8-blade v0)."""
from __future__ import annotations

from pathlib import Path

from scripts.chip.clifford_cayley_v0 import BLADES, cayley_terms

OUT = Path(__file__).resolve().parents[2] / "fixtures" / "chip" / "clifford_geo_prod_v0.v"


def _blade_real(mvar: str, idx: int) -> str:
    return f"blade_real_{idx}({mvar})"


def _term_expr(i: int, j: int, sign: int, a: str = "a", b: str = "b") -> str:
    prod = f"({_blade_real(a, i)} * {_blade_real(b, j)})"
    return f"(-{prod})" if sign < 0 else prod


def main() -> None:
    terms = cayley_terms()
    lines = [
        "// Clifford geo_prod v0 — generated · inlined blade_real_N · verilator-safe",
        "// Regenerate: python scripts/chip/gen_clifford_geo_prod_v0_sv.py",
        "`include \"clifford_alu_v0_pkg.vh\"",
        "`include \"clifford_bf16_ops_v0.vh\"",
        "",
        "module clifford_geo_prod_v0 (",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] a,",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] b,",
        "    output reg  [`CLIFFORD_MOTOR_W-1:0] r",
        ");",
        "",
        "  reg [15:0] out0, out1, out2, out3, out4, out5, out6, out7;",
        "",
        "  always @(*) begin",
    ]

    for k in range(8):
        acc = " + ".join(_term_expr(i, j, s) for i, j, s in terms[k])
        lines.append(f"    out{k} = real_to_bf16({acc});")

    concat_parts = [f"out{k}" for k in range(7, -1, -1)]
    concat = ", ".join(concat_parts)
    lines.append(f"    r = {{ {concat} }};")
    lines.append("  end")
    lines.append("endmodule")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
