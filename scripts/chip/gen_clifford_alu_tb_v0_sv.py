"""Generate clifford_alu_tb_v0.v from clifford_alu_vectors_v1.json (P5 full oracle parity)."""
from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_VECTORS = _REPO / "fixtures" / "chip" / "clifford_alu_vectors_v1.json"
_OUT = _REPO / "fixtures" / "chip" / "clifford_alu_tb_v0.v"

_OP_MAP = {
    "V_GEO_PROD": "`CLIFFORD_OP_V_GEO_PROD",
    "V_SANDWICH": "`CLIFFORD_OP_V_SANDWICH",
    "NORM": "`CLIFFORD_OP_NORM",
}


def _cases(vectors: dict) -> list[dict]:
    rows: list[dict] = []
    p2 = vectors.get("p2_smoke")
    if p2:
        rows.append(
            {
                "id": "p2_smoke",
                "op": "V_GEO_PROD",
                "rs1": p2["rs1_hex"],
                "rs2": p2["rs2_hex"],
                "exp": p2["expected_rd_hex"],
            }
        )
    for row in vectors.get("p2_cases", []):
        rows.append(
            {
                "id": row["id"],
                "op": "V_GEO_PROD",
                "rs1": row["rs1_hex"],
                "rs2": row["rs2_hex"],
                "exp": row["expected_rd_hex"],
            }
        )
    p3s = vectors.get("p3_smoke")
    if p3s:
        rows.append(
            {
                "id": "p3_smoke",
                "op": "V_SANDWICH",
                "rs1": p3s["rs1_hex"],
                "rs2": p3s["rs2_hex"],
                "exp": p3s["expected_rd_hex"],
            }
        )
    for row in vectors.get("p3_cases", []):
        rows.append(
            {
                "id": row["id"],
                "op": row.get("opcode", "V_SANDWICH"),
                "rs1": row["rs1_hex"],
                "rs2": row.get("rs2_hex", "0"),
                "exp": row["expected_rd_hex"],
            }
        )
    return rows


def _hex128(h: str) -> str:
    h = h.replace("_", "").lower()
    return f"128'h{h}"


def main() -> None:
    vectors = json.loads(_VECTORS.read_text(encoding="utf-8"))
    cases = _cases(vectors)
    n = len(cases)

    lines = [
        "// Clifford ALU v0 — P5 full-vector TB (generated)",
        "// Regenerate: python scripts/chip/gen_clifford_alu_tb_v0_sv.py",
        "`timescale 1ns/1ps",
        "`include \"clifford_alu_v0_pkg.vh\"",
        "",
        "module clifford_alu_tb_v0;",
        f"  localparam integer N_CASES = {n};",
        "",
        "  reg clk;",
        "  reg rst;",
        "  reg gp_synth_en;",
        "  reg op_valid;",
        "  wire op_ready;",
        "  reg [2:0] op;",
        "  reg [`CLIFFORD_MOTOR_W-1:0] rs1;",
        "  reg [`CLIFFORD_MOTOR_W-1:0] rs2;",
        "  wire [`CLIFFORD_MOTOR_W-1:0] rd;",
        "  wire [`CLIFFORD_PHI_W-1:0] phi;",
        "  wire wb_done;",
        "  wire macro_retire;",
        "",
        "  reg [2:0] case_op [0:N_CASES-1];",
        "  reg [`CLIFFORD_MOTOR_W-1:0] case_rs1 [0:N_CASES-1];",
        "  reg [`CLIFFORD_MOTOR_W-1:0] case_rs2 [0:N_CASES-1];",
        "  reg [`CLIFFORD_MOTOR_W-1:0] case_exp [0:N_CASES-1];",
        "",
        "  integer cases_pass;",
        "  integer cases_fail;",
        "  integer ci;",
        "  integer cyc;",
        "  reg saw_wb;",
        "",
        "  clifford_alu_top_v0 dut (",
        "      .clk(clk),",
        "      .rst(rst),",
        "      .gp_synth_en(gp_synth_en),",
        "      .op_valid(op_valid),",
        "      .op_ready(op_ready),",
        "      .op(op),",
        "      .rs1(rs1),",
        "      .rs2(rs2),",
        "      .rd(rd),",
        "      .phi(phi),",
        "      .wb_done(wb_done),",
        "      .macro_retire(macro_retire)",
        "  );",
        "",
        "  initial clk = 1'b0;",
        "  always #5 clk = ~clk;",
        "",
        "  initial begin",
            "    cases_pass = 0;",
            "    cases_fail = 0;",
            "    gp_synth_en = 1'b0;",
            "",
    ]

    for i, c in enumerate(cases):
        lines.append(f"    case_op[{i}] = {_OP_MAP[c['op']]};")
        lines.append(f"    case_rs1[{i}] = {_hex128(c['rs1'])};")
        lines.append(f"    case_rs2[{i}] = {_hex128(c['rs2'])};")
        lines.append(f"    case_exp[{i}] = {_hex128(c['exp'])};")
        lines.append("")

    lines.extend(
        [
            "    for (ci = 0; ci < N_CASES; ci = ci + 1) begin",
            "      cyc = 0;",
            "      saw_wb = 1'b0;",
            "      rst = 1'b1;",
            "      op_valid = 1'b0;",
            "      op = case_op[ci];",
            "      rs1 = case_rs1[ci];",
            "      rs2 = case_rs2[ci];",
            "      #20 rst = 1'b0;",
            "      wait (op_ready == 1'b1);",
            "      @(posedge clk);",
            "      op_valid = 1'b1;",
            "      @(posedge clk);",
            "      op_valid = 1'b0;",
            "      while (!saw_wb) begin",
            "        @(posedge clk);",
            "        cyc = cyc + 1;",
            "        if (wb_done) saw_wb = 1'b1;",
            "        if (cyc > 32) begin",
            '          $display("TB_FAIL case=%0d timeout", ci);',
            "          cases_fail = cases_fail + 1;",
            "          ci = N_CASES;",
            "        end",
            "      end",
            "      if (ci < N_CASES) begin",
            '        if (rd !== case_exp[ci]) begin',
            '          $display("TB_FAIL case=%0d got=%h exp=%h wb=%0d", ci, rd, case_exp[ci], saw_wb);',
            "          cases_fail = cases_fail + 1;",
            "        end else begin",
            '          $display("TB_PASS case=%0d rd=%h", ci, rd);',
            "          cases_pass = cases_pass + 1;",
            "        end",
            "        #10;",
            "      end",
            "    end",
            "",
            "    if (cases_fail == 0) begin",
            '      $display("TB_PASS cases=%0d", cases_pass);',
            "      $finish(0);",
            "    end else begin",
            '      $display("TB_FAIL pass=%0d fail=%0d", cases_pass, cases_fail);',
            "      $finish(1);",
            "    end",
            "  end",
            "endmodule",
            "",
        ]
    )

    _OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {_OUT} ({n} cases)")


if __name__ == "__main__":
    main()
