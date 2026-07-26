"""Generate clifford_geo_prod_cga32_tb_v0.v — oracle-locked motor512 smoke."""
from __future__ import annotations

from pathlib import Path

_OUT = Path(__file__).resolve().parents[2] / "fixtures" / "chip" / "clifford_geo_prod_cga32_tb_v0.v"


def _words512(hex512: str) -> tuple[str, str, str, str, str, str, str, str]:
    h = hex512.lower().replace("0x", "").zfill(128)
    # 8 x 64-bit chunks, MSW first in concat style matching verilog {w7..w0}
    chunks = [h[128 - 16 * (i + 1) : 128 - 16 * i] for i in range(8)]
    return tuple(chunks)  # w0..w7 low to high in motor layout


def _motor512_to_verilog_literal(hex512: str) -> str:
    parts = _words512(hex512)
    return "{" + ", ".join(f"64'h{p}" for p in reversed(parts)) + "}"


def main() -> None:
    import sys

    _repo = Path(__file__).resolve().parents[2]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))
    from scripts.chip.clifford_cga32_oracle_v1 import Cga32Motor
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    id_a = DqMotor.identity()
    t_b = DqMotor.from_se3(1.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0)
    a_id = Cga32Motor.from_dq_motor128(id_a.to_motor128_hex())
    b_id = a_id
    b_t = Cga32Motor.from_dq_motor128(t_b.to_motor128_hex())
    cases = [
        ("cga32_id_id", a_id, b_id, a_id.geo_prod(b_id)),
        ("cga32_id_trans", a_id, b_t, a_id.geo_prod(b_t)),
    ]

    body = ""
    for tag, a, b, exp in cases:
        body += (
            f"    run_case(\n"
            f"      {_motor512_to_verilog_literal(a.to_motor512_hex())},\n"
            f"      {_motor512_to_verilog_literal(b.to_motor512_hex())},\n"
            f"      {_motor512_to_verilog_literal(exp.to_motor512_hex())},\n"
            f'      "{tag}");\n'
        )

    text = f"""// CGA32 motor512 geo_prod TB — oracle gold
// Regenerate: python scripts/chip/gen_clifford_geo_prod_cga32_tb_v0_sv.py
`timescale 1ns/1ps
`include "clifford_alu_v0_pkg.vh"

module clifford_geo_prod_cga32_tb_v0;
  reg [`CLIFFORD_CGA_MOTOR_W-1:0] a, b;
  wire [`CLIFFORD_CGA_MOTOR_W-1:0] r;
  integer n_ok;
  clifford_geo_prod_cga32_v0 u (.a(a), .b(b), .r(r));

  task run_case;
    input [`CLIFFORD_CGA_MOTOR_W-1:0] ta, tb, exp;
    input [255:0] tag;
    begin
      a = ta; b = tb;
      #1;
      if (r !== exp) begin
        $display("TB_FAIL %s sim=%h exp=%h", tag, r, exp);
        $finish(1);
      end
      $display("TB_PASS %s", tag);
      n_ok = n_ok + 1;
    end
  endtask

  initial begin
    n_ok = 0;
{body}
    if (n_ok !== {len(cases)}) begin $display("TB_FAIL case_count"); $finish(1); end
    $display("TB_PASS cga32_motor_smoke cases=%0d", n_ok);
    $finish(0);
  end
endmodule
"""
    _OUT.write_text(text, encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
