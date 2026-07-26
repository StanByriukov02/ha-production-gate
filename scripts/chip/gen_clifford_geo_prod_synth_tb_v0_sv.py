"""Generate clifford_geo_prod_synth_tb_v0.v — sim vs synth parity from vectors + LC2."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_VECTORS = _REPO / "fixtures" / "chip" / "clifford_alu_vectors_v1.json"
_OUT = _REPO / "fixtures" / "chip" / "clifford_geo_prod_synth_tb_v0.v"

_LC2 = {
    "id": "lc2_rotor_point",
    "rs1_hex": "0000000000003ec40000000000003f6d",
    "rs2_hex": "000000000000000000003d120000",
}


def _load_oracle():
    path = _REPO / "scripts" / "chip" / "clifford_pga8_oracle_v0.py"
    spec = importlib.util.spec_from_file_location("clifford_pga8_oracle_v0", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("oracle missing")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["clifford_pga8_oracle_v0"] = mod
    spec.loader.exec_module(mod)
    return mod


def _geo_cases(vectors: dict, oracle) -> list[dict]:
    rows: list[dict] = []
    smoke = vectors.get("p2_smoke")
    if smoke:
        rows.append(
            {
                "id": "p2_smoke",
                "rs1": smoke["rs1_hex"],
                "rs2": smoke["rs2_hex"],
                "exp": smoke["expected_rd_hex"],
            }
        )
    for row in vectors.get("p2_cases", []):
        rows.append(
            {
                "id": row["id"],
                "rs1": row["rs1_hex"],
                "rs2": row["rs2_hex"],
                "exp": row["expected_rd_hex"],
            }
        )
    rows.append(
        {
            "id": _LC2["id"],
            "rs1": _LC2["rs1_hex"],
            "rs2": _LC2["rs2_hex"],
            "exp": _lc2_oracle_hex(oracle),
        }
    )
    return rows


def _lc2_oracle_hex(oracle) -> str:
    rs1 = oracle.unpack_motor(int(_LC2["rs1_hex"], 16))
    rs2 = oracle.unpack_motor(int(_LC2["rs2_hex"], 16))
    return oracle.geo_prod_hex(rs1, rs2)


def _hex128(h: str) -> str:
    return f"128'h{h.replace('_', '').lower()}"


def main() -> None:
    vectors = json.loads(_VECTORS.read_text(encoding="utf-8"))
    oracle = _load_oracle()
    cases = _geo_cases(vectors, oracle)
    lines = [
        "// P5.2 — sim geo_prod vs synth geo_prod parity TB (generated)",
        "// Regenerate: python scripts/chip/gen_clifford_geo_prod_synth_tb_v0_sv.py",
        "`timescale 1ns/1ps",
        "`include \"clifford_alu_v0_pkg.vh\"",
        "`include \"clifford_bf16_ops_v0.vh\"",
        "",
        "module clifford_geo_prod_synth_tb_v0;",
        "  reg [`CLIFFORD_MOTOR_W-1:0] a, b;",
        "  wire [`CLIFFORD_MOTOR_W-1:0] r_sim, r_synth;",
        "",
        "  clifford_geo_prod_v0 u_sim (.a(a), .b(b), .r(r_sim));",
        "  clifford_geo_prod_synth_v0 u_synth (.a(a), .b(b), .r(r_synth));",
        "",
        "  initial begin",
        f"    integer n_ok = 0;",
    ]
    for i, row in enumerate(cases):
        lines.append(f"    // case {i}: {row['id']}")
        lines.append(f"    a = {_hex128(row['rs1'])};")
        lines.append(f"    b = {_hex128(row['rs2'])};")
        lines.append("    #1;")
        lines.append("    if (r_sim !== r_synth) begin")
        lines.append(
            f'      $display("TB_FAIL {row["id"]} sim=%h synth=%h", r_sim, r_synth);'
        )
        lines.append("      $finish(1);")
        lines.append("    end")
        if row.get("exp"):
            lines.append(f"    if (r_synth !== {_hex128(row['exp'])}) begin")
            lines.append(
                f'      $display("TB_FAIL {row["id"]}_oracle synth=%h exp={row["exp"]}", r_synth);'
            )
            lines.append("      $finish(1);")
            lines.append("    end")
        lines.append("    n_ok = n_ok + 1;")
    lines.extend(
        [
            f'    if (n_ok !== {len(cases)}) begin $display("TB_FAIL case_count"); $finish(1); end',
            '    $display("TB_PASS geo_prod_synth_parity n=%0d", n_ok);',
            "    $finish(0);",
            "  end",
            "endmodule",
            "",
        ]
    )
    _OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {_OUT} cases={len(cases)}")


if __name__ == "__main__":
    main()
