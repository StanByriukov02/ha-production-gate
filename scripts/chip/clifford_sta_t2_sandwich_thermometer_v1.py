"""T2.7 — STA sandwich binding-path thermometer (fresh OpenSTA · NOT closure)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_STA_T2_THERMOMETER_RECEIPT_v1.json"
_T2 = _CHIP / "CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1.json"
_T25 = _CHIP / "CHIP_CLIFFORD_PHI_OVERLAP_T2_5_RECEIPT_v1.json"
_P515 = _CHIP / "CHIP_CLIFFORD_ALU_P5_15_RECEIPT_v1.json"
_SCOPE = _REPO / "docs" / "agent_workflow" / "CLIFFORD_STA_SANDWICH_BINDING_PATH_v1.md"
_CLOCK_NS = 10.0
_WNS_SANDWICH_FLOOR = -100.0


def _load_verdict(path: Path, verdict: str) -> bool:
    return path.is_file() and json.loads(path.read_text(encoding="utf-8")).get("verdict") == verdict


def _classify_binding_path(tail: str) -> str:
    has_sandwich = "u_sandwich_pipe" in tail
    has_norm = "u_norm_synth" in tail or "u_norm_pipe" in tail
    has_gp = "u_geo_prod_pipe" in tail
    if has_sandwich and has_norm:
        return "sandwich_norm_comb"
    if has_sandwich:
        return "sandwich_comb"
    if has_gp:
        return "geo_prod_comb"
    return "unknown"


def _required_period_ns(clock_ns: float, wns_ns: float | None) -> float | None:
    if wns_ns is None:
        return None
    return round(clock_ns - wns_ns, 3)


def _geo_prod_slice_wns() -> float | None:
    if not _P515.is_file():
        return None
    data = json.loads(_P515.read_text(encoding="utf-8"))
    wns = data.get("honesty", {}).get("wns_ns")
    if wns is None:
        wns = (data.get("liberty_timing") or {}).get("opensta_liberty", {}).get("wns_ns")
    return float(wns) if wns is not None else None


def run_sta_t2_sandwich_thermometer(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    from scripts.chip.run_clifford_alu_opensta_liberty_full_v0 import run_clifford_alu_opensta_liberty_full

    t2_ok = _load_verdict(_T2, "OPT_BASELINE_PASS")
    t25_ok = _load_verdict(_T25, "PHI_OVERLAP_T2_5_PASS")
    lib = run_clifford_alu_opensta_liberty_full()
    ys = lib.get("yosys_mapped", {})
    sta = lib.get("opensta_liberty", {})
    tail = (sta.get("stdout_tail", "") or "") + (sta.get("reason", "") or "")
    wns = sta.get("wns_ns")
    gp_wns = _geo_prod_slice_wns()
    binding = _classify_binding_path(tail)
    req_period = _required_period_ns(_CLOCK_NS, wns)
    req_mhz = round(1000.0 / req_period, 2) if req_period and req_period > 0 else None

    checks: list[dict[str, Any]] = [
        {"id": "t2_opt_baseline_prerequisite", "pass": t2_ok},
        {"id": "binding_path_doc", "pass": _SCOPE.is_file()},
        {
            "id": "yosys_full_alu_mapped",
            "pass": ys.get("status") == "PASS" and ys.get("stdcell_mapped"),
            "detail": f"cells={ys.get('cells', 0)}",
        },
        {
            "id": "opensta_liberty_ran",
            "pass": sta.get("opensta_run") is True and sta.get("checks_ok") is True,
            "detail": sta.get("status", ""),
        },
        {
            "id": "multicycle_mcp_applied",
            "pass": sta.get("multicycle_applied") is True,
            "detail": f"groups={sta.get('multicycle_groups_applied', 0)}",
        },
        {
            "id": "wns_negative_thermometer",
            "pass": wns is not None and wns < 0,
            "detail": f"wns_ns={wns}",
        },
        {
            "id": "wns_sandwich_deep_binding",
            "pass": wns is not None and wns <= _WNS_SANDWICH_FLOOR,
            "detail": f"floor={_WNS_SANDWICH_FLOOR}",
        },
        {
            "id": "binding_path_is_sandwich",
            "pass": binding in ("sandwich_norm_comb", "sandwich_comb"),
            "detail": binding,
        },
        {
            "id": "full_alu_worse_than_geo_slice",
            "pass": wns is not None and gp_wns is not None and wns < gp_wns,
            "detail": f"full={wns} geo_slice={gp_wns}",
        },
        {
            "id": "sta_t2_timing_report_marker",
            "pass": "STA_T2_TIMING_REPORT_OK" in tail,
        },
    ]

    verdict = "STA_T2_THERMOMETER_PASS" if all(c["pass"] for c in checks) else "STA_T2_THERMOMETER_FAIL"
    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_STA_T2_THERMOMETER_RECEIPT_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "timing": {
            "clock_ns": _CLOCK_NS,
            "wns_ns": wns,
            "geo_prod_slice_wns_ns": gp_wns,
            "binding_path": binding,
            "required_period_ns": req_period,
            "required_fmax_mhz_hint": req_mhz,
            "timing_violated": sta.get("timing_violated"),
        },
        "liberty_full": {
            "verdict": lib.get("verdict"),
            "yosys_cells": ys.get("cells"),
            "yosys_dff": ys.get("dff_count"),
            "multicycle_groups": sta.get("multicycle_groups_applied"),
        },
        "honesty": {
            "timing_closure": False,
            "not_timing_signoff": True,
            "liberty_corner": "Nangate45_typ reference — NOT PDK signoff",
            "phi_overlap_t2_5": "PHI_OVERLAP_T2_5_PASS" if t25_ok else "OPEN",
            "overlap_does_not_cut_comb_depth": True,
            "closure_ladder_doc": "docs/agent_workflow/CLIFFORD_STA_SANDWICH_BINDING_PATH_v1.md",
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        (_CHIP / "sta" / "clifford_sta_t2_thermometer_report_v1.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
    return receipt


if __name__ == "__main__":
    print(json.dumps(run_sta_t2_sandwich_thermometer(), indent=2))
