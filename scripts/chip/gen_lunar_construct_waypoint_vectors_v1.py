"""Mint lunar construct inter-zone waypoint vectors — oracle + iron RTL + CXX rails."""
from __future__ import annotations

import importlib.util
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_VEC_JSON = _REPO / "fixtures" / "chip" / "lunar_construct_waypoint_vectors_v1.json"
_VEC_BIN = _REPO / "fixtures" / "chip" / "lunar_construct_waypoint_vectors_v1.bin"
_RTL_TB = _REPO / "fixtures" / "chip" / "clifford_lunar_construct_waypoint_rtl_tb_v0.v"
_STRUCT_TB = _REPO / "fixtures" / "chip" / "clifford_lunar_construct_waypoint_structural_rtl_tb_v0.v"
_MAPPED_SLICE_TB = _REPO / "fixtures" / "chip" / "sta" / "clifford_lunar_construct_waypoint_mapped_slice_rtl_tb_v0.v"
_SEGMENT_TICKS = 6


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


def _motors_for_waypoint(oracle: Any, *, x_m: float, y_m: float, z_m: float, theta_rad: float) -> tuple[list[int], list[int], list[int], float, float, float]:
    half = theta_rad * 0.5
    rotor = oracle.motor_from_blades(s=math.cos(half), e12=-math.sin(half))
    rev = oracle.reverse_coeffs(rotor)
    point = oracle.motor_from_blades(e1=x_m, e2=y_m, e3=z_m)
    tmp = oracle.geo_prod_coeffs(rotor, point)
    pose = oracle.geo_prod_coeffs(tmp, rev)
    return (
        rotor,
        rev,
        point,
        oracle.bf16_to_f32(pose[1]),
        oracle.bf16_to_f32(pose[2]),
        oracle.bf16_to_f32(pose[3]),
    )


def build_inter_zone_segments() -> list[dict[str, Any]]:
    from dogfood_platform.lunar_fleet_maneuver_compiler_v1 import build_site_path_graph, _load_policy

    graph = build_site_path_graph(_load_policy())
    nodes = list(graph["nodes"])
    segments: list[dict[str, Any]] = []
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        dx = float(b["x_m"]) - float(a["x_m"])
        dy = float(b["y_m"]) - float(a["y_m"])
        theta = math.atan2(dy, dx)
        segments.append(
            {
                "segment_id": i,
                "zone_from": a["zone_id"],
                "zone_to": b["zone_id"],
                "path_s_start": float(a["path_s"]),
                "path_s_end": float(b["path_s"]),
                "x_start_m": float(a["x_m"]),
                "y_start_m": float(a["y_m"]),
                "x_end_m": float(b["x_m"]),
                "y_end_m": float(b["y_m"]),
                "edge_m": max(math.hypot(dx, dy), 10.0),
                "theta_rad": theta,
            }
        )
    return segments


