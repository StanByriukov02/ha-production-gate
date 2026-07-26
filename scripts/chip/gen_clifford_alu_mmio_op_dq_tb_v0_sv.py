"""Generate clifford_alu_mmio_op_dq_tb_v0.v — MMIO OP_DQ iron smoke (oracle gold)."""
from __future__ import annotations

from pathlib import Path

_OUT = Path(__file__).resolve().parents[2] / "fixtures" / "chip" / "clifford_alu_mmio_op_dq_tb_v0.v"


def main() -> None:
    import sys

    _repo = Path(__file__).resolve().parents[2]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    id_a = DqMotor.identity()
    t_b = DqMotor.from_se3(1.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0)
    exp = id_a.geo_prod(t_b)
    exp_hex = exp.to_motor128_hex()

    # motor128 little-endian word layout: rd0 = lanes 0-1, rd1 = lanes 2-3, ...
  # exp_hex is 32 hex chars = 128 bits, MSB-first in string; TB uses same as cga_tb
    w0 = int(exp_hex[24:32], 16)
    w1 = int(exp_hex[16:24], 16)
    w2 = int(exp_hex[8:16], 16)
    w3 = int(exp_hex[0:8], 16)

    a_hex = id_a.to_motor128_hex()
    b_hex = t_b.to_motor128_hex()

    def words(hex128: str) -> tuple[int, int, int, int]:
        return (
            int(hex128[24:32], 16),
            int(hex128[16:24], 16),
            int(hex128[8:16], 16),
            int(hex128[0:8], 16),
        )

    aw0, aw1, aw2, aw3 = words(a_hex)
    bw0, bw1, bw2, bw3 = words(b_hex)

    text = f"""// MMIO OP_DQ_GEO_PROD iron TB — oracle gold id * trans
// Regenerate: python scripts/chip/gen_clifford_alu_mmio_op_dq_tb_v0_sv.py
`timescale 1ns/1ps
`include "clifford_alu_v0_pkg.vh"

module clifford_alu_mmio_op_dq_tb_v0;
  reg clk;
  reg rst;
  reg reg_wen;
  reg reg_ren;
  reg [5:0] reg_addr;
  reg [31:0] reg_wdata;
  wire [31:0] reg_rdata;

  integer cyc;

  clifford_alu_mmio_v0 dut (
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

  reg [31:0] rd0, rd1, rd2, rd3;
  reg [31:0] st;

  initial begin
    rst = 1'b1;
    reg_wen = 1'b0;
    reg_ren = 1'b0;
    reg_addr = 6'd0;
    reg_wdata = 32'd0;
    #20 rst = 1'b0;

    mmio_write(6'h08, 32'd3);  // OP_DQ_GEO_PROD
    mmio_write(6'h0C, 32'h{aw0:08x});
    mmio_write(6'h10, 32'h{aw1:08x});
    mmio_write(6'h14, 32'h{aw2:08x});
    mmio_write(6'h18, 32'h{aw3:08x});
    mmio_write(6'h1C, 32'h{bw0:08x});
    mmio_write(6'h20, 32'h{bw1:08x});
    mmio_write(6'h24, 32'h{bw2:08x});
    mmio_write(6'h28, 32'h{bw3:08x});
    mmio_write(6'h00, 32'd1);  // START

    cyc = 0;
    while (cyc < 40) begin
      @(posedge clk);
      mmio_read(6'h04, st);
      if (st[2]) cyc = 100;
      cyc = cyc + 1;
    end

    mmio_read(6'h2C, rd0);
    mmio_read(6'h30, rd1);
    mmio_read(6'h34, rd2);
    mmio_read(6'h38, rd3);

    if (rd0 === 32'h{w0:08x} && rd1 === 32'h{w1:08x} && rd2 === 32'h{w2:08x} && rd3 === 32'h{w3:08x}) begin
      $display("TB_PASS mmio_op_dq id_trans rd=%h%h%h%h", rd3, rd2, rd1, rd0);
      $finish(0);
    end else begin
      $display("TB_FAIL mmio_op_dq rd=%h%h%h%h exp=%h%h%h%h st=%h",
               rd3, rd2, rd1, rd0, 32'h{w3:08x}, 32'h{w2:08x}, 32'h{w1:08x}, 32'h{w0:08x}, st);
      $finish(1);
    end
  end
endmodule
"""
    _OUT.write_text(text, encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
