"""Generate CGA32 motor512 geo_prod sim + synth + bf16 ops."""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_FIX = _REPO / "fixtures" / "chip"
_OPS = _FIX / "clifford_cga_motor_bf16_ops_v0.vh"
_SIM = _FIX / "clifford_geo_prod_cga32_v0.v"
_SYNTH = _FIX / "clifford_geo_prod_cga32_synth_v0.v"


def _write_ops() -> None:
    from scripts.chip._cga32_gen_common_v1 import BLADE_COUNT, gen_cga_motor_bf16_ops_vh

    _OPS.write_text(gen_cga_motor_bf16_ops_vh(), encoding="utf-8")


def _write_sim() -> None:
    from scripts.chip._cga32_gen_common_v1 import BLADE_COUNT, sim_geo_prod_body

    decl = [f"  real acc_{k};" for k in range(BLADE_COUNT)]
    body = sim_geo_prod_body()
    outs = ", ".join(f"real_to_bf16(acc_{k})" for k in reversed(range(BLADE_COUNT)))
    text = "\n".join(
        [
            "// CGA32 motor512 geo_prod — generated from clifford_cga32_cayley_v1",
            "// Regenerate: python scripts/chip/gen_clifford_geo_prod_cga32_v0_sv.py",
            '`include "clifford_alu_v0_pkg.vh"',
            '`include "clifford_cga_motor_bf16_ops_v0.vh"',
            "",
            "module clifford_geo_prod_cga32_v0 (",
            "    input  wire [`CLIFFORD_CGA_MOTOR_W-1:0] a,",
            "    input  wire [`CLIFFORD_CGA_MOTOR_W-1:0] b,",
            "    output reg  [`CLIFFORD_CGA_MOTOR_W-1:0] r",
            ");",
            "",
            *decl,
            "",
            "  always @(*) begin",
            *body,
            f"    r = {{ {outs} }};",
            "  end",
            "endmodule",
            "",
        ]
    )
    _SIM.write_text(text, encoding="utf-8")


def _write_synth() -> None:
    from scripts.chip._cga32_gen_common_v1 import (
        blade_slice,
        synth_acc_name,
        synth_mul_name,
        unique_ij_pairs,
    )
    from scripts.chip.clifford_cga32_cayley_v1 import BLADE_COUNT, cayley_terms

    lines = [
        "// CGA32 motor512 geo_prod synth — yosys probe (phase-2)",
        "// Regenerate: python scripts/chip/gen_clifford_geo_prod_cga32_v0_sv.py",
        '`include "clifford_alu_v0_pkg.vh"',
        "",
        "module clifford_geo_prod_cga32_synth_v0 (",
        "    input  wire [`CLIFFORD_CGA_MOTOR_W-1:0] a,",
        "    input  wire [`CLIFFORD_CGA_MOTOR_W-1:0] b,",
        "    output wire [`CLIFFORD_CGA_MOTOR_W-1:0] r",
        ");",
    ]
    for m in ("a", "b"):
        for i in range(BLADE_COUNT):
            lines.append(f"  wire [15:0] {m}_bf{i} = {blade_slice(m, i)};")

    pairs = unique_ij_pairs()
    for i, j in pairs:
        name = synth_mul_name(i, j)
        lines.append(f"  wire [31:0] f32_{name};")
        lines.append(
            f"  bf16_mul_widen_f32_v0 u_{name} (.a(a_bf{i}), .b(b_bf{j}), .y(f32_{name}));"
        )

    terms = cayley_terms()
    out_bf: list[str] = []
    for out in range(BLADE_COUNT):
        acc = "32'h0"
        step = 0
        for i, j, sign in terms[out]:
            step += 1
            src = f"f32_{synth_mul_name(i, j)}"
            if sign < 0:
                lines.append(f"  wire [31:0] term_o{out}_{step};")
                lines.append(f"  assign term_o{out}_{step} = {src} ^ 32'h80000000;")
                src = f"term_o{out}_{step}"
            an = synth_acc_name(out, step)
            lines.append(f"  wire [31:0] {an};")
            lines.append(f"  f32_add_synth_v0 u_{an} (.a({acc}), .b({src}), .y({an}));")
            acc = an
        ob = f"out_bf{out}"
        lines.append(f"  wire [15:0] {ob};")
        lines.append(f"  f32_to_bf16_rne_v0 u_rne_{out} (.f({acc}), .h({ob}));")
        out_bf.append(ob)

    concat = ", ".join(out_bf[BLADE_COUNT - 1 :: -1])
    lines.append(f"  assign r = {{ {concat} }};")
    lines.append("endmodule")
    lines.append("")
    _SYNTH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    import sys

    _repo = Path(__file__).resolve().parents[2]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))
    _write_ops()
    _write_sim()
    _write_synth()
    print(f"wrote {_OPS.name}, {_SIM.name}, {_SYNTH.name}")


if __name__ == "__main__":
    main()