def mint_lunar_construct_waypoint_vectors(*, write: bool = True) -> dict[str, Any]:
    from dogfood_platform.lunar_fleet_maneuver_compiler_v1 import build_site_path_graph, _load_policy

    oracle = _load_oracle()
    graph = build_site_path_graph(_load_policy())
    segments = build_inter_zone_segments()
    ticks: list[dict[str, Any]] = []
    bin_chunks: list[bytes] = []
    tick_i = 0

    for seg in segments:
        dx = seg["x_end_m"] - seg["x_start_m"]
        dy = seg["y_end_m"] - seg["y_start_m"]
        for step in range(1, _SEGMENT_TICKS + 1):
            frac = step / _SEGMENT_TICKS
            x_m = seg["x_start_m"] + dx * frac
            y_m = seg["y_start_m"] + dy * frac
            path_s = seg["path_s_start"] + (seg["path_s_end"] - seg["path_s_start"]) * frac
            rotor, rev, point, px, py, pz = _motors_for_waypoint(
                oracle, x_m=x_m, y_m=y_m, z_m=0.0, theta_rad=seg["theta_rad"]
            )
            ticks.append(
                {
                    "tick": tick_i,
                    "segment_id": seg["segment_id"],
                    "zone_from": seg["zone_from"],
                    "zone_to": seg["zone_to"],
                    "path_s": round(path_s, 6),
                    "meters": round(path_s, 6),
                    "x_m": round(x_m, 6),
                    "y_m": round(y_m, 6),
                    "z_m": 0.0,
                    "theta_rad": round(seg["theta_rad"], 9),
                    "oracle_x_m": round(px, 6),
                    "oracle_y_m": round(py, 6),
                    "oracle_z_m": round(pz, 6),
                    "rotor_hex": _motor_hex(rotor),
                    "rev_hex": _motor_hex(rev),
                    "point_hex": _motor_hex(point),
                }
            )
            bin_chunks.append(
                struct.pack("<If", tick_i, float(path_s))
                + _pack_motor(rotor)
                + _pack_motor(point)
                + _pack_motor(rev)
            )
            tick_i += 1

    doc: dict[str, Any] = {
        "vector_id": "lunar_construct_waypoint_vectors_v1",
        "profile_id": "lunar_base_construct_alpha",
        "segment_ticks": _SEGMENT_TICKS,
        "site_graph_total_path_m": graph["total_path_m"],
        "segment_count": len(segments),
        "tick_count": len(ticks),
        "segments": segments,
        "ticks": ticks,
        "mint_role": "inter_zone_site_graph_geometry",
        "compute_layers": [
            "python_pga8_oracle",
            "iron_rtl_mmio",
            "cxx_world_motion_rail",
            "cxx_world_waypoint_rail",
        ],
    }

    if write:
        _VEC_JSON.parent.mkdir(parents=True, exist_ok=True)
        _VEC_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        _VEC_BIN.write_bytes(struct.pack("<I", len(ticks)) + b"".join(bin_chunks))
    return doc


def write_lunar_construct_waypoint_rtl_tb(vectors: dict[str, Any]) -> Path:
    ticks = vectors["ticks"]
    n = len(ticks)
    rotor_lines = "\n".join(f"    rotor_motor[{i}] = 128'h{t['rotor_hex']};" for i, t in enumerate(ticks))
    rev_lines = "\n".join(f"    rev_motor[{i}] = 128'h{t['rev_hex']};" for i, t in enumerate(ticks))
    point_lines = "\n".join(f"    point_motor[{i}] = 128'h{t['point_hex']};" for i, t in enumerate(ticks))
    tick_id_lines = "\n".join(f"    tick_ids[{i}] = {t['tick']};" for i, t in enumerate(ticks))
    mvals = [f"      mvals[{i}] = {float(t.get('meters', t['path_s'])):.6f};" for i, t in enumerate(ticks)]

    body = f"""// Lunar construct waypoint RTL iron TB — per-tick point motor array
// Regenerate: python scripts/chip/gen_lunar_construct_waypoint_vectors_v1.py
`timescale 1ns/1ps
`include "clifford_alu_v0_pkg.vh"
`include "clifford_bf16_ops_v0.vh"

module clifford_lunar_construct_waypoint_rtl_tb_v0;
  localparam integer N_TICKS = {n};

  reg clk;
  reg rst;
  reg reg_wen;
  reg reg_ren;
  reg [5:0] reg_addr;
  reg [31:0] reg_wdata;
  wire [31:0] reg_rdata;

  reg [127:0] rotor_motor [0:N_TICKS-1];
  reg [127:0] rev_motor [0:N_TICKS-1];
  reg [127:0] point_motor [0:N_TICKS-1];
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
{point_lines}
{tick_id_lines}
    begin : init_meters
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
      run_geo_prod(rotor_motor[ti], point_motor[ti], tmp_motor);
      run_geo_prod(tmp_motor, rev_motor[ti], out_motor);
      $display("RTL_WORLD_POSE %0d %f %f %f %f",
          tick_ids[ti], tick_meters[ti],
          blade_real_1(out_motor), blade_real_2(out_motor), blade_real_3(out_motor));
    end
    $display("TB_PASS rtl_lunar_construct_waypoint");
    $finish(0);
  end
endmodule
"""
    _RTL_TB.write_text(body, encoding="utf-8")
    return _RTL_TB


