"""Mint combat world-motion vectors + RTL iron TB (vector glue only — geo_prod on iron/cxx)."""
from __future__ import annotations

import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_COMBAT = _REPO / "fixtures" / "robot" / "m_combat_earth_traverse_tick_stream_v1.json"
_VEC_JSON = _REPO / "fixtures" / "chip" / "clifford_world_motion_vectors_v1.json"
_VEC_BIN = _REPO / "fixtures" / "chip" / "clifford_world_motion_vectors_v1.bin"
_RTL_TB = _REPO / "fixtures" / "chip" / "clifford_world_motion_rtl_tb_v0.v"

_TRAVERSE_M = 500.0
_BODY_REF_M = (0.31, 0.0, 0.21)
_THETA_SCALE = math.pi * 0.35


def _load_oracle():
    path = _REPO / "scripts" / "chip" / "clifford_pga8_oracle_v0.py"
    spec = importlib.util.spec_from_file_location("clifford_pga8_oracle_v0", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _motor_hex(coeffs: list[int]) -> str:
    w = 0
    for i, c in enumerate(coeffs):
        w |= (int(c) & 0xFFFF) << (16 * i)
    return f"{w:032x}"


def _pack_motor(coeffs: list[int]) -> bytes:
    return struct.pack("<8H", *[int(c) & 0xFFFF for c in coeffs])


def mint_world_motion_vectors() -> dict:
    oracle = _load_oracle()
    combat = json.loads(_COMBAT.read_text(encoding="utf-8"))
    ticks_in = list(combat.get("ticks") or [])
    bx, by, bz = _BODY_REF_M
    point = oracle.motor_from_blades(e1=bx, e2=by, e3=bz)
    point_hex = _motor_hex(point)

    rows: list[dict] = []
    bin_chunks: list[bytes] = [struct.pack("<I", len(ticks_in))]
    for t in ticks_in:
        tick_i = int(t["tick"])
        meters = float(t["meters"])
        theta = (meters / _TRAVERSE_M) * _THETA_SCALE
        half = theta * 0.5
        rotor = oracle.motor_from_blades(s=math.cos(half), e12=-math.sin(half))
        rev = oracle.reverse_coeffs(rotor)
        rotor_hex = _motor_hex(rotor)
        rev_hex = _motor_hex(rev)
        rows.append(
            {
                "tick": tick_i,
                "meters": meters,
                "theta_rad": theta,
                "rotor_hex": rotor_hex,
                "rev_hex": rev_hex,
                "point_hex": point_hex,
            }
        )
        bin_chunks.append(
            struct.pack("<If", tick_i, meters)
            + _pack_motor(rotor)
            + _pack_motor(point)
            + _pack_motor(rev)
        )

    doc = {
        "vector_id": "clifford_world_motion_vectors_v1",
        "traverse_m": _TRAVERSE_M,
        "body_ref_m": list(_BODY_REF_M),
        "theta_scale": _THETA_SCALE,
        "point_hex": point_hex,
        "tick_count": len(rows),
        "ticks": rows,
        "mint_role": "bf16_hex_glue_only",
        "compute_layers": ["iron_rtl_mmio", "cxx_rigid_pose"],
    }
    _VEC_JSON.parent.mkdir(parents=True, exist_ok=True)
    _VEC_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    _VEC_BIN.write_bytes(b"".join(bin_chunks))
    return doc


def write_world_motion_rtl_tb(vectors: dict) -> Path:
    ticks = vectors["ticks"]
    n = len(ticks)
    rotor_lines = "\n".join(
        f"    rotor_motor[{i}] = 128'h{t['rotor_hex']};" for i, t in enumerate(ticks)
    )
    rev_lines = "\n".join(
        f"    rev_motor[{i}] = 128'h{t['rev_hex']};" for i, t in enumerate(ticks)
    )
    point_hex = vectors["point_hex"]
    body = f"""// World motion RTL iron TB — generated · 2× GEO_PROD MMIO per combat tick
// Regenerate: python scripts/chip/gen_clifford_world_motion_iron_v0.py
`timescale 1ns/1ps
`include "clifford_alu_v0_pkg.vh"
`include "clifford_bf16_ops_v0.vh"

module clifford_world_motion_rtl_tb_v0;
  localparam integer N_TICKS = {n};
  localparam [127:0] POINT_MOTOR = 128'h{point_hex};

  reg clk;
  reg rst;
  reg reg_wen;
  reg reg_ren;
  reg [5:0] reg_addr;
  reg [31:0] reg_wdata;
  wire [31:0] reg_rdata;

  reg [127:0] rotor_motor [0:N_TICKS-1];
  reg [127:0] rev_motor [0:N_TICKS-1];
  integer tick_ids [0:N_TICKS-1];
  real tick_meters [0:N_TICKS-1];
  integer ti;
  integer cyc;
  reg [127:0] tmp_motor;
  reg [127:0] out_motor;
  reg [31:0] st;

  clifford_alu_mmio_v0 dut (
      .clk(clk), .rst(rst),
      .reg_wen(reg_wen), .reg_ren(reg_ren),
      .reg_addr(reg_addr), .reg_wdata(reg_wdata), .reg_rdata(reg_rdata)
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
    reg_wen = 1'b0; reg_ren = 1'b0;
    reg_addr = 6'd0; reg_wdata = 32'd0;
{rotor_lines}
{rev_lines}
"""
    tick_id_lines = "\n".join(
        f"    tick_ids[{i}] = {t['tick']};" for i, t in enumerate(ticks)
    )
    mvals = [f"      mvals[{i}] = {t['meters']:.6f};" for i, t in enumerate(ticks)]
    body += tick_id_lines + "\n"
    body += """    begin : init_meters
      integer mi;
      real mvals [0:N_TICKS-1];
"""
    body += "\n".join(mvals)
    body += """
      for (mi = 0; mi < N_TICKS; mi = mi + 1) begin
        tick_meters[mi] = mvals[mi];
      end
    end
    #20 rst = 1'b0;
    for (ti = 0; ti < N_TICKS; ti = ti + 1) begin
      run_geo_prod(rotor_motor[ti], POINT_MOTOR, tmp_motor);
      run_geo_prod(tmp_motor, rev_motor[ti], out_motor);
      $display("RTL_WORLD_POSE %0d %f %f %f %f",
          tick_ids[ti], tick_meters[ti],
          blade_real_1(out_motor), blade_real_2(out_motor), blade_real_3(out_motor));
    end
    $display("TB_PASS rtl_world_motion");
    $finish(0);
  end
endmodule
"""
    _RTL_TB.write_text(body, encoding="utf-8")
    return _RTL_TB


_STRUCT_TB = _REPO / "fixtures" / "chip" / "clifford_world_motion_structural_rtl_tb_v0.v"
_MAPPED_TB = _REPO / "fixtures" / "chip" / "sta" / "clifford_world_motion_mapped_slice_rtl_tb_v0.v"
_MAPPED_MMIO_TB = _REPO / "fixtures" / "chip" / "sta" / "clifford_world_motion_mapped_mmio_rtl_tb_v0.v"


def write_world_motion_structural_rtl_tb(vectors: dict) -> Path:
    """MMIO TB with gp_synth datapath enabled (synthesizable structural, pre-map)."""
    write_world_motion_rtl_tb(vectors)
    text = _RTL_TB.read_text(encoding="utf-8")
    text = text.replace("clifford_world_motion_rtl_tb_v0", "clifford_world_motion_structural_rtl_tb_v0")
    text = text.replace("TB_PASS rtl_world_motion", "TB_PASS rtl_world_motion_structural")
    text = text.replace(
        "#20 rst = 1'b0;",
        "#20 rst = 1'b0;\n    mmio_write(6'h3E, 32'd1);",
    )
    _STRUCT_TB.write_text(text, encoding="utf-8")
    return _STRUCT_TB


def write_world_motion_mapped_slice_rtl_tb(vectors: dict) -> Path:
    """Mapped Nangate45 geo_prod slice — 2× GEO_PROD per tick (structural netlist)."""
    ticks = vectors["ticks"]
    n = len(ticks)
    rotor_lines = "\n".join(
        f"    rotor_motor[{i}] = 128'h{t['rotor_hex']};" for i, t in enumerate(ticks)
    )
    rev_lines = "\n".join(
        f"    rev_motor[{i}] = 128'h{t['rev_hex']};" for i, t in enumerate(ticks)
    )
    point_hex = vectors["point_hex"]
    tick_id_lines = "\n".join(
        f"    tick_ids[{i}] = {t['tick']};" for i, t in enumerate(ticks)
    )
    mvals = [f"      mvals[{i}] = {t['meters']:.6f};" for i, t in enumerate(ticks)]
    body = f"""// Mapped geo_prod slice world motion TB — Nangate45 structural smoke
`timescale 1ns/1ps
`include "clifford_alu_v0_pkg.vh"
`include "clifford_bf16_ops_v0.vh"

module clifford_world_motion_mapped_slice_rtl_tb_v0;
  localparam integer N_TICKS = {n};
  localparam [127:0] POINT_MOTOR = 128'h{point_hex};

  reg clk, rst;
  reg ex1_latch, ex2_eval, ex2_latch, ex3_eval, ex3_latch, wb_eval;
  reg [`CLIFFORD_MOTOR_W-1:0] a, b;
  wire [`CLIFFORD_MOTOR_W-1:0] r;
  reg [127:0] rotor_motor [0:N_TICKS-1];
  reg [127:0] rev_motor [0:N_TICKS-1];
  integer tick_ids [0:N_TICKS-1];
  real tick_meters [0:N_TICKS-1];
  integer ti;
  reg [127:0] tmp_motor, out_motor;

  clifford_sta_geo_prod_slice_top_v0 dut (
      .clk(clk), .rst(rst), .gp_synth_en(1'b1),
      .ex1_latch(ex1_latch), .ex2_eval(ex2_eval), .ex2_latch(ex2_latch),
      .ex3_eval(ex3_eval), .ex3_latch(ex3_latch), .wb_eval(wb_eval),
      .a(a), .b(b), .r(r)
  );

  initial clk = 1'b0;
  always #5 clk = ~clk;

  // T2.22 — full φ-EX pipeline stimulus (matches clifford_geo_prod_ex_pipe_dual_tb_v0)
  task automatic pulse_geo_prod(input [127:0] ma, input [127:0] mb, output [127:0] rd);
    begin
      a = ma;
      b = mb;
      ex1_latch = 1'b0;
      ex2_eval = 1'b0;
      ex2_latch = 1'b0;
      ex3_eval = 1'b0;
      ex3_latch = 1'b0;
      wb_eval = 1'b0;
      @(posedge clk);
      ex1_latch = 1'b1;
      @(posedge clk);
      ex1_latch = 1'b0;
      repeat (2) @(posedge clk);
      @(posedge clk);
      ex2_eval = 1'b1;
      @(posedge clk);
      ex2_eval = 1'b0;
      @(posedge clk);
      ex2_latch = 1'b1;
      @(posedge clk);
      ex2_latch = 1'b0;
      repeat (2) @(posedge clk);
      @(posedge clk);
      ex3_eval = 1'b1;
      @(posedge clk);
      ex3_eval = 1'b0;
      @(posedge clk);
      ex3_latch = 1'b1;
      @(posedge clk);
      ex3_latch = 1'b0;
      @(posedge clk);
      wb_eval = 1'b1;
      @(posedge clk);
      wb_eval = 1'b0;
      @(posedge clk);
      rd = r;
    end
  endtask

  initial begin
    rst = 1'b1;
{rotor_lines}
{rev_lines}
{tick_id_lines}
    begin : init_meters
      integer mi;
      real mvals [0:N_TICKS-1];
"""
    body += "\n".join(mvals)
    body += """
      for (mi = 0; mi < N_TICKS; mi = mi + 1) tick_meters[mi] = mvals[mi];
    end
    #20 rst = 1'b0;
    for (ti = 0; ti < N_TICKS; ti = ti + 1) begin
      pulse_geo_prod(rotor_motor[ti], POINT_MOTOR, tmp_motor);
      pulse_geo_prod(tmp_motor, rev_motor[ti], out_motor);
      $display("RTL_MAPPED_POSE %0d %f %f %f %f",
          tick_ids[ti], tick_meters[ti],
          blade_real_1(out_motor), blade_real_2(out_motor), blade_real_3(out_motor));
    end
    $display("TB_PASS rtl_world_motion_mapped_slice");
    $finish(0);
  end
endmodule
"""
    _MAPPED_TB.parent.mkdir(parents=True, exist_ok=True)
    _MAPPED_TB.write_text(body, encoding="utf-8")
    return _MAPPED_TB


def write_world_motion_mapped_mmio_rtl_tb(vectors: dict, *, n_ticks: int | None = None) -> Path:
    """Full ALU mapped netlist — MMIO φ-FSM path (H1)."""
    import re

    ticks = vectors["ticks"]
    if n_ticks is not None:
        n = max(1, min(int(n_ticks), len(ticks)))
        vectors = {**vectors, "ticks": ticks[:n]}
    write_world_motion_structural_rtl_tb(vectors)
    text = _STRUCT_TB.read_text(encoding="utf-8")
    text = text.replace("clifford_world_motion_structural_rtl_tb_v0", "clifford_world_motion_mapped_mmio_rtl_tb_v0")
    text = text.replace("TB_PASS rtl_world_motion_structural", "TB_PASS rtl_world_motion_mapped_mmio")
    if n_ticks is not None:
        text = re.sub(
            r"localparam integer N_TICKS = \d+;",
            f"localparam integer N_TICKS = {len(vectors['ticks'])};",
            text,
            count=1,
        )
    header = "// H1 — full ALU mapped MMIO world motion TB (Nangate45 + clifford_alu_mmio_v0)\n"
    _MAPPED_MMIO_TB.parent.mkdir(parents=True, exist_ok=True)
    _MAPPED_MMIO_TB.write_text(header + text, encoding="utf-8")
    return _MAPPED_MMIO_TB


def main() -> None:
    vectors = mint_world_motion_vectors()
    tb = write_world_motion_rtl_tb(vectors)
    print(json.dumps({"vectors": str(_VEC_JSON.name), "rtl_tb": tb.name, "ticks": vectors["tick_count"]}))


if __name__ == "__main__":
    main()
