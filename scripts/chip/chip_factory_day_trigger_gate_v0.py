"""Chip factory day trigger gate — secret sauce inject; LOCKED 2026-07-03.

Machine gate (not md canon). State: CHIP_FACTORY_DAY_TRIGGER_STATE_v1.json
Canon: docs/agent_workflow/CHIP_FACTORY_SECRET_SAUCE_DAY_TRIGGER_V1.md
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STATE = _CHIP / "CHIP_FACTORY_DAY_TRIGGER_STATE_v1.json"
_CANON = "docs/agent_workflow/CHIP_FACTORY_SECRET_SAUCE_DAY_TRIGGER_V1.md"

_CHIP_TRIGGERS = re.compile(
    r"(?i)(\bchip\b|dogfood|factory|gap|dram|cache.?l2|hbm|carrier|cryo|"
    r"combination|moon|matrix|invent|iron|tomorrow|envelope|platonic)",
)

ENGINEERING_GAPS: tuple[str, ...] = (
    "DRAM_OFF_CHIP_GB",
    "invent_wider_bus_tile",
    "invent_lpddr_offchip",
    "invent_hbm_compute_die",
    "NASA-CRYO-COTS-GAP",
    "REGFILE_DEPTH",
    "POPE_SCRATCHPAD_LAW",
    "CACHE_L2_KB",
    "ISR_HOT_PATH_US",
    "SRAM_TILE_KB",
)

SPRINT_ORDER: tuple[str, ...] = (
    "DRAM_OFF_CHIP_GB",
    "NASA-CRYO-COTS-GAP",
    "invent_hbm_compute_die",
    "CACHE_L2_KB",
    "SRAM_TILE_KB",
)

INJECT = """CHIP FACTORY DAY TRIGGER (LOCKED 2026-07-03) — SECRET SAUCE

NOT pipeline 1+1. Sauce = 5 mechanisms:
  1 cross-ledger motion hash (chip↔robot↔world↔crown) — twin falsifier
  2 combination cell = hypothesis × 7 physics (tcad·trace·weste·linker·decap·thermal·mono)
  3 grid falsifiers (loud FAIL · non-monotone shield) — factory proves alive
  4 platonic A↔B slot gaps — INVENT map, not foundry excuse
  5 REPLACE $M sim/flight with in-world iron + better observability

30s gate EVERY hop:
  DELETE wrong req · REPLACE which external tool · INVENT iron artifact · OBSERVE · FALSIFY · TIER honest
  STOP: >2 new .py/turn without L0-L4 iron

SPRINT #3 gap: invent_hbm_compute_die → **CARRIER_HBM_MMIO_HIL_PASS** (iverilog MCU vs carrier)
NEXT: CACHE_L2_KB + SRAM_TILE_KB → **CACHE_SRAM_SPRINT4_HIL_PASS** (L2 hit/miss + weste area)
SPRINT #5 gap: invent_wider_bus_tile → **WIDER_BUS_TILE_HIL_PASS** (G1 bus sweep · congestion @ 128b)
SPRINT #6 gap: invent_lpddr_offchip → **LPDDR_HOST_RING_HIL_PASS** (host ring ladder · twin≠MCU)
SPRINT #7 gap: REGFILE_DEPTH → **REGFILE_DEPTH_POLICY_HIL_PASS** (µs vs depth · serial MCU falsifier)
SPRINT #9 gap: ISR_HOT_PATH_US → **ISR_HOT_PATH_HIL_PASS** (trace path µs spread)
BLOCK C: **BLOCK_C_COQUAL_PASS**
BLOCK D: **BLOCK_D_COMPUTE_PASS**
NEXT: **G6 visual** — full chip↔robot↔package module sheet (our N from slots · transistors)

TABU: foundry nag · pytest=iron · outbound north · re-audit matrix · FAIL=PASS · plans in chat only
FOCUS: vault `CHIP_ASSEMBLY_VISUAL_PROGRAM_V1` · G6.1 three reference modules