def write_lunar_construct_waypoint_structural_rtl_tb(vectors: dict[str, Any]) -> Path:
    """MMIO TB with gp_synth datapath enabled (synthesizable structural, pre-map)."""
    write_lunar_construct_waypoint_rtl_tb(vectors)
    text = _RTL_TB.read_text(encoding="utf-8")
    text = text.replace("clifford_lunar_construct_waypoint_rtl_tb_v0", "clifford_lunar_construct_waypoint_structural_rtl_tb_v0")
    text = text.replace("TB_PASS rtl_lunar_construct_waypoint", "TB_PASS rtl_lunar_construct_waypoint_structural")
    text = text.replace(
        "#20 rst = 1'b0;",
        "#20 rst = 1'b0;\n    mmio_write(6'h3E, 32'd1);",
    )
    _STRUCT_TB.write_text(text, encoding="utf-8")
    return _STRUCT_TB


def write_lunar_construct_waypoint_mapped_slice_rtl_tb(vectors: dict[str, Any]) -> Path:
    """Mapped Nangate45 geo_prod slice — 2× GEO_PROD per tick (per-tick point motor)."""
    ticks = vectors["ticks"]
    n = len(ticks)
    rotor_lines = "\n".join(f"    rotor_motor[{i}] = 128'h{t['rotor_hex']};" for i, t in enumerate(ticks))
    rev_lines = "\n".join(f"    rev_motor[{i}] = 128'h{t['rev_hex']};" for i, t in enumerate(ticks))
    point_lines = "\n".join(f"    point_motor[{i}] = 128'h{t['point_hex']};" for i, t in enumerate(ticks))
    tick_id_lines = "\n".join(f"    tick_ids[{i}] = {t['tick']};" for i, t in enumerate(ticks))
    mvals = [f"      mvals[{i}] = {float(t.get('meters', t['path_s'])):.6f};" for i, t in enumerate(ticks)]
    body = f"""// Mapped geo_prod slice lunar construct waypoint TB — Nangate45 structural smoke
`timescale 1ns/1ps
`include "clifford_alu_v0_pkg.vh"
`include "clifford_bf16_ops_v0.vh"

module clifford_lunar_construct_waypoint_mapped_slice_rtl_tb_v0;
  localparam integer N_TICKS = {n};

  reg clk, rst;
  reg ex1_latch, ex2_eval, ex2_latch, ex3_eval, ex3_latch, wb_eval;
  reg [`CLIFFORD_MOTOR_W-1:0] a, b;
  wire [`CLIFFORD_MOTOR_W-1:0] r;
  reg [127:0] rotor_motor [0:N_TICKS-1];
  reg [127:0] rev_motor [0:N_TICKS-1];
  reg [127:0] point_motor [0:N_TICKS-1];
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
{point_lines}
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
      pulse_geo_prod(rotor_motor[ti], point_motor[ti], tmp_motor);
      pulse_geo_prod(tmp_motor, rev_motor[ti], out_motor);
      $display("RTL_MAPPED_POSE %0d %f %f %f %f",
          tick_ids[ti], tick_meters[ti],
          blade_real_1(out_motor), blade_real_2(out_motor), blade_real_3(out_motor));
    end
    $display("TB_PASS rtl_lunar_construct_waypoint_mapped_slice");
    $finish(0);
  end
endmodule
"""
    _MAPPED_SLICE_TB.parent.mkdir(parents=True, exist_ok=True)
    _MAPPED_SLICE_TB.write_text(body, encoding="utf-8")
    return _MAPPED_SLICE_TB


if __name__ == "__main__":
    doc = mint_lunar_construct_waypoint_vectors()
    tb = write_lunar_construct_waypoint_rtl_tb(doc)
    print(json.dumps({"vector_id": doc["vector_id"], "ticks": doc["tick_count"], "rtl_tb": tb.name}))
