"""Legalize clifford.gp — oracle bit-match vs hand SV vectors (T4 gate op)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_VECTORS = _REPO / "fixtures" / "chip" / "clifford_alu_vectors_v1.json"
_MLIR_EX = _REPO / "mlir" / "clifford" / "examples"


def _oracle():
    from scripts.chip import clifford_pga8_oracle_v0 as o

    return o


def _hex_to_coeffs(hex_str: str) -> list[int]:
    o = _oracle()
    return list(o.unpack_motor(int(hex_str, 16)))


def legalize_gp(rs1_hex: str, rs2_hex: str) -> str:
    """MLIR clifford.gp semantics = oracle geo_prod (L0 gold)."""
    o = _oracle()
    a = _hex_to_coeffs(rs1_hex)
    b = _hex_to_coeffs(rs2_hex)
    return o.motor_hex(o.geo_prod_coeffs(a, b))


def _vector_gp_cases(vectors: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    smoke = vectors.get("p2_smoke")
    if smoke:
        out.append(
            {
                "id": "p2_smoke",
                "rs1_hex": smoke["rs1_hex"],
                "rs2_hex": smoke["rs2_hex"],
                "expected_rd_hex": smoke["expected_rd_hex"],
            }
        )
    for c in vectors.get("p2_cases", []):
        out.append(
            {
                "id": c["id"],
                "rs1_hex": c["rs1_hex"],
                "rs2_hex": c["rs2_hex"],
                "expected_rd_hex": c["expected_rd_hex"],
            }
        )
    return out


def run_gp_legalize_gate(*, include_mlir_examples: bool = True) -> dict[str, Any]:
    vectors = json.loads(_VECTORS.read_text(encoding="utf-8"))
    cases = _vector_gp_cases(vectors)

    if include_mlir_examples:
        from scripts.chip.clifford_mlir_parse_v1 import load_mlir_cases

        for mlir_path in sorted(_MLIR_EX.glob("*.mlir")):
            for mc in load_mlir_cases(mlir_path):
                cases.append(
                    {
                        "id": f"{mlir_path.stem}:{mc.case_id}",
                        "rs1_hex": mc.rs1_hex,
                        "rs2_hex": mc.rs2_hex,
                        "expected_rd_hex": mc.expected_rd_hex,
                    }
                )

    rows: list[dict[str, Any]] = []
    all_ok = True
    for c in cases:
        got = legalize_gp(c["rs1_hex"], c["rs2_hex"])
        ok = got.lower() == c["expected_rd_hex"].lower()
        all_ok = all_ok and ok
        rows.append({**c, "legalized_rd_hex": got, "pass": ok})

    return {
        "gate_id": "clifford_gp_legalize_v1",
        "verdict": "LEGALIZE_PASS" if all_ok else "LEGALIZE_FAIL",
        "n_cases": len(rows),
        "n_pass": sum(1 for r in rows if r["pass"]),
        "cases": rows,
        "honesty": {
            "semantics": "oracle geo_prod_coeffs — same as hand SV clifford_geo_prod_v0",
            "circt_emitted": False,
            "iron_sim": "vectors JSON + oracle — not verilator on MLIR emit",
        },
    }