Canon: docs/agent_workflow/CHIP_FACTORY_SECRET_SAUCE_DAY_TRIGGER_V1.md
Marker: REPLACE / INVENT / IRON_RAN / FALSIFIER required in handoff"""


def _matrix_pass() -> bool:
    path = _CHIP / "CHIP_CONDITION_MATRIX_AUDIT_v1.json"
    if not path.is_file():
        return False
    doc = json.loads(path.read_text(encoding="utf-8"))
    summary = doc.get("summary") or {}
    return doc.get("verdict") == "CONDITION_MATRIX_AUDIT_PASS" and summary.get("pass_rows", 0) >= 34


def evaluate(*, prompt: str = "") -> dict[str, Any]:
    chip_context = bool(_CHIP_TRIGGERS.search(prompt))
    matrix_ok = _matrix_pass()
    done: list[str] = []
    if (_CHIP / "CHIP_DRAM_HOST_HIL_RECEIPT_v1.json").is_file():
        done.append("DRAM_OFF_CHIP_GB")
    if (_CHIP / "CHIP_NASA_CRYO_POWER_HIL_RECEIPT_v1.json").is_file():
        done.append("NASA-CRYO-COTS-GAP")
    if (_CHIP / "CHIP_COMPUTE_CARRIER_HBM_MMIO_HIL_RECEIPT_v1.json").is_file():
        done.append("invent_hbm_compute_die")
    if (_CHIP / "CHIP_CACHE_SRAM_SPRINT4_HIL_RECEIPT_v1.json").is_file():
        done.append("CACHE_L2_KB+SRAM_TILE_KB")
    if (_CHIP / "CHIP_WIDER_BUS_TILE_HIL_RECEIPT_v1.json").is_file():
        done.append("invent_wider_bus_tile")
    if (_CHIP / "CHIP_LPDDR_HOST_RING_HIL_RECEIPT_v1.json").is_file():
        done.append("invent_lpddr_offchip")
    if (_CHIP / "CHIP_REGFILE_DEPTH_POLICY_HIL_RECEIPT_v1.json").is_file():
        done.append("REGFILE_DEPTH")
    if (_CHIP / "CHIP_POPE_SCRATCHPAD_LAW_HIL_RECEIPT_v1.json").is_file():
        done.append("POPE_SCRATCHPAD_LAW")
    if (_CHIP / "CHIP_ISR_HOT_PATH_HIL_RECEIPT_v1.json").is_file():
        done.append("ISR_HOT_PATH_US")
    if (_CHIP / "CHIP_BLOCK_C_COQUAL_RECEIPT_v1.json").is_file():
        block_c = json.loads((_CHIP / "CHIP_BLOCK_C_COQUAL_RECEIPT_v1.json").read_text(encoding="utf-8"))
        if block_c.get("verdict") == "BLOCK_C_COQUAL_PASS":
            done.append("BLOCK_C_COQUAL")
    if (_CHIP / "CHIP_BLOCK_D_COMPUTE_RECEIPT_v1.json").is_file():
        block_d = json.loads((_CHIP / "CHIP_BLOCK_D_COMPUTE_RECEIPT_v1.json").read_text(encoding="utf-8"))
        if block_d.get("verdict") == "BLOCK_D_COMPUTE_PASS":
            done.append("BLOCK_D_COMPUTE")
    if len(done) >= 10:
        active_gap = "CHIP_ASSEMBLY_VISUAL_G6"
    elif len(done) >= 9:
        active_gap = "BLOCK_C_COQUAL"
    elif len(done) >= 8:
        active_gap = "ISR_HOT_PATH_US"
    elif len(done) >= 7:
        active_gap = "POPE_SCRATCHPAD_LAW"
    elif len(done) >= 6:
        active_gap = "REGFILE_DEPTH"
    elif len(done) >= 5:
        active_gap = "invent_lpddr_offchip"
    elif len(done) >= 4:
        active_gap = "invent_wider_bus_tile"
    elif len(done) >= 3:
        active_gap = "CACHE_L2_KB+SRAM_TILE_KB"
    elif len(done) >= 2:
        active_gap = SPRINT_ORDER[2]
    elif len(done) == 1:
        active_gap = SPRINT_ORDER[1]
    else:
        active_gap = SPRINT_ORDER[0]

    if active_gap == "CACHE_L2_KB+SRAM_TILE_KB":
        focus = "in-world REPLACE — L2 hit/miss iron + SRAM weste area (DRAM+cryo+HBM HIL done)"
    elif active_gap == "invent_lpddr_offchip":
        focus = "in-world REPLACE — host ring LPDDR ladder (data host axis)"
    elif active_gap == "BLOCK_C_COQUAL":
        focus = "Block C — hardest corner chip+robot+world co-qual chain"
    elif active_gap == "BLOCK_D_COMPUTE":
        focus = "Block D — compute path MMIO pose loop · session policy honest"
    elif active_gap == "CHIP_ASSEMBLY_VISUAL_G6":
        focus = "G6 visual — Vella-grade module sheet · chip↔robot↔package · transistors · vault canon"
    elif active_gap == "ENVELOPE_CLOSE":
        focus = "Chip condition envelope A–D closed — outbound/janitor lane only"
    elif active_gap == "ISR_HOT_PATH_US":
        focus = "in-world REPLACE — ISR hot-path trace envelope (control axis)"
    elif active_gap == "POPE_SCRATCHPAD_LAW":
        focus = "in-world REPLACE — Pope scratchpad law trace_sim gate"
    elif active_gap == "REGFILE_DEPTH":
        focus = "in-world REPLACE — regfile depth vs ISR cost (control axis)"
    elif active_gap == "invent_wider_bus_tile":
        focus = "in-world REPLACE — wider bus G1 sweep (sprint 1-4 HIL done)"
    elif active_gap == "invent_hbm_compute_die":
        focus = "in-world REPLACE — HBM carrier MMIO iron (DRAM+cryo HIL done)"
    else:
        focus = "in-world REPLACE — sprint gap iron"

    state: dict[str, Any] = {
        "state_id": "CHIP_FACTORY_DAY_TRIGGER_STATE_v1",
        "locked_date": "2026-07-03",
        "canon": _CANON,
        "active": chip_context or True,
        "matrix_34_34": matrix_ok,
        "engineering_gaps": list(ENGINEERING_GAPS),
        "sprint_order": list(SPRINT_ORDER),
        "sprint_done": done,
        "active_gap": active_gap,
        "focus": focus,
        "secret_sauce": [
            "cross_ledger_motion_hash",
            "combination_cell_7_physics",
            "grid_falsifiers_alive",
            "platonic_ab_slot_gaps",
            "replace_external_with_observable_iron",
        ],
        "tabu": [
            "foundry_nag",
            "pytest_as_iron",
            "outbound_north",
            "invented_bom_gb",
            "matrix_reaudit_without_regression",
        ],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "inject": INJECT if chip_context else "",
    }
    _STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return state


def run_gate(*, prompt: str = "") -> dict[str, Any]:
    return evaluate(prompt=prompt)


if __name__ == "__main__":
    import sys

    p = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "chip factory gap"
    doc = run_gate(prompt=p)
    print(json.dumps({"active_gap": doc["active_gap"], "matrix_34_34": doc["matrix_34_34"]}, indent=2))
