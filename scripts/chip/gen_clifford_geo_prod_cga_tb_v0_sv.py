"""Generate clifford_geo_prod_cga_tb_v0.v — oracle-locked CGA motor smoke (T5)."""
from __future__ import annotations

from pathlib import Path

_OUT = Path(__file__).resolve().parents[2] / "fixtures" / "chip" / "clifford_geo_prod_cga_tb_v0.v"


def _case(tag: str, a_hex: str, b_hex: str, exp_hex: str) -> str:
    return (
        f"    run_case(\n"
        f"      128'h{a_hex},\n"
        f"      128'h{b_hex},\n"
        f"      128'h{exp_hex},\n"
        f"      \"{tag}\");\n"
    )


def main() -> None:
    import sys
    from pathlib import Path as _P

    _repo = _P(__file__).resolve().parents[2]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    id_a = DqMotor.identity()
    id_b = DqMotor.identity()
    t_b = DqMotor.from_se3(1.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0)

    cases = [
        ("dq_id_id", id_a, id_b, id_a.geo_prod(id_b)),
        ("dq_id_trans", id_a, t_b, id_a.geo_prod(t_b)),
    ]

    body = "".join(
        _case(tag, a.to_motor128_hex(), b.to_motor128_hex(), exp.to_motor128_hex())
        for tag, a, b, exp in cases
    )

    lines = [
        "// T5 — CGA motor geo_prod iron TB (oracle bf16 gold vs SV)",
        "// Regenerate: python scripts/chip/gen_clifford_geo_prod_cga_tb_v0_sv.py",
        "`timescale 1ns/1ps",
        "`include \"clifford_alu_v0_pkg.vh\"",
        "`include \"clifford_bf16_ops_v0.vh\"",
        "",
        "module clifford_geo_prod_cga_tb_v0;",
        "  reg [127:0] a, b;",
        "  wire [127:0] r;",
        "  integer n_ok;",
        "  clifford_geo_prod_cga_v0 u (.a(a), .b(b), .r(r));",
        "",
        "  task run_case;",
        "    input [127:0] ta, tb, exp;",
        "    input [255:0] tag;",
        "    begin",
        "      a = ta;",
        "      b = tb;",
        "      #1;",
        "      if (r !== exp) begin",
        "        $display(\"TB_FAIL %s sim=%h exp=%h\", tag, r, exp);",
        "        $finish(1);",
        "      end",
        "      $display(\"TB_PASS %s r=%h\", tag, r);",
        "      n_ok = n_ok + 1;",
        "    end",
        "  endtask",
        "",
        "  initial begin",
        "    n_ok = 0;",
        body,
        "    if (n_ok !== 2) begin $display(\"TB_FAIL case_count\"); $finish(1); end",
        "    $display(\"TB_PASS cga_motor_smoke cases=%0d\", n_ok);",
        "    $finish(0);",
        "  end",
        "endmodule",
        "",
    ]
    _OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
