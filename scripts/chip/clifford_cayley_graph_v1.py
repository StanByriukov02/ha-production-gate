"""T1 — Cayley mul graph gold · RTL term parity · receipt fixture writer."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.chip.clifford_cayley_v0 import (
    BLADE_NAMES,
    EVEN_MOTOR_INDICES,
    build_graph_catalog,
    cayley_terms,
    matmul_4x4_stats,
    motor_motor_output_indices,
    nl_claim_48_40,
)

_REPO = Path(__file__).resolve().parents[2]
_FIX = _REPO / "fixtures" / "chip"
_RTL_GP = _FIX / "clifford_geo_prod_v0.v"
_GRAPH_FIX = _FIX / "clifford_cayley_mul_graph_v1.json"
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1.json"
_BIND = _CHIP / "CHIP_CLIFFORD_CAYLEY_GOLD_T1_BIND_v1.json"

_CANON = (
    "docs/agent_workflow/CLIFFORD_DEPTH_PLAN_V1.md",
    "docs/agent_workflow/CLIFFORD_CODEC_CONTRACT_V0.md",
    "scripts/chip/clifford_cayley_v0.py",
)


def count_rtl_gp_mul_terms(path: Path | None = None) -> dict[str, int]:
    path = path or _RTL_GP
    text = path.read_text(encoding="utf-8")
    mul_hits = re.findall(r"blade_real_\d+\([^)]+\)\s*\*\s*blade_real_\d+\([^)]+\)", text)
    out_lines = re.findall(r"^\s*out\d\s*=", text, flags=re.MULTILINE)
    return {
        "rtl_mul_terms": len(mul_hits),
        "rtl_out_blades": len(out_lines),
        "rtl_path": str(path.relative_to(_REPO)).replace("\\", "/"),
    }


def build_mul_graph_doc() -> dict[str, Any]:
    catalog = build_graph_catalog()
    rtl = count_rtl_gp_mul_terms()
    full = catalog["full_8blade_rtl"]
    matmul = matmul_4x4_stats()
    nl = nl_claim_48_40()
    cse = catalog["full_8blade_cse_unique_ij"]
    even_motor = catalog["even_motor_closed"]

    rtl_matches_gold = rtl["rtl_mul_terms"] == full.mul_terms

    better_than_matmul_mul = full.mul_terms <= matmul.mul_terms
    better_than_matmul_add = full.add_terms <= matmul.add_terms

    nl_matches_any = nl.mul_terms in {g.mul_terms for g in catalog.values()}

    return {
        "graph_id": "clifford_cayley_mul_graph_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "algebra": {
            "label": "Cl(3,0) spatial PGA8",
            "metric": "e1^2=e2^2=e3^2=+1",
            "null_plane": "PARK_P2.1",
            "blade_names": list(BLADE_NAMES),
            "even_motor_indices": list(EVEN_MOTOR_INDICES),
            "motor_motor_output_indices": list(motor_motor_output_indices()),
        },
        "graphs": {k: v.to_dict() for k, v in catalog.items()},
        "references": {
            "matmul_4x4": matmul.to_dict(),
            "nl_claim": nl.to_dict(),
        },
        "rtl_parity": {
            **rtl,
            "matches_full_8blade_gold": rtl_matches_gold,
        },
        "analysis": {
            "rtl_is_gold_for_v0": rtl_matches_gold,
            "nl_48_mul_matches_catalog": nl_matches_any,
            "nl_48_mul_matches_rtl": nl.mul_terms == full.mul_terms,
            "full_gp_vs_matmul_mul": {
                "gp_mul": full.mul_terms,
                "matmul_mul": matmul.mul_terms,
                "gp_not_worse_mul_count": better_than_matmul_mul,
            },
            "full_gp_vs_matmul_add": {
                "gp_add": full.add_terms,
                "matmul_add": matmul.add_terms,
                "gp_not_worse_add_count": better_than_matmul_add,
            },
            "cse_unique_ij_mul": cse.mul_terms,
            "even_motor_closed_mul": even_motor.mul_terms,
            "verdict_hint": (
                "RTL=64/56 matches full Cayley; NL 48/40 unverified; "
                "even-motor-closed smaller but NOT current RTL datapath"
            ),
        },
        "cayley_table_sparse": _sparse_table_export(),
    }


def _sparse_table_export() -> list[dict[str, Any]]:
    terms = cayley_terms()
    rows: list[dict[str, Any]] = []
    for k in range(8):
        for i, j, sign in terms[k]:
            rows.append(
                {
                    "out": BLADE_NAMES[k],
                    "i": BLADE_NAMES[i],
                    "j": BLADE_NAMES[j],
                    "sign": sign,
                }
            )
    return rows


def run_cayley_gold_t1(*, write: bool = True) -> dict[str, Any]:
    doc = build_mul_graph_doc()
    full = doc["graphs"]["full_8blade_rtl"]
    rtl_ok = doc["rtl_parity"]["matches_full_8blade_gold"]
    nl_ok = doc["analysis"]["nl_48_mul_matches_catalog"]

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("full_8blade_mul_64", full["mul_terms"] == 64)
    chk("full_8blade_add_56", full["add_terms"] == 56)
    chk("rtl_term_parity", rtl_ok, detail=str(doc["rtl_parity"]["rtl_mul_terms"]))
    chk("cse_unique_ij_64", doc["graphs"]["full_8blade_cse_unique_ij"]["mul_terms"] == 64)
    chk("even_motor_closed_smaller", doc["graphs"]["even_motor_closed"]["mul_terms"] < 64)
    chk("motor_motor_outputs_even", set(motor_motor_output_indices()).issubset({0, 4, 5, 6}))
    chk("nl_48_not_gold", not nl_ok or doc["analysis"]["nl_48_mul_matches_rtl"] is False)
    chk(
        "gp_mul_not_worse_than_matmul",
        full["mul_terms"] <= doc["references"]["matmul_4x4"]["mul_terms"],
    )

    verdict = "T1_PASS" if all(c["pass"] for c in checks) else "T1_FAIL"

    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1",
        "bind_id": "CHIP_CLIFFORD_CAYLEY_GOLD_T1_BIND_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canon": list(_CANON),
        "sprint_track": "T1",
        "checks": checks,
        "graph_fixture": "fixtures/chip/clifford_cayley_mul_graph_v1.json",
        "gold_mul_add": {"mul": full["mul_terms"], "add": full["add_terms"]},
        "rtl_parity": doc["rtl_parity"],
        "analysis": doc["analysis"],
        "honesty": {
            "nl_48_mul": "UNVERIFIED — not matching RTL gold 64",
            "optimize_path": "even_motor_closed is future fork — not v0 RTL",
            "matmul_compare": "mul-count tie 64/64 — win is representation/ops not raw mul",
        },
    }

    if write:
        _GRAPH_FIX.parent.mkdir(parents=True, exist_ok=True)
        _GRAPH_FIX.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        bind = {"bind_id": "CHIP_CLIFFORD_CAYLEY_GOLD_T1_BIND_v1", **receipt}
        _BIND.write_text(json.dumps(bind, indent=2) + "\n", encoding="utf-8")

    dual = None
    if verdict == "T1_PASS" and write:
        from dogfood_platform.chip_clifford_dual_physics_review_v1 import run_dual_physics_review

        dual = run_dual_physics_review(phase="T1", write=write)

    receipt["dual_physics"] = dual.get("verdict") if dual else "SKIPPED"
    receipt["dual_physics_receipt"] = dual.get("receipt_id") if dual else None

    if write:
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    return receipt


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(_REPO))
    r = run_cayley_gold_t1()
    print(json.dumps({"verdict": r["verdict"], "dual": r.get("dual_physics")}, indent=2))
    raise SystemExit(0 if r["verdict"] == "T1_PASS" else 1)
