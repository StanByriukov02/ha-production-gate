"""Build dual-physics sub prompts — Eve agent-directory pattern."""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

_SUB_DIRS = {
    "algebra": _REPO / "agents" / "clifford-algebra-phys" / "instructions.md",
    "iron": _REPO / "agents" / "clifford-iron-reliability" / "instructions.md",
}

_PHASE_READS = {
    "T3": [
        "scripts/chip/clifford_motor_lerp_v1.py",
        "results/platform_bpass/chip/CHIP_CLIFFORD_MOTOR_LERP_STUDY_RECEIPT_v1.json",
        "docs/agent_workflow/CLIFFORD_MOTOR_LERP_SCOPE_v1.md",
        "results/platform_bpass/chip/CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1.json",
        "results/platform_bpass/chip/CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1.json",
    ],
    "T4": [
        "mlir/clifford/README.md",
        "mlir/clifford/dialect/CliffordOps.td",
        "results/platform_bpass/chip/CHIP_CLIFFORD_MLIR_UNPARK_T4_RECEIPT_v1.json",
        "scripts/chip/clifford_mlir_legalize_v1.py",
        "scripts/chip/clifford_circt_structural_diff_v1.py",
    ],
}


def build_sub_prompt(mode: str, phase: str, *, extra: str = "") -> str:
    """mode: CLIFFORD_ALGEBRA_PHYS | CLIFFORD_IRON_RELIABILITY"""
    key = "algebra" if "ALGEBRA" in mode else "iron"
    instr = _SUB_DIRS[key].read_text(encoding="utf-8")
    reads = "\n".join(f"- `{p}`" for p in _PHASE_READS.get(phase, []))
    return (
        f"{instr}\n\n"
        f"## Parent dispatch\n"
        f"**TARGET:** {phase}\n"
        f"**MODE:** {mode}\n\n"
        f"### Read now\n{reads}\n\n"
        f"{extra}\n"
        "Return the output marker block exactly as specified in instructions."
    )
