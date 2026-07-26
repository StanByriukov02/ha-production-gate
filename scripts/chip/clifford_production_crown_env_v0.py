"""Production crown env — Clifford crown default backend (chip = carrier only)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_GATE = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_PRODUCTION_CROWN_GATE_RECEIPT_v1.json"


def production_crown_status() -> dict[str, Any]:
    if not _GATE.is_file():
        return {"ready": False, "verdict": "missing"}
    doc = json.loads(_GATE.read_text(encoding="utf-8"))
    verdict = doc.get("verdict", "")
    ready = verdict in ("PRODUCTION_CROWN_GATE_READY", "PRODUCTION_CROWN_GATE_PASS")
    return {
        "ready": ready,
        "verdict": verdict,
        "law": doc.get("law", {}),
        "waiting_m3": (doc.get("honesty") or {}).get("waiting_m3_for_full_pass"),
    }


def apply_production_crown_env(*, force: bool = False) -> bool:
    """Set CLIFFORD_BACKEND=verilator when production crown gate is READY/PASS."""
    st = production_crown_status()
    if not st["ready"] and not force:
        return False
    os.environ["CLIFFORD_BACKEND"] = "verilator"
    return True


def production_crown_context() -> dict[str, Any]:
    st = production_crown_status()
    return {
        "clifford_alu_is_crown": True,
        "chip_is_carrier": True,
        "production_crown_env_applied": apply_production_crown_env() if st["ready"] else False,
        "clifford_backend": os.environ.get("CLIFFORD_BACKEND"),
        "gate_verdict": st["verdict"],
    }
