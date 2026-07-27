"""Coupling cell wear oracle v1 — PY_GLUE cited-bind oracle (not engine crown).

Engine truth = C++ parity receipt CHIP_COUPLING_CELL_WEAR_PARITY_RECEIPT_v1.json
TABU: claim MEASURED silicon · use without parity PASS.
"""
from __future__ import annotations

from typing import Any

RADIATION_STRESS_SCALE_MV = 50.0
INGRESS_STRESS_SCALE = 0.3
MAX_DUTY_LOSS = 0.25
MIN_DUTY_CAP = 0.5
ORACLE = "CITED_BIND"


def evaluate_wear_cell(*, ingress_mult: float, radiation_delta_vth_mv: float) -> dict[str, Any]:
    ingress_term = max(0.0, float(ingress_mult) - 1.0) * INGRESS_STRESS_SCALE
    rad_term = max(0.0, float(radiation_delta_vth_mv)) / RADIATION_STRESS_SCALE_MV
    stress = min(1.0, ingress_term + rad_term)
    duty_cap = max(MIN_DUTY_CAP, 1.0 - stress * MAX_DUTY_LOSS)
    return {
        "stress_index": round(stress, 4),
        "effective_duty_cap": round(duty_cap, 4),
        "headroom_loss_pct": round((1.0 - duty_cap) * 100.0, 2),
    }


def load_parity_truth_row(case_id: str = "terminal_lunar_crater") -> dict[str, Any] | None:
    """Primary engine row from parity receipt when PASS."""
    from pathlib import Path

    import json

    repo = Path(__file__).resolve().parents[1]
    receipt = repo / "results" / "platform_bpass" / "chip" / "CHIP_COUPLING_CELL_WEAR_PARITY_RECEIPT_v1.json"
    if not receipt.is_file():
        return None
    doc = json.loads(receipt.read_text(encoding="utf-8"))
    if doc.get("verdict") != "COUPLING_CELL_WEAR_PARITY_PASS":
        return None
    for row in doc.get("cases") or []:
        if str(row.get("id")) == case_id:
            return row.get("outputs")
    return None
