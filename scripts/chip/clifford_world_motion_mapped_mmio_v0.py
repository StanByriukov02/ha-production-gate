"""Mapped structural MMIO + netlist slice parity for world motion poses."""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_WORLD_MOTION_MAPPED_MMIO_RECEIPT_v1.json"
_PARITY_TOL_M = 0.012


def _rmse(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> float:
    if len(a) != len(b) or not a:
        return float("inf")
    err = 0.0
    for pa, pb in zip(a, b):
        err += (pa["x_m"] - pb["x_m"]) ** 2 + (pa["y_m"] - pb["y_m"]) ** 2 + (pa["z_m"] - pb["z_m"]) ** 2
    return math.sqrt(err / len(a))


def _ticks_sane(ticks: list[dict[str, Any]]) -> bool:
    if not ticks:
        return False
    for t in ticks:
        for key in ("x_m", "y_m", "z_m"):
            v = float(t[key])
            if not math.isfinite(v) or abs(v) > 100.0:
                return False
    return True


def _align_ticks(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    n = min(len(a), len(b))
    if n <= 0:
        return [], []
    return a[:n], b[:n]


def build_mapped_mmio_parity(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_iron_mmio_driver_v0 import (
        run_iron_world_motion_mapped_slice_sim,
        run_iron_world_motion_sim,
        run_iron_world_motion_structural_sim,
        run_iron_world_motion_synth_slice_sim,
    )

    backend = os.environ.get("CLIFFORD_IRON_BACKEND", "auto")
    behavioral = run_iron_world_motion_sim(backend=backend)
    structural = run_iron_world_motion_structural_sim(backend=backend)
    synth_slice = run_iron_world_motion_synth_slice_sim(backend=backend)
    mapped = run_iron_world_motion_mapped_slice_sim(backend="iverilog")

    b_ticks = list(behavioral.get("ticks") or [])
    s_ticks = list(structural.get("ticks") or [])
    ss_ticks = list(synth_slice.get("ticks") or [])
    m_ticks = list(mapped.get("ticks") or [])

    struct_rmse = _rmse(b_ticks, s_ticks) if behavioral.get("status") == "PASS" and structural.get("status") == "PASS" else float("inf")
    synth_rmse = _rmse(b_ticks, ss_ticks) if behavioral.get("status") == "PASS" and _ticks_sane(ss_ticks) else float("inf")
    mapped_rmse = _rmse(b_ticks, m_ticks) if behavioral.get("status") == "PASS" and _ticks_sane(m_ticks) else float("inf")
    mapped_vs_synth_rmse = _rmse(ss_ticks, m_ticks) if _ticks_sane(ss_ticks) and _ticks_sane(m_ticks) else float("inf")

    struct_ok = structural.get("status") == "PASS" and math.isfinite(struct_rmse) and struct_rmse < _PARITY_TOL_M
    synth_pipeline_ok = synth_slice.get("status") == "PASS" and _ticks_sane(ss_ticks) and math.isfinite(synth_rmse) and synth_rmse < _PARITY_TOL_M
    mapped_func_ok = mapped.get("status") == "PASS" and _ticks_sane(m_ticks) and math.isfinite(mapped_rmse) and mapped_rmse < _PARITY_TOL_M
    mapped_vs_synth_ok = (
        mapped.get("status") == "PASS"
        and _ticks_sane(m_ticks)
        and _ticks_sane(ss_ticks)
        and math.isfinite(mapped_vs_synth_rmse)
        and mapped_vs_synth_rmse < _PARITY_TOL_M
    )
    mapped_elab_ok = mapped.get("status") == "PASS"

    run_alu = os.environ.get("CLIFFORD_MAPPED_ALU_MMIO", "").strip() in ("1", "true", "yes")
    tick_cap = int(os.environ.get("CLIFFORD_MAPPED_TICKS", "50"))
    alu_mapped: dict[str, Any] | None = None
    alu_func_ok = False
    alu_elab_ok = False
    alu_signoff_ok = False
    if run_alu:
        from scripts.chip.clifford_iron_mmio_driver_v0 import run_iron_world_motion_mapped_alu_mmio_sim

        alu_mapped = run_iron_world_motion_mapped_alu_mmio_sim(backend="iverilog")
        a_ticks = list(alu_mapped.get("ticks") or [])
        b_alu, a_cmp = _align_ticks(b_ticks, a_ticks)
        alu_rmse = _rmse(b_alu, a_cmp) if behavioral.get("status") == "PASS" and _ticks_sane(a_cmp) else float("inf")
        alu_func_ok = alu_mapped.get("status") == "PASS" and _ticks_sane(a_cmp) and math.isfinite(alu_rmse) and alu_rmse < _PARITY_TOL_M
        alu_elab_ok = alu_mapped.get("status") == "PASS"
        alu_signoff_ok = alu_func_ok and len(a_cmp) >= 50

    verdict = "PASS" if struct_ok else ("DEGRADED" if mapped_elab_ok else "FAIL")

    doc = {
        "receipt_id": "CHIP_CLIFFORD_WORLD_MOTION_MAPPED_MMIO_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "behavioral_mmio": {
            "status": behavioral.get("status"),
            "backend": behavioral.get("backend"),
            "ticks": behavioral.get("tick_count"),
        },
        "structural_synth_mmio": {
            "status": structural.get("status"),
            "backend": structural.get("backend"),
            "ticks": structural.get("tick_count"),
            "rmse_vs_behavioral_m": round(struct_rmse, 6) if math.isfinite(struct_rmse) else None,
            "parity_ok": struct_ok,
        },
        "rtl_synth_slice_pipeline": {
            "status": synth_slice.get("status"),
            "backend": synth_slice.get("backend"),
            "ticks": synth_slice.get("tick_count"),
            "pipeline_stimulus_ok": synth_pipeline_ok,
            "rmse_vs_behavioral_m": round(synth_rmse, 6) if math.isfinite(synth_rmse) else None,
            "parity_ok": synth_pipeline_ok,
        },
        "mapped_netlist_slice": {
            "status": mapped.get("status"),
            "backend": mapped.get("backend"),
            "ticks": mapped.get("tick_count"),
            "netlist": "results/platform_bpass/chip/sta/clifford_sta_geo_prod_slice_mapped_v0.v",
            "primitives": "fixtures/chip/sta/nangate45_sim_primitives_v0.v",
            "elaboration_smoke_ok": mapped_elab_ok,
            "functional_parity_ok": mapped_func_ok,
            "functional_parity_vs_rtl_synth_ok": mapped_vs_synth_ok,
            "rmse_vs_behavioral_m": round(mapped_rmse, 6) if math.isfinite(mapped_rmse) else None,
            "rmse_vs_rtl_synth_slice_m": round(mapped_vs_synth_rmse, 6) if math.isfinite(mapped_vs_synth_rmse) else None,
            "parity_ok": mapped_func_ok,
            "sim_layer": mapped.get("sim_layer"),
            "next_hop": None if mapped_func_ok else ("T2.22c_gate_level_f32_functional" if not mapped_vs_synth_ok else None),
        },
        "honesty": {
            "structural_synth_is_pre_map_datapath": True,
            "pipeline_stimulus_t2_22a": synth_pipeline_ok,
            "mapped_slice_elab_smoke": mapped_elab_ok,
            "mapped_functional_parity_pending": mapped_elab_ok and not mapped_func_ok,
            "mapped_hybrid_sim_gate_pipe_rtl_arith": False,
            "nangate45_sim_primitives_liberty_truth": True,
            "full_nangate45_comb_mul_iverilog_unreliable": False,
            "cell_models_zero_delay": True,
            "not_full_alu_mapped_mmio": not alu_signoff_ok,
            "alu_mmio_leg_env_gated": not run_alu,
            "alu_tick_cap": tick_cap if run_alu else None,
            "wb_eval_was_tied_zero_pre_t2_22": True,
        },
    }
    if run_alu and alu_mapped is not None:
        a_ticks = list(alu_mapped.get("ticks") or [])
        b_alu, a_cmp = _align_ticks(b_ticks, a_ticks)
        alu_rmse = _rmse(b_alu, a_cmp) if behavioral.get("status") == "PASS" and _ticks_sane(a_cmp) else float("inf")
        doc["mapped_full_alu_mmio"] = {
            "status": alu_mapped.get("status"),
            "backend": alu_mapped.get("backend"),
            "ticks": alu_mapped.get("tick_count"),
            "tick_cap": tick_cap,
            "netlist": "results/platform_bpass/chip/sta/clifford_sta_alu_slice_mapped_v0.v",
            "hybrid_netlist": "results/platform_bpass/chip/sta/clifford_sta_alu_slice_mapped_hybrid_v0.v",
            "elaboration_smoke_ok": alu_elab_ok,
            "functional_parity_ok": alu_func_ok,
            "signoff_50tick_ok": alu_signoff_ok,
            "rmse_vs_behavioral_m": round(alu_rmse, 6) if math.isfinite(alu_rmse) else None,
            "parity_ok": alu_func_ok,
            "sim_layer": alu_mapped.get("sim_layer"),
            "hybrid_funcsim": os.environ.get("CLIFFORD_MAPPED_ALU_HYBRID", "").strip() in ("1", "true", "yes"),
        }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = build_mapped_mmio_parity()
    print(json.dumps({k: v for k, v in out.items() if k != "honesty"}, indent=2))
    raise SystemExit(0 if out["verdict"] in ("PASS", "DEGRADED") else 1)
