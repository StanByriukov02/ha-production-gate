"""Chip Python glue gate — GAP/memory hops need iron evidence, not pytest theater.

Machine gate (not md canon). Writes CHIP_PYTHON_GLUE_STATE_v1.json
Canon: OPERATOR_CURSOR_AGENT_MODES_V1.md § WORK + iron-first
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STATE = _CHIP / "CHIP_PYTHON_GLUE_STATE_v1.json"

_GAP_PROMPT = re.compile(
    r"(?i)(\bgap\b|dram.derived|cache.?l2|invent.flight|aggregate.pressure|"
    r"body.memory|nasa.cryo|chip.*memory|envelope.flight|ift[\s-]?[45])",
)

# L5 glue allowed — must not be sole proof.
_L5_GLUE_ONLY = (
    "chip_dram_derived_capacity_bind_v1.py",
    "chip_cache_l2_on_derived_bind_v1.py",
    "chip_nasa_cryo_gap_named_bind_v1.py",
)

# Iron thermometers required for GAP invent flight PASS.
_REQUIRED_IRON = (
    "foc_isr_trace",
    "tcad_deck_variant",
    "weste_p_dyn",
    "iverilog_pose",
)

INJECT_FAIL = """CHIP IRON-FIRST GATE (glue FAIL)
TABU: pytest-only · run_* bind PASS без iron · JSON verdict без trace/sim/synth.

Пирамида: L1 trace_sim/iverilog · L2 tcad variant · L3 weste · L5 receipt LAST.
GAP invent: python -m dogfood_platform.chip_gap_invent_flight_v1 — только после iron hops.

Run: python scripts/chip/chip_python_glue_gate_v0.py
State: results/platform_bpass/chip/CHIP_PYTHON_GLUE_STATE_v1.json
Stop: >2 новых .py за turn без verilator/yosys/trace — STOP replan."""

INJECT_OK = """CHIP IRON-FIRST (glue gate PASS)
Python = L5 receipt glue · PASS только зеркалит iron на диске.
GAP flight: S1 combination iron + S2 tunnel pose iverilog · не pytest assert dict.
Marker: IRON_RAN: trace_sim|tcad|iverilog · PY_GLUE: receipt only"""


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _gap_flight_iron() -> tuple[list[str], list[str]]:
    """Return (iron_present, violations)."""
    present: list[str] = []
    violations: list[str] = []

    flight = _CHIP / "CHIP_GAP_INVENT_FLIGHT_RECEIPT_v1.json"
    if not flight.is_file():
        violations.append("CHIP_GAP_INVENT_FLIGHT_RECEIPT_v1.json missing")
        return present, violations

    doc = _load(flight)
    if doc.get("verdict") == "GAP_INVENT_FLIGHT_PASS":
        ev = doc.get("iron_evidence") or {}
        for key in _REQUIRED_IRON:
            if ev.get(key, {}).get("pass"):
                present.append(key)
            else:
                violations.append(f"GAP flight missing iron evidence: {key}")

    cells = _CHIP / "CHIP_GAP_INVENT_COMBINATION_CELLS_BIND_v1.json"
    if cells.is_file():
        for cell in _load(cells).get("cells", []):
            irons = {s.get("iron") for s in cell.get("iron_steps", [])}
            if "foc_isr_trace" in irons:
                present.append("foc_isr_trace_cells")
            if "tcad_deck_variant" in irons:
                present.append("tcad_deck_variant_cells")

    pose = _CHIP / "CHIP_CLIFFORD_LC2_BENCH_POSE_PROBE_RECEIPT_v1.json"
    if pose.is_file():
        p = _load(pose)
        if p.get("verdict") == "LC2_POSE_PROBE_PASS" and (p.get("honesty") or {}).get("iron_rtl_in_loop"):
            present.append("iverilog_pose")
        elif doc.get("verdict") == "GAP_INVENT_FLIGHT_PASS":
            violations.append("pose probe iron loop not closed on disk")

    return present, violations


def _pytest_theater_scan() -> list[str]:
    """Flag unit tests that only call run_* bind without iron chain."""
    issues: list[str] = []
    tests = _REPO / "tests"
    for name in (
        "test_chip_dram_derived_capacity_bind_v1.py",
        "test_chip_cache_l2_on_derived_bind_v1.py",
        "test_chip_nasa_cryo_gap_named_bind_v1.py",
    ):
        if (tests / name).is_file():
            issues.append(f"theater test present: tests/{name} — delete; use test_chip_gap_invent_flight_v1")
    return issues


def evaluate(*, prompt: str = "") -> dict[str, Any]:
    iron_present, violations = _gap_flight_iron()
    violations.extend(_pytest_theater_scan())

    level = "none" if not violations else "critical"
    state: dict[str, Any] = {
        "state_id": "CHIP_PYTHON_GLUE_STATE_v1",
        "glue_level": level,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "iron_present": sorted(set(iron_present)),
        "required_iron": list(_REQUIRED_IRON),
        "violations": violations,
        "l5_glue_modules": list(_L5_GLUE_ONLY),
        "inject": "" if level == "none" else INJECT_FAIL,
        "inject_ok": INJECT_OK if level == "none" else "",
    }
    _CHIP.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def prompt_context(prompt: str) -> str:
    if not _GAP_PROMPT.search(prompt):
        return ""
    state = evaluate(prompt=prompt)
    if state["glue_level"] != "none":
        return state["inject"] + "\n" + "\n".join(f"- {v}" for v in state["violations"])
    return state["inject_ok"]


def run_gate() -> dict[str, Any]:
    state = evaluate(prompt="")
    return {"verdict": "PASS" if state["glue_level"] == "none" else "FAIL", "state": state}


if __name__ == "__main__":
    out = run_gate()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 1)
