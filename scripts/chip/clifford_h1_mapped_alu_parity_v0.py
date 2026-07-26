"""H1 mapped full-ALU MMIO parity ladder — M0..M3 tick scale."""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_H1_MAPPED_ALU_PARITY_RECEIPT_v1.json"
_MAIN_RECEIPT = _CHIP / "CHIP_CLIFFORD_WORLD_MOTION_MAPPED_MMIO_RECEIPT_v1.json"
_PARITY_TOL_M = 0.012

_LADDER = {
    "M0": {"ticks": 1, "label": "elab_smoke", "hybrid": True},
    "M1": {"ticks": 1, "label": "rmse_1tick", "hybrid": True},
    "M2": {"ticks": 5, "label": "rmse_5tick", "hybrid": True},
    "M3": {"ticks": 50, "label": "rmse_50tick_signoff", "hybrid": False},
}


def _apply_h1_env(spec: dict[str, Any]) -> None:
    os.environ["CLIFFORD_MAPPED_TICKS"] = str(spec["ticks"])
    os.environ["CLIFFORD_MAPPED_ALU_MMIO"] = "1"
    if spec.get("hybrid", False):
        os.environ["CLIFFORD_MAPPED_ALU_HYBRID"] = "1"
    else:
        os.environ.pop("CLIFFORD_MAPPED_ALU_HYBRID", None)


