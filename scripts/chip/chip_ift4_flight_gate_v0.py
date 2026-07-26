"""CHIP IFT-4 flight gate — inject flight thinking; TABU VPS/audit theater.

Machine gate (not md canon). State: CHIP_IFT4_FLIGHT_STATE_v1.json
Rule: hook `hook_before_submit_chip_ift4_flight` only (no .mdc)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STATE = _CHIP / "CHIP_IFT4_FLIGHT_STATE_v1.json"

_CHIP_TRIGGERS = re.compile(
    r"(?i)(\bchip\b|ift[\s-]?[34]|combination|moon.?iron|co-?qual|envelope|"
    r"го\s*[abc]?|factory|heatmap|integrated.mission|robot.tunnel|"
    r"condition.matrix|production.ladder)",
)

_VPS_TABU = re.compile(
    r"(?i)(vps|ssh\s*ubuntu@|run_temporal.*vps|deploy.*vps|3\.123\.|35\.158\.)",
)

INJECT_FLIGHT = """CHIP IFT-4 + FACTORY DAY TRIGGER (in-world · LOCKED 2026-07-03)

**Secret sauce (not pipeline):** cross-ledger hash · 7-physics combination cell · grid falsifiers · platonic slot gaps · REPLACE $M sim/flight in-world.

30s gate: DELETE wrong req · REPLACE external tool · INVENT iron artifact · OBSERVE · FALSIFY · TIER honest
SPRINT gap #1: DRAM_OFF_CHIP_GB → behavioral host Verilator HIL (not BOM GB)
NEXT: cryo power fixture · HBM carrier MMIO iron

IRON: verilator/yosys/tcad/trace before new .py · >2 py without L0-L4 → STOP
TABU: foundry nag · pytest=iron · outbound north · matrix re-audit · invented GB · VPS

Canon: docs/agent_workflow/CHIP_FACTORY_SECRET_SAUCE_DAY_TRIGGER_V1.md
Marker handoff: REPLACE / INVENT / IRON_RAN / FALSIFIER"""

INJECT_VPS_BLOCK = """CHIP IFT-4 GATE — VPS TABU
VPS/SSH is NOT chip IFT-4 · NOT engineering flight · PARK infra only.
Redo plan: local iron segment (S1-S3). operator-zero-network applies."""


def _ift3_factory_green() -> bool:
    heat = _CHIP / "CHIP_COMBINATION_CELLS_HEATMAP_RECEIPT_v1.json"
    matrix = _CHIP / "CHIP_IFT3_COMBINATION_MATRIX_RECEIPT_v1.json"
    if not heat.is_file() or not matrix.is_file():
        return False
    h = json.loads(heat.read_text(encoding="utf-8"))
    m = json.loads(matrix.read_text(encoding="utf-8"))
    return (
        h.get("verdict") == "COMBINATION_HEATMAP_PASS"
        and not h.get("quick", True)
        and m.get("verdict") == "COMBINATION_MATRIX_PASS"
    )


def evaluate(*, prompt: str = "") -> dict[str, Any]:
    vps_violation = bool(_VPS_TABU.search(prompt))
    chip_context = bool(_CHIP_TRIGGERS.search(prompt))
    ift3_green = _ift3_factory_green()

    level = "critical" if vps_violation else ("warn" if chip_context and not ift3_green else "none")
    inject = ""
    if vps_violation:
        inject = INJECT_VPS_BLOCK
    elif chip_context:
        inject = INJECT_FLIGHT

    state: dict[str, Any] = {
        "state_id": "CHIP_IFT4_FLIGHT_STATE_v1",
        "flight_level": level,
        "ift3_factory_green": ift3_green,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "vps_tabu_fired": vps_violation,
        "inject": inject,
        "segments": ["S1_coqual_stress", "S2_moon_full_local", "S3_temporal_local"],
    }
    _CHIP.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def prompt_context(prompt: str) -> str:
    if not _CHIP_TRIGGERS.search(prompt) and not _VPS_TABU.search(prompt):
        return ""
    state = evaluate(prompt=prompt)
    parts = [state.get("inject") or ""]
    try:
        import importlib.util

        dt_path = _REPO / "scripts" / "chip" / "chip_factory_day_trigger_gate_v0.py"
        spec = importlib.util.spec_from_file_location("chip_factory_day_trigger_gate_v0", dt_path)
        dt_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dt_mod)
        dt = dt_mod.evaluate(prompt=prompt)
        if dt.get("inject") and dt["inject"] not in parts[0]:
            parts.append(dt["inject"])
    except Exception:
        pass
    return "\n\n".join(p for p in parts if p)


def run_gate() -> dict[str, Any]:
    state = evaluate(prompt="")
    verdict = "PASS" if state["flight_level"] != "critical" else "FAIL"
    return {"verdict": verdict, "state": state}


if __name__ == "__main__":
    import sys

    out = run_gate()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 1)
