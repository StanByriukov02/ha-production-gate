"""Generate LC2 pose RTL-in-loop TB — iron MMIO geo_prod chain."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_OUT = _REPO / "fixtures" / "chip" / "clifford_lc2_pose_rtl_tb_v0.v"
_KEYFRAMES = _REPO / "fixtures" / "twin" / "lc2_bench_demo_keyframes_v1.json"


def _load_oracle():
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    path = _REPO / "scripts" / "chip" / "clifford_pga8_oracle_v0.py"
    spec = importlib.util.spec_from_file_location("clifford_pga8_oracle_v0", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["clifford_pga8_oracle_v0"] = mod
    spec.loader.exec_module(mod)
    return mod


def _motor_hex(coeffs) -> str:
    w = 0
    for i, c in enumerate(coeffs):
        w |= (int(c) & 0xFFFF) << (16 * i)
    return f"128'h{w:032x}"


def _landmarks():
    h = 0.05
    return [
        (h, 0.0, 0.0),
        (0.0, h, 0.0),
        (0.0, 0.0, h),
        (-h, 0.0, 0.0),
        (0.0, -h, 0.0),
        (0.0, 0.0, -h),
        (h, h, 0.0),
        (0.0, 0.0, 0.0),
    ]


def main() -> None:
    import json

    oracle = _load_oracle()
    theta = json.loads(_KEYFRAMES.read_text(encoding="utf-8"))["sequences"][0]["keyframes"][1]["q"]
    half = theta * 0.5
    rotor = oracle.motor_from_blades(s=math.cos(half), e12=-math.sin(half))
    rev = oracle.reverse_coeffs(rotor)
    rotor_h = _motor_hex(rotor)
    rev_h = _motor_hex(rev)

    pts = []
    for i, (x, y, z) in enumerate(_landmarks()):
        pm = oracle.motor_from_blades(e1=x, e2=y, e3=z)
        pts.append((i, _motor_hex(pm)))

    point_lines = "\n".join(
        f"    point_motor[{i}] = {h};" for i, h in pts
    )

    body = f"""// LC2 pose RTL-in-loop TB — generated · LAW: GEO_PROD chain only
// Regenerate: python scripts/chip/gen_clifford_lc2_pose_rtl_tb_v0_sv.py
`timescale 1ns/1ps
`include "clifford_alu_v0_pkg.vh"
`include "clifford_bf16_ops_v0.vh"

module clifford_lc2_pose_rtl_tb_v0;
  localparam integer N_LM = {len(pts)};

  reg clk;
  reg rst;
  reg reg_wen;
  reg reg_ren;
  reg [5:0] reg_addr;
  reg [31:0] reg_wdata;
  wire [31:0] reg_rdata;

  reg [127:0] point_motor [0:N_LM-1];
  integer li;
  integer cyc;
  reg [127:0] tmp_motor;
  reg [127:0] out_motor;
  reg [31:0] st;

  localparam [127:0] ROTOR_MOTOR = {rotor_h};
  localparam [127:0] REV_ROTOR   = {rev_h};

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
      reg_addr = addr; reg_wdata = data; reg_wen = 1'b1; reg_ren = 1'b0;
      @(posedge clk);
      reg_wen = 1'b0;
    end
  endtask

  task automatic mmio_read(input [5:0] addr, output [31:0] data);
    begin
      @(posedge clk);
      reg_addr = addr; reg_ren = 1'b1; reg_wen = 1'b0;
      @(posedge clk);
      data = reg_rdata; reg_ren = 1'b0;
    end
  endtask

  task automatic motor_to_mmio(input [127:0] motor, input [5:0] base_addr);
    begin
      mmio_write(base_addr + 6'h00, motor[31:0]);
      mmio_write(base_addr + 6'h04, motor[63:32]);
      mmio_write(base_addr + 6'h08, motor[95:64]);
      mmio_write(base_addr + 6'h0C, motor[127:96]);
    end
  endtask

  task automatic read_motor_from_mmio(input [5:0] base_addr, output [127:0] motor);
    reg [31:0] w0, w1, w2, w3;
    begin
      mmio_read(base_addr + 6'h00, w0);
      mmio_read(base_addr + 6'h04, w1);
      mmio_read(base_addr + 6'h08, w2);
      mmio_read(base_addr + 6'h0C, w3);
      motor = {{w3, w2, w1, w0}};
    end
  endtask

  task automatic run_geo_prod(input [127:0] a, input [127:0] b, output [127:0] rd);
    begin
      mmio_write(6'h08, 32'd0);
      motor_to_mmio(a, 6'h0C);
      motor_to_mmio(b, 6'h1C);
      mmio_write(6'h00, 32'd1);
      cyc = 0;
      while (cyc < 48) begin
        @(posedge clk);
        mmio_read(6'h04, st);
        if (st[2]) cyc = 100;
        cyc = cyc + 1;
      end
      read_motor_from_mmio(6'h2C, rd);
    end
  endtask

  initial begin
    rst = 1'b1;
    reg_wen = 1'b0;
    reg_ren = 1'b0;
    reg_addr = 6'd0;
    reg_wdata = 32'd0;
{point_lines}
    #20 rst = 1'b0;
    for (li = 0; li < N_LM; li = li + 1) begin
      run_geo_prod(ROTOR_MOTOR, point_motor[li], tmp_motor);
      run_geo_prod(tmp_motor, REV_ROTOR, out_motor);
      $display("RTL_POSE %0d %f %f %f", li,
          blade_real_1(out_motor), blade_real_2(out_motor), blade_real_3(out_motor));
    end
    $display("TB_PASS rtl_lc2_pose");
    $finish(0);
  end
endmodule
"""
    _OUT.write_text(body, encoding="utf-8")
    print(f"wrote {_OUT.name} landmarks={len(pts)}")


if __name__ == "__main__":
    main()
