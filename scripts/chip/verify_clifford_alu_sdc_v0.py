"""Verify Clifford ALU SDC contract matches φ-FSM macro-cycle (P5.7)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_FIX = _REPO / "fixtures" / "chip"
_SDC = _FIX / "clifford_alu_macro_cycle_v0.sdc"
_MANIFEST = _FIX / "clifford_alu_timing_manifest_v1.json"
_FSM = _FIX / "clifford_phi_fsm_v0.v"
_TOP = _FIX / "clifford_alu_top_v0.v"


def _phi_latch_phases() -> tuple[int, int, int]:
    text = _FSM.read_text(encoding="utf-8")
    ex1_phi = ex3_phi = wb_phi = None
    for m in re.finditer(r"3'd(\d+):\s*ex1_latch\s*=", text):
        ex1_phi = int(m.group(1))
    for m in re.finditer(r"3'd(\d+):\s*ex3_latch\s*=", text):
        ex3_phi = int(m.group(1))
    for m in re.finditer(r"3'd(\d+):\s*begin\s*\n\s*ex2_recovery\s*=\s*1'b1;\s*\n\s*wb_eval", text):
        wb_phi = int(m.group(1))
    if ex1_phi is None or ex3_phi is None or wb_phi is None:
        raise ValueError("phi FSM latch phases not found")
    return ex1_phi, ex3_phi, wb_phi


def verify_clifford_alu_sdc() -> dict[str, Any]:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    sdc = _SDC.read_text(encoding="utf-8")
    top = _TOP.read_text(encoding="utf-8")

    ex1_phi, ex3_phi, wb_phi = _phi_latch_phases()
    mc = manifest["macro_cycle"]
    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "id": "sdc_file_present",
            "pass": _SDC.is_file(),
        }
    )
    checks.append(
        {
            "id": "manifest_present",
            "pass": _MANIFEST.is_file(),
        }
    )

    for tok in manifest["required_sdc_tokens"]:
        checks.append({"id": f"sdc_token_{tok}", "pass": tok in sdc, "detail": tok})

    setup_m = re.search(r"set\s+MCP_EX1_EX3_SETUP\s+(\d+)", sdc)
    hold_m = re.search(r"set\s+MCP_EX1_EX3_HOLD\s+(\d+)", sdc)
    setup = int(setup_m.group(1)) if setup_m else -1
    hold = int(hold_m.group(1)) if hold_m else -1
    cycles = ex3_phi - ex1_phi

    checks.append(
        {
            "id": "phi_ex1_ex3_cycle_match",
            "pass": setup == cycles == mc["multicycle_setup"] == mc["cycles_ex1_to_ex3"],
            "detail": f"phi{ex1_phi}→phi{ex3_phi} setup={setup} exp={cycles}",
        }
    )
    checks.append(
        {
            "id": "multicycle_hold_setup_minus_one",
            "pass": hold == setup - 1 == mc["multicycle_hold"],
            "detail": f"hold={hold} setup={setup}",
        }
    )
    checks.append(
        {
            "id": "wb_eval_phi6",
            "pass": wb_phi == mc["wb_eval_phi"],
            "detail": f"wb_eval@phi{wb_phi}",
        }
    )

    for inst in manifest["ex_pipe_instances"]:
        checks.append(
            {
                "id": f"top_{inst}",
                "pass": inst in top,
                "detail": inst,
            }
        )

    multicycle_count = len(re.findall(r"set_multicycle_path\s+-setup", sdc))
    checks.append(
        {
            "id": "multicycle_path_count",
            "pass": multicycle_count >= 5,
            "detail": f"setup_paths={multicycle_count}",
        }
    )

    ok = all(c["pass"] for c in checks)
    return {
        "verdict": "SDC_CONTRACT_PASS" if ok else "SDC_CONTRACT_FAIL",
        "checks": checks,
        "phi": {"ex1_latch": ex1_phi, "ex3_latch": ex3_phi, "wb_eval": wb_phi},
        "honesty": manifest.get("honesty", {}),
    }


if __name__ == "__main__":
    print(json.dumps(verify_clifford_alu_sdc(), indent=2))