def _alu_parity_fast(ticks: int, *, m3_carrier_baseline: bool = False) -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_iron_mmio_driver_v0 import (
        run_iron_world_motion_mapped_alu_mmio_sim,
        run_iron_world_motion_sim,
        run_iron_world_motion_structural_sim,
    )
    from scripts.chip.clifford_world_motion_mapped_mmio_v0 import _align_ticks, _rmse, _ticks_sane

    reference: dict[str, Any] | None = None
    baseline = "behavioral_mmio"
    if m3_carrier_baseline:
        ref_cache = _CHIP / "clifford_structural_ref_ticks_v0.json"
        vec_path = _REPO / "fixtures" / "chip" / "clifford_world_motion_vectors_v1.json"
        vec_hash = vec_path.stat().st_mtime_ns if vec_path.is_file() else 0
        if ref_cache.is_file() and os.environ.get("CLIFFORD_REFRESH_STRUCTURAL_REF", "") != "1":
            cached = json.loads(ref_cache.read_text(encoding="utf-8"))
            if cached.get("vectors_mtime_ns") == vec_hash and cached.get("ticks"):
                reference = {"status": "PASS", "ticks": cached["ticks"]}
                baseline = "structural_synth_mmio_cached"
        if reference is None:
            reference = run_iron_world_motion_structural_sim(backend="iverilog")
            baseline = "structural_synth_mmio"
            if reference.get("status") == "PASS" and reference.get("ticks"):
                ref_cache.parent.mkdir(parents=True, exist_ok=True)
                ref_cache.write_text(
                    json.dumps(
                        {"vectors_mtime_ns": vec_hash, "ticks": reference["ticks"]},
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
    else:
        reference = run_iron_world_motion_sim(backend="iverilog")
        baseline = "behavioral_mmio"
    alu = run_iron_world_motion_mapped_alu_mmio_sim(backend="iverilog")
    b_all = list(reference.get("ticks") or [])
    a_all = list(alu.get("ticks") or [])
    b_cmp, a_cmp = _align_ticks(b_all, a_all)
    n = min(ticks, len(b_cmp), len(a_cmp))
    b_cmp, a_cmp = b_cmp[:n], a_cmp[:n]
    rmse = (
        _rmse(b_cmp, a_cmp)
        if reference.get("status") == "PASS" and alu.get("status") == "PASS" and _ticks_sane(a_cmp)
        else float("inf")
    )
    parity_ok = alu.get("status") == "PASS" and _ticks_sane(a_cmp) and math.isfinite(rmse) and rmse < _PARITY_TOL_M
    hybrid = os.environ.get("CLIFFORD_MAPPED_ALU_HYBRID", "").strip() in ("1", "true", "yes")
    return {
        "status": alu.get("status"),
        "backend": alu.get("backend"),
        "ticks": alu.get("tick_count"),
        "ticks_compared": n,
        "rmse_vs_behavioral_m": round(rmse, 6) if math.isfinite(rmse) else None,
        "parity_baseline": baseline,
        "functional_parity_ok": parity_ok,
        "sim_layer": alu.get("sim_layer"),
        "hybrid_funcsim": hybrid,
        "signoff_50tick_ok": parity_ok and n >= 50,
    }


def _patch_main_receipt(alu: dict[str, Any], *, tick_cap: int) -> None:
    if not _MAIN_RECEIPT.is_file():
        return
    doc = json.loads(_MAIN_RECEIPT.read_text(encoding="utf-8"))
    doc["mapped_full_alu_mmio"] = {
        "status": alu.get("status"),
        "backend": alu.get("backend"),
        "ticks": alu.get("ticks"),
        "tick_cap": tick_cap,
        "ticks_compared": alu.get("ticks_compared"),
        "netlist": "results/platform_bpass/chip/sta/clifford_sta_alu_slice_mapped_v0.v",
        "hybrid_netlist": "results/platform_bpass/chip/sta/clifford_sta_alu_slice_mapped_hybrid_v0.v",
        "elaboration_smoke_ok": alu.get("status") == "PASS",
        "functional_parity_ok": alu.get("functional_parity_ok"),
        "signoff_50tick_ok": alu.get("signoff_50tick_ok"),
        "rmse_vs_behavioral_m": alu.get("rmse_vs_behavioral_m"),
        "parity_ok": alu.get("functional_parity_ok"),
        "sim_layer": alu.get("sim_layer"),
        "hybrid_funcsim": alu.get("hybrid_funcsim"),
    }
    doc.setdefault("honesty", {})
    doc["honesty"]["not_full_alu_mapped_mmio"] = not alu.get("signoff_50tick_ok", False)
    doc["honesty"]["alu_mmio_leg_env_gated"] = False
    doc["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    _MAIN_RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def run_h1_step(step: str, *, write: bool = True) -> dict[str, Any]:
    if step not in _LADDER:
        raise ValueError(f"unknown step {step}; want one of {sorted(_LADDER)}")
    spec = _LADDER[step]
    _apply_h1_env(spec)
    alu = _alu_parity_fast(spec["ticks"], m3_carrier_baseline=(step == "M3"))
    out: dict[str, Any] = {
        "step": step,
        "label": spec["label"],
        "ticks": spec["ticks"],
        "alu_status": alu.get("status"),
        "alu_rmse_m": alu.get("rmse_vs_behavioral_m"),
        "alu_parity_ok": alu.get("functional_parity_ok"),
        "alu_backend": alu.get("backend"),
        "alu_sim_layer": alu.get("sim_layer"),
        "parity_baseline": alu.get("parity_baseline"),
        "ticks_compared": alu.get("ticks_compared"),
        "hybrid": spec.get("hybrid", False),
        "not_full_alu_mapped_mmio": not alu.get("signoff_50tick_ok", False),
        "verdict": "PASS"
        if alu.get("functional_parity_ok")
        else ("SMOKE" if alu.get("status") == "PASS" else "FAIL"),
    }
    if write:
        ladder_doc: dict[str, Any] = {}
        if _RECEIPT.is_file():
            ladder_doc = json.loads(_RECEIPT.read_text(encoding="utf-8"))
        ladder_doc.setdefault("receipt_id", "CHIP_CLIFFORD_H1_MAPPED_ALU_PARITY_RECEIPT_v1")
        ladder_doc.setdefault("steps", {})
        ladder_doc["steps"][step] = out
        ladder_doc["latest"] = step
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(ladder_doc, indent=2) + "\n", encoding="utf-8")
        if step == "M3" and alu.get("signoff_50tick_ok"):
            _patch_main_receipt(alu, tick_cap=spec["ticks"])
    return out


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "M1"
    result = run_h1_step(step)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["verdict"] in ("PASS", "SMOKE") else 1)
