"""Clifford + robot gate registry — single manifest for parallel / CI runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_REGISTRY = _REPO / "fixtures" / "chip" / "clifford_gate_registry_v0.json"
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_GATE_REGISTRY_RECEIPT_v1.json"

_GATES: list[dict[str, Any]] = [
    {"id": "python_glue", "tier": "light", "entry": "scripts/chip/clifford_python_glue_gate_v0.py", "receipt": "results/platform_bpass/chip/CLIFFORD_PYTHON_GLUE_STATE_v1.json"},
    {"id": "crown_stack", "tier": "light", "entry": "scripts/chip/clifford_crown_stack_gate_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_CROWN_STACK_GATE_RECEIPT_v1.json"},
    {"id": "production_crown", "tier": "light", "entry": "scripts/chip/clifford_production_crown_gate_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_PRODUCTION_CROWN_GATE_RECEIPT_v1.json"},
    {"id": "crown_motor_bind", "tier": "light", "entry": "scripts/chip/clifford_crown_motor_bind_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_CROWN_MOTOR_BIND_RECEIPT_v1.json"},
    {"id": "crown_moon_bind", "tier": "light", "entry": "scripts/chip/clifford_crown_moon_bind_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_CROWN_MOON_BIND_RECEIPT_v1.json"},
    {"id": "reverse_mmio_parity", "tier": "light", "entry": "scripts/chip/clifford_reverse_mmio_parity_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_REVERSE_MMIO_PARITY_RECEIPT_v1.json"},
    {"id": "mmio_opcode_inventory", "tier": "light", "entry": "scripts/chip/clifford_mmio_opcode_inventory_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_MMIO_OPCODE_INVENTORY_RECEIPT_v1.json"},
    {"id": "expedition_degraded", "tier": "light", "entry": "scripts/chip/clifford_expedition_degraded_gate_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_EXPEDITION_DEGRADED_GATE_RECEIPT_v1.json"},
    {"id": "runtime_gate", "tier": "light", "entry": "dogfood_platform/dogfood_twin_clifford_runtime_gate_v1.py", "receipt": "fixtures/twin/clifford_runtime_gate_v1.json"},
    {"id": "m3_signoff", "tier": "heavy", "entry": "scripts/chip/run_h1_m3_local_v0.ps1", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_H1_MAPPED_ALU_PARITY_RECEIPT_v1.json", "mutex": "clifford_sim_heavy_lock_v0.json"},
    {"id": "world_expedition", "tier": "heavy", "entry": "scripts/chip/run_clifford_world_expedition_batch_v0.ps1", "receipt": "results/platform_bpass/moon/ROBOT_IFT2_WORLD_EXPEDITION_BATCH_RECEIPT_v1.json"},
    {"id": "sim_slot_runner", "tier": "robot", "entry": "dogfood_platform/robot_ift2_sim_slot_runner_v1.py", "receipt": "results/platform_bpass/moon/ROBOT_IFT2_SIM_SLOT_RUNNER_RECEIPT_v1.json"},
    {"id": "fpga_yosys_smoke", "tier": "carrier", "entry": "scripts/chip/clifford_fpga_yosys_smoke_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_FPGA_YOSYS_ELAB_RECEIPT_v1.json"},
    {"id": "scale_tier_v2", "tier": "scale", "entry": "scripts/chip/run_clifford_scale_tier_v0.ps1", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_SCALE_TIER_V2_RECEIPT_v1.json"},
    {"id": "chip_carrier_tier_v4", "tier": "carrier", "entry": "scripts/chip/run_clifford_post_crown_batch_v0.ps1", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_CHIP_CARRIER_TIER_V4_RECEIPT_v1.json"},
    {"id": "carrier_mission_clock", "tier": "carrier", "entry": "scripts/chip/clifford_carrier_mission_clock_study_v0.py", "receipt": "results/platform_bpass/chip/CHIP_CLIFFORD_CARRIER_MISSION_CLOCK_STUDY_RECEIPT_v1.json"},
]


def build_gate_registry(*, write: bool = True) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "registry_id": "clifford_gate_registry_v0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "law": {"clifford_alu_is_crown": True, "chip_is_carrier": True},
        "orchestrator": "scripts/chip/run_clifford_parallel_gates_v0.ps1",
        "gates": _GATES,
        "policy": {
            "heavy_mutex": "results/platform_bpass/chip/clifford_sim_heavy_lock_v0.json",
            "tabu_parallel_iverilog": True,
        },
    }
    if write:
        _REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        _REGISTRY.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(
            json.dumps(
                {
                    "receipt_id": "CHIP_CLIFFORD_GATE_REGISTRY_RECEIPT_v1",
                    "verdict": "GATE_REGISTRY_PASS",
                    "gate_count": len(_GATES),
                    "registry": str(_REGISTRY.relative_to(_REPO)).replace("\\", "/"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return doc


if __name__ == "__main__":
    print(json.dumps(build_gate_registry(), indent=2))
