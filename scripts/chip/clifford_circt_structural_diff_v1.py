"""CIRCT structural diff vs hand SV — T4.2 (no circt-opt binary required)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_RTL = _REPO / "fixtures" / "chip" / "clifford_geo_prod_v0.v"
_LOWER = _REPO / "mlir" / "clifford" / "lower" / "LOWER_PLAN_v1.md"


def _parse_rtl_module(text: str) -> dict[str, Any]:
    mod = re.search(r"module\s+(\w+)\s*\(", text)
    ports = re.findall(r"(?:input|output)\s+(?:\w+\s+)?(?:\[[^\]]+\]\s+)?(\w+)\s*[,)]", text)
    mul_hits = re.findall(r"blade_real_\d+\([^)]+\)\s*\*\s*blade_real_\d+\([^)]+\)", text)
    out_lines = re.findall(r"^\s*out\d\s*=", text, flags=re.MULTILINE)
    return {
        "module": mod.group(1) if mod else "",
        "ports": list(ports),
        "mul_terms": len(mul_hits),
        "out_blades": len(out_lines),
    }


def run_circt_structural_diff(*, t1_gold_mul: int = 64) -> dict[str, Any]:
    from scripts.chip.clifford_cayley_graph_v1 import count_rtl_gp_mul_terms

    rtl_text = _RTL.read_text(encoding="utf-8")
    rtl = _parse_rtl_module(rtl_text)
    fanin = count_rtl_gp_mul_terms()

    mlir_plan = {
        "lower_target_module": "clifford_geo_prod_v0",
        "expected_ports": ["a", "b", "r"],
        "cayley_mul_terms": t1_gold_mul,
        "out_blades": 8,
        "circt_binary": "SKIPPED",
        "lower_plan_doc": str(_LOWER.relative_to(_REPO)).replace("\\", "/"),
    }

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("hand_rtl_module", rtl["module"] == "clifford_geo_prod_v0")
    chk("port_names_abr", rtl["ports"] == ["a", "b", "r"])
    chk("rtl_mul_terms_t1_gold", rtl["mul_terms"] == t1_gold_mul, detail=str(rtl["mul_terms"]))
    chk("fanin_counter_parity", fanin["rtl_mul_terms"] == rtl["mul_terms"])
    chk("out_blades_eight", rtl["out_blades"] == 8)
    chk("lower_plan_present", _LOWER.is_file())
    chk(
        "mlir_plan_mul_match",
        mlir_plan["cayley_mul_terms"] == rtl["mul_terms"],
    )

    verdict = "STRUCTURAL_DIFF_PASS" if all(c["pass"] for c in checks) else "STRUCTURAL_DIFF_FAIL"

    return {
        "diff_id": "clifford_circt_structural_diff_v1",
        "verdict": verdict,
        "hand_rtl": {**rtl, "path": str(_RTL.relative_to(_REPO)).replace("\\", "/")},
        "mlir_lower_plan": mlir_plan,
        "checks": checks,
        "honesty": {
            "circt_opt_ran": False,
            "netlist_diff": False,
            "structural_only": True,
            "next_hop": "circt-opt emit when toolchain pinned",
        },
    }
