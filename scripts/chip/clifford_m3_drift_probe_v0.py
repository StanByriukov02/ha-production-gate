"""M3 drift probe — hybrid vs full mapped ALU MMIO per-tick RMSE (diagnostic, not signoff)."""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_M3_DRIFT_PROBE_RECEIPT_v1.json"
_TOL_M = 0.012


def _run_layer(*, hybrid: bool, ticks: int) -> list[dict[str, Any]]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_iron_mmio_driver_v0 import run_iron_world_motion_mapped_alu_mmio_sim

    os.environ["CLIFFORD_MAPPED_TICKS"] = str(ticks)
    os.environ["CLIFFORD_MAPPED_ALU_MMIO"] = "1"
    if hybrid:
        os.environ["CLIFFORD_MAPPED_ALU_HYBRID"] = "1"
    else:
        os.environ.pop("CLIFFORD_MAPPED_ALU_HYBRID", None)
    sim = run_iron_world_motion_mapped_alu_mmio_sim(backend="iverilog")
    return list(sim.get("ticks") or [])


def _rmse(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return float("inf")
    err = 0.0
    for i in range(n):
        for k in ("x_m", "y_m", "z_m"):
            err += (float(a[i][k]) - float(b[i][k])) ** 2
    return math.sqrt(err / (n * 3))


def evaluate_m3_drift_probe(*, write: bool = True) -> dict[str, Any]:
    tick_caps = [int(x) for x in os.environ.get("CLIFFORD_DRIFT_PROBE_TICKS", "1").split(",") if x.strip()]
    rows: list[dict[str, Any]] = []
    for n in tick_caps:
        hybrid_ticks = _run_layer(hybrid=True, ticks=n)
        full_ticks = _run_layer(hybrid=False, ticks=n)
        rmse = _rmse(hybrid_ticks, full_ticks)
        rows.append(
            {
                "ticks": n,
                "hybrid_count": len(hybrid_ticks),
                "full_mapped_count": len(full_ticks),
                "hybrid_vs_full_rmse_m": round(rmse, 6) if math.isfinite(rmse) else None,
                "drift_ok": math.isfinite(rmse) and rmse < _TOL_M,
            }
        )

    worst = max((r["hybrid_vs_full_rmse_m"] or float("inf")) for r in rows) if rows else float("inf")
    all_ok = bool(rows) and all(r.get("drift_ok") for r in rows)
    verdict = "M3_DRIFT_PROBE_PASS" if all_ok and math.isfinite(worst) and worst < _TOL_M else "M3_DRIFT_PROBE_WARN"
    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_M3_DRIFT_PROBE_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "rows": rows,
        "honesty": {
            "not_m3_signoff": True,
            "purpose": "local hybrid vs full mapped pose delta before VPS 50-tick",
        },
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_m3_drift_probe()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] in ("M3_DRIFT_PROBE_PASS", "M3_DRIFT_PROBE_WARN") else 1)
