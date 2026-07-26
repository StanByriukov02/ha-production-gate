"""Clifford Python glue gate — twin/world motion must not compute geo_prod in Python.

Machine gate (not md theater). Writes CLIFFORD_PYTHON_GLUE_STATE_v1.json.
Canon: docs/agent_workflow/CLIFFORD_ALU_BUILD_STACK_V1.md §6
Rule: .cursor/rules/clifford-work-iron-first.mdc
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STATE = _CHIP / "CLIFFORD_PYTHON_GLUE_STATE_v1.json"

# Paths where geo_prod / rigid_pose in Python is allowed (mint, bench, library).
_ALLOW_PREFIXES = (
    "scripts/chip/gen_clifford",
    "scripts/chip/clifford_pga8_oracle",
    "scripts/chip/clifford_iron_mmio_driver",
    "dogfood_platform/clifford_pga8_motor_v1.py",
    "dogfood_platform/chip_clifford_lc2_bench_pose_probe_v1.py",
    "dogfood_platform/dogfood_twin_clifford_pose_bind_v1.py",
    "dogfood_platform/dogfood_twin_clifford_world_iron_v1.py",
    "tests/",
)

# Twin motion stack — Python orchestrates iron+cxx only.
_WATCH_REL = (
    "dogfood_platform/dogfood_twin_clifford_world_engine_v1.py",
    "dogfood_platform/dogfood_twin_clifford_motor_stack_v1.py",
    "dogfood_platform/dogfood_twin_clifford_runtime_gate_v1.py",
)

_ALLOW_PREFIXES = _ALLOW_PREFIXES + ("scripts/chip/clifford_world_motion_iron_v0.py",)

_FORBIDDEN_IN_WATCH = (
    "geo_prod_coeffs",
    "rigid_pose_body_m",
    "_geo_prod_rail",
    "apply_point_m(",
    ".rigid_pose(",
    "_cxx_line(",
)

_WORLD_ENGINE_REQUIRED = (
    "build_world_combat_rail",
    "python_does_not_geo_prod",
    "iron_rtl_and_cxx_not_python_gp",
)

_MOTION_JSON = _REPO / "fixtures" / "twin" / "clifford_world_motion_v1.json"
_ENGINE_RECEIPT = _REPO / "results" / "platform_bpass" / "moon" / "ROBOT_IFT2_CLIFFORD_WORLD_ENGINE_RECEIPT_v1.json"

_IRON_FIRST_PROMPT = re.compile(
    r"clifford|geo_prod|world.runtime|dogfood_twin_clifford|world.motion|combat.rail|iron.rtl|motor.stack",
    re.I,
)

INJECT_BLOCK = """MODE: CLIFFORD_IRON_FIRST (glue gate FAIL)
Python glue gate blocked twin Clifford motion — geo_prod must run on iron RTL + cxx, not Python loops.
Fix: dogfood_twin_clifford_world_iron_v1 · gen_clifford_world_motion_iron_v0 · clifford_world_motion_rail.exe
Run: python scripts/chip/clifford_python_glue_gate_v0.py
State: results/platform_bpass/chip/CLIFFORD_PYTHON_GLUE_STATE_v1.json
TABU: MotorPGA8.rigid_pose / geo_prod_coeffs in dogfood_twin_clifford_world_engine*"""

INJECT_OK = """MODE: CLIFFORD_IRON_FIRST (glue gate PASS)
Twin motion compute = iron RTL MMIO + cxx batch · Python = mint vectors + receipts only.
Primary: fixtures/chip/clifford_world_motion_rtl_tb_v0.v · clifford_world_motion_rail.exe
Marker: IRON_LAYER: sim|cxx|receipt · PY_GLUE: receipt only"""


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _is_allowed(rel: str) -> bool:
    return any(rel.startswith(p) or p in rel for p in _ALLOW_PREFIXES)


def _scan_watch_file(rel: str) -> list[str]:
    path = _REPO / rel.replace("/", "\\")
    if not path.is_file():
        return []
    if _is_allowed(rel):
        return []
    text = path.read_text(encoding="utf-8")
    violations: list[str] = []
    for pat in _FORBIDDEN_IN_WATCH:
        if pat in text:
            violations.append(f"{rel}: forbidden `{pat}`")
    if rel.endswith("dogfood_twin_clifford_world_engine_v1.py"):
        for req in _WORLD_ENGINE_REQUIRED:
            if req not in text:
                violations.append(f"{rel}: missing required `{req}`")
    return violations


def _check_motion_artifacts() -> list[str]:
    issues: list[str] = []
    if _MOTION_JSON.is_file():
        doc = json.loads(_MOTION_JSON.read_text(encoding="utf-8"))
        layers = doc.get("compute_layers") or {}
        iron = layers.get("iron") or doc.get("iron_sim") or {}
        cxx = layers.get("cxx") or {}
        if not doc.get("honesty", {}).get("python_does_not_geo_prod"):
            issues.append("clifford_world_motion_v1.json: python_does_not_geo_prod != true")
        if layers.get("iron", {}).get("status") != "PASS" and iron.get("backend") is None:
            issues.append("motion json iron layer missing PASS")
        if cxx.get("status") != "PASS":
            issues.append(f"motion json cxx status={cxx.get('status')}")
        if layers.get("iron_cxx_parity_ok") is False:
            issues.append("motion json iron_cxx_parity_ok false")
        chip_rcpt = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_WORLD_MOTION_IRON_RECEIPT_v1.json"
        if chip_rcpt.is_file():
            chip = json.loads(chip_rcpt.read_text(encoding="utf-8"))
            if chip.get("verdict") != "PASS":
                issues.append(f"chip iron receipt verdict={chip.get('verdict')}")
    return issues


def evaluate(*, prompt: str = "") -> dict[str, Any]:
    violations: list[str] = []
    for rel in _WATCH_REL:
        violations.extend(_scan_watch_file(rel))
    violations.extend(_check_motion_artifacts())

    level = "none" if not violations else "critical"
    state: dict[str, Any] = {
        "state_id": "CLIFFORD_PYTHON_GLUE_STATE_v1",
        "glue_level": level,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "violations": violations,
        "watch_files": list(_WATCH_REL),
        "inject": "" if level == "none" else INJECT_BLOCK,
        "inject_ok": INJECT_OK if level == "none" else "",
    }
    _CHIP.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def prompt_context(prompt: str) -> str:
    state = evaluate(prompt=prompt)
    if not _IRON_FIRST_PROMPT.search(prompt):
        return ""
    if state["glue_level"] != "none":
        return state["inject"]
    return state["inject_ok"]


def file_edit_context(rel_posix: str) -> str:
    if not any(m in rel_posix for m in ("dogfood_twin_clifford", "fixtures/twin/clifford_world_motion")):
        return ""
    state = evaluate(prompt="")
    if state["glue_level"] != "none":
        return state["inject"] + "\nViolations:\n" + "\n".join(f"- {v}" for v in state["violations"])
    return ""


def run_gate() -> dict[str, Any]:
    state = evaluate(prompt="")
    verdict = "PASS" if state["glue_level"] == "none" else "FAIL"
    return {"verdict": verdict, "state": state}


if __name__ == "__main__":
    out = run_gate()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 1)
