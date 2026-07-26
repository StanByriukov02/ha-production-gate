"""M3 per-tick drift — behavioral crown vs carrier full mapped (one compile each)."""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_M3_PER_TICK_DRIFT_RECEIPT_v1.json"
_TICK_TOL_M = 0.012
_CUM_TOL_M = 0.012


def _tick_err(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.sqrt(
        (float(a["x_m"]) - float(b["x_m"])) ** 2
        + (float(a["y_m"]) - float(b["y_m"])) ** 2
        + (float(a["z_m"]) - float(b["z_m"])) ** 2
    )


def _cum_rmse(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return float("inf")
    err = sum(r["err_m"] ** 2 for r in rows)
    return math.sqrt(err / len(rows))


def evaluate_m3_per_tick_drift(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))

    n = int(os.environ.get("CLIFFORD_MAPPED_TICKS", "50"))
    os.environ["CLIFFORD_MAPPED_ALU_MMIO"] = "1"
    os.environ.pop("CLIFFORD_MAPPED_ALU_HYBRID", None)
    os.environ["CLIFFORD_MAPPED_TICKS"] = str(n)

    from scripts.chip.clifford_iron_mmio_driver_v0 import (
        run_iron_world_motion_mapped_alu_mmio_sim,
        run_iron_world_motion_structural_sim,
    )

    reference = run_iron_world_motion_structural_sim(backend="iverilog")
    full = run_iron_world_motion_mapped_alu_mmio_sim(backend="iverilog")
    b_ticks = list(reference.get("ticks") or [])
    f_ticks = list(full.get("ticks") or [])
    m = min(len(b_ticks), len(f_ticks), n)

    per_tick: list[dict[str, Any]] = []
    first_fail: int | None = None
    max_err = 0.0
    max_tick = -1
    for i in range(m):
        err = _tick_err(b_ticks[i], f_ticks[i])
        max_err = max(max_err, err)
        if err > max_err - 1e-12:
            max_tick = i
        row = {
            "tick": int(b_ticks[i]["tick"]),
            "meters": float(b_ticks[i].get("meters", 0)),
            "err_m": round(err, 6),
            "behavioral_x": round(float(b_ticks[i]["x_m"]), 6),
            "mapped_x": round(float(f_ticks[i]["x_m"]), 6),
            "tick_ok": err < _TICK_TOL_M,
        }
        per_tick.append(row)
        if first_fail is None and err >= _TICK_TOL_M:
            first_fail = int(b_ticks[i]["tick"])

    cum_rmse = _cum_rmse(per_tick)
    hybrid_rmse: float | None = None
    if os.environ.get("CLIFFORD_M3_SCAN_HYBRID", "").strip() in ("1", "true", "yes"):
        os.environ["CLIFFORD_MAPPED_ALU_HYBRID"] = "1"
        hybrid = run_iron_world_motion_mapped_alu_mmio_sim(backend="iverilog")
        h_ticks = list(hybrid.get("ticks") or [])
        hm = min(len(b_ticks), len(h_ticks), m)
        if hm > 0:
            hybrid_rmse = math.sqrt(
                sum(_tick_err(b_ticks[i], h_ticks[i]) ** 2 for i in range(hm)) / hm
            )

    verdict = "M3_PER_TICK_DRIFT_PASS" if cum_rmse < _CUM_TOL_M and first_fail is None else "M3_PER_TICK_DRIFT_FAIL"
    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_M3_PER_TICK_DRIFT_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "ticks_compared": m,
        "cumulative_rmse_m": round(cum_rmse, 6) if math.isfinite(cum_rmse) else None,
        "first_fail_tick": first_fail,
        "max_tick_err_m": round(max_err, 6),
        "max_err_tick": max_tick,
        "hybrid_rmse_m": round(hybrid_rmse, 6) if hybrid_rmse is not None else None,
        "per_tick": per_tick,
        "honesty": {
            "crown_path": "structural_synth_mmio",
            "carrier_path": "mapped_full_alu_mmio",
            "tick_tol_m": _TICK_TOL_M,
            "cum_tol_m": _CUM_TOL_M,
        },
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_m3_per_tick_drift()
    print(json.dumps({k: v for k, v in out.items() if k != "per_tick"}, indent=2))
    raise SystemExit(0 if out["verdict"] == "M3_PER_TICK_DRIFT_PASS" else 1)
