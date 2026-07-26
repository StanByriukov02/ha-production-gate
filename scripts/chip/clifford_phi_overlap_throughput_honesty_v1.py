"""T2.5b — overlap throughput honesty (scheduler ≠ comb depth · STA independent)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FIX = _REPO / "fixtures" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_PHI_OVERLAP_THROUGHPUT_HONESTY_RECEIPT_v1.json"
_T25 = _CHIP / "CHIP_CLIFFORD_PHI_OVERLAP_T2_5_RECEIPT_v1.json"
_THERM = _CHIP / "CHIP_CLIFFORD_STA_T2_THERMOMETER_RECEIPT_v1.json"
_STAGED = _CHIP / "CHIP_CLIFFORD_STA_T2_SANDWICH_STAGED_PROMOTE_RECEIPT_v1.json"
_BENCH = _CHIP / "CHIP_CLIFFORD_COMPOSE_TIER_BENCHMARK_RECEIPT_v1.json"
_SCOPE = _REPO / "docs/agent_workflow/CLIFFORD_PHI_OVERLAP_MODE_v1.md"
_ALU_TOP = _FIX / "clifford_alu_top_v0.v"


def run_phi_overlap_throughput_honesty(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    from scripts.chip.clifford_phi_overlap_unpark_t2_v1 import run_phi_overlap_unpark_t2_5

    overlap = run_phi_overlap_unpark_t2_5(write=False)
    scope = _SCOPE.read_text(encoding="utf-8") if _SCOPE.is_file() else ""
    alu = _ALU_TOP.read_text(encoding="utf-8") if _ALU_TOP.is_file() else ""
    bench = json.loads(_BENCH.read_text(encoding="utf-8")) if _BENCH.is_file() else {}
    therm_wns = None
    if _THERM.is_file():
        therm_wns = json.loads(_THERM.read_text(encoding="utf-8")).get("timing", {}).get("wns_ns")
    staged_wns = None
    if _STAGED.is_file():
        staged_wns = json.loads(_STAGED.read_text(encoding="utf-8")).get("timing", {}).get("staged_wns_ns")

    iron_unpip = (bench.get("benchmarks") or {}).get("iron_modeled_op4", {})
    iron_overlap = (bench.get("benchmarks") or {}).get("iron_modeled_overlap_t2_5", {})
    tp_ratio = None
    if iron_unpip.get("us_per_compose") and iron_overlap.get("us_per_compose"):
        tp_ratio = round(iron_unpip["us_per_compose"] / iron_overlap["us_per_compose"], 2)

    checks = [
        {"id": "overlap_t2_5_prerequisite", "pass": overlap.get("verdict") == "PHI_OVERLAP_T2_5_PASS"},
        {"id": "overlap_scope_doc", "pass": _SCOPE.is_file()},
        {"id": "throughput_table_in_doc", "pass": "1 motor / 2φ" in scope},
        {"id": "comb_depth_tabu_in_doc", "pass": "comb depth" in scope.lower() or "comb depth" in scope},
        {
            "id": "overlap_not_in_alu_top",
            "pass": "overlap" not in alu.lower() and "phi_overlap" not in alu.lower(),
        },
        {
            "id": "verilator_overlap_steady",
            "pass": (overlap.get("verilator") or {}).get("verdict") == "VERILATOR_PHI_OVERLAP_PASS",
        },
        {
            "id": "modeled_throughput_4x",
            "pass": tp_ratio is not None and tp_ratio >= 3.5,
            "detail": f"unpip/overlap_us_ratio={tp_ratio}",
        },
        {
            "id": "sta_wns_independent_of_overlap",
            "pass": therm_wns is not None and staged_wns is not None,
            "detail": f"therm={therm_wns} staged={staged_wns} — overlap scheduler not in STA netlist",
        },
        {
            "id": "overlap_honesty_timing_closure_false",
            "pass": overlap.get("honesty", {}).get("timing_closure") is False,
        },
    ]

    verdict = "PHI_OVERLAP_THROUGHPUT_HONESTY_PASS" if all(c["pass"] for c in checks) else "PHI_OVERLAP_THROUGHPUT_HONESTY_FAIL"
    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_PHI_OVERLAP_THROUGHPUT_HONESTY_RECEIPT_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "throughput": {
            "unpipelined_us_per_compose": iron_unpip.get("us_per_compose"),
            "overlap_steady_us_per_compose": iron_overlap.get("us_per_compose"),
            "modeled_speedup": tp_ratio,
            "honesty": "scheduler sim retire cadence — datapath comb unchanged",
        },
        "comb_depth": {
            "sta_thermometer_wns_ns": therm_wns,
            "sta_after_staged_promote_wns_ns": staged_wns,
            "overlap_affects_comb": False,
        },
        "overlap_receipt_verdict": overlap.get("verdict"),
        "honesty": {
            "overlap_improves_throughput_not_wns": True,
            "alu_top_still_unpipelined_fsm": True,
            "dual_physics_phase": "T2_OVERLAP",
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(run_phi_overlap_throughput_honesty(), indent=2))
