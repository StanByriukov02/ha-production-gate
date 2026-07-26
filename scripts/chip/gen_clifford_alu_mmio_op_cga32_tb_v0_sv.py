"""Generate clifford_alu_mmio_op_cga32_tb_v0.v — MMIO OP_CGA32 motor512 iron smoke."""
from __future__ import annotations

from pathlib import Path

_OUT = Path(__file__).resolve().parents[2] / "fixtures" / "chip" / "clifford_alu_mmio_op_cga32_tb_v0.v"


def _words512(hex512: str) -> list[int]:
    h = hex512.lower().replace("0x", "").zfill(128)
    return [int(h[128 - 8 * (i + 1) : 128 - 8 * i], 16) for i in range(16)]


def main() -> None:
    import sys

    _repo = Path(__file__).resolve().parents[2]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))
    from scripts.chip.clifford_cga32_oracle_v1 import Cga32Motor
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    id_a = DqMotor.identity()
    t_b = DqMotor.from_se3(1.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0)
    a = Cga32Motor.from_dq_motor128(id_a.to_motor128_hex())
    b = Cga32Motor.from_dq_motor128(t_b.to_motor128_hex())
    exp = a.geo_prod(b)
    aw = _words512(a.to_motor512_hex())
    bw = _words512(b.to_motor512_hex())
    ew = _words512(exp.to_motor512_hex())

    load_rs1 = "\n".join(
        f"    mmio_write(6'h39, 32'd{i}); mmio_write(6'h0C, 32'h{aw[i]:08x});" for i in range(16)
    )
    load_rs2 = "\n".join(
        f"    mmio_write(6'h39, 32'd{i}); mmio_write(6'h1C, 32'h{bw[i]:08x});" for i in range(16)
    )
    read_rd = "\n".join(
        f"    mmio_write(6'h39, 32'd{i}); mmio_read(6'h2C, rd[{i}]);" for i in range(16)
    )
    exp_checks = " && ".join(f"rd[{i}] === 32'h{ew[i]:08x}" for i in range(16))
    exp_display = ", ".join(f"32'h{ew[i]:08x}" for i in reversed(range(16)))

    text = f"""// MMIO OP_CGA32_GEO_PROD iron TB — oracle gold id * trans (motor512)
// Regenerate: python scripts/chip/gen_clifford_alu_mmio_op_cga32_tb_v0_sv.py
`timescale 1ns/1ps
`include "clifford_alu_v0_pkg.vh"

module clifford_alu_mmio_op_cga32_tb_v0;
  reg clk;
  reg rst;
  reg reg_wen;
  reg reg_ren;
  reg [5:0] reg_addr;
  reg [31:0] reg_wdata;
  wire [31:0] reg_rdata;

  integer cyc;
  reg [31:0] rd [0:15];

  clifford_alu_mmio_cga32_v0 dut (
      .clk(clk),
      .rst(rst),
      .reg_wen(reg_wen),
      .reg_ren(reg_ren),
      .reg_addr(reg_addr),
      .reg_wdata(reg_wdata),
      .reg_rdata(reg_rdata)
  );

  initial clk = 1'b0;
  always #5 clk = ~clk;

  task automatic mmio_write(input [5:0] addr, input [31:0] data);
    begin
      @(posedge clk);
      reg_addr  = addr;
      reg_wdata = data;
      reg_wen   = 1'b1;
      reg_ren   = 1'b0;
      @(posedge clk);
      reg_wen   = 1'b0;
    end
  endtask

  task automatic mmio_read(input [5:0] addr, output [31:0] data);
    begin
      @(posedge clk);
      reg_addr = addr;
      reg_ren  = 1'b1;
      reg_wen  = 1'b0;
      @(posedge clk);
      data     = reg_rdata;
      reg_ren  = 1'b0;
    end
  endtask

  reg [31:0] st;

  initial begin
    rst = 1'b1;
    reg_wen = 1'b0;
    reg_ren = 1'b0;
    reg_addr = 6'd0;
    reg_wdata = 32'd0;
    #20 rst = 1'b0;

    mmio_write(6'h08, 32'd4);  // OP_CGA32_GEO_PROD
{load_rs1}
{load_rs2}
    mmio_write(6'h00, 32'd1);  // START

    cyc = 0;
    while (cyc < 40) begin
      @(posedge clk);
      mmio_read(6'h04, st);
      if (st[2]) cyc = 100;
      cyc = cyc + 1;
    end

{read_rd}

    if ({exp_checks}) begin
      $display("TB_PASS mmio_op_cga32 id_trans");
      $finish(0);
    end else begin
      $display("TB_FAIL mmio_op_cga32 st=%h exp=%s", st, "{exp_display}");
      $finish(1);
    end
  end
endmodule
"""
    _OUT.write_text(text, encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
