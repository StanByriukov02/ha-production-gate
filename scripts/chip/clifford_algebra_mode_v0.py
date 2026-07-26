"""Clifford algebra mode switch — internal math rail selector (not Cursor stress).

Canon: docs/agent_workflow/CLIFFORD_ALGEBRA_MODE_SWITCH_V1.md
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from scripts.chip.clifford_op_law_v0 import PoseTabuViolation


class AlgebraMode(IntEnum):
    KINEMATIC = 0  # rigid: gp chain only for pose
    REFORM = 1  # sandwich microprogram
    RAW = 2  # expert direct op


class AlgebraIntent(IntEnum):
    RIGID_POSE = 0
    REFORM_SANDWICH = 1
    RAW_OP = 2


@dataclass(frozen=True)
class MacroStep:
    op: str  # V_GEO_PROD | V_SANDWICH | NORM
    rs1_hex: str
    rs2_hex: str
    note: str = ""


class AlgebraModeViolation(RuntimeError):
    pass


def mode_name(mode: AlgebraMode) -> str:
    return mode.name


def validate_op(mode: AlgebraMode, op: str, *, intent: AlgebraIntent | None = None) -> None:
    op_u = op.upper()
    if mode == AlgebraMode.KINEMATIC and op_u in ("V_SANDWICH", "SANDWICH", "001"):
        if intent in (AlgebraIntent.RIGID_POSE, None):
            raise AlgebraModeViolation(
                f"mode={mode_name(mode)}: V_SANDWICH blocked for pose — use GEO_PROD chain"
            )
    if mode == AlgebraMode.KINEMATIC and intent == AlgebraIntent.REFORM_SANDWICH:
        raise AlgebraModeViolation("REFORM sandwich intent incompatible with KINEMATIC mode")


def lower_rigid_pose(rotor_hex: str, point_hex: str, *, reverse_fn) -> list[MacroStep]:
    """Two GEO_PROD macros: gp(gp(R,p), reverse(R)). reverse_fn(rotor_hex)->hex."""
    rev = reverse_fn(rotor_hex)
    return [
        MacroStep("V_GEO_PROD", rotor_hex, point_hex, "R*p"),
        MacroStep("V_GEO_PROD", "__TMP__", rev, "tmp*~R"),
    ]


def lower_intent(
    mode: AlgebraMode,
    intent: AlgebraIntent,
    rs1_hex: str,
    rs2_hex: str,
    *,
    reverse_fn=None,
    raw_op: str = "V_GEO_PROD",
) -> list[MacroStep]:
    if intent == AlgebraIntent.RIGID_POSE:
        if mode != AlgebraMode.KINEMATIC:
            raise AlgebraModeViolation("rigid pose requires KINEMATIC mode")
        if reverse_fn is None:
            raise ValueError("reverse_fn required for pose lowering")
        return lower_rigid_pose(rs1_hex, rs2_hex, reverse_fn=reverse_fn)
    if intent == AlgebraIntent.REFORM_SANDWICH:
        validate_op(mode, "V_SANDWICH", intent=intent)
        if mode not in (AlgebraMode.REFORM, AlgebraMode.RAW):
            raise AlgebraModeViolation("REFORM sandwich requires REFORM or RAW mode")
        return [MacroStep("V_SANDWICH", rs1_hex, rs2_hex, "reform sandwich")]
    if intent == AlgebraIntent.RAW_OP:
        if mode != AlgebraMode.RAW:
            raise AlgebraModeViolation("RAW_OP requires RAW mode")
        return [MacroStep(raw_op, rs1_hex, rs2_hex, "raw direct op")]
    raise AlgebraModeViolation(f"unknown intent {intent}")


def execute_chain(
    steps: list[MacroStep],
    oracle: Any,
) -> str:
    """Run lowered macro chain via oracle glue; returns final rd hex."""
    tmp_hex: str | None = None
    rd_hex = "0" * 32
    for step in steps:
        rs1_hex = step.rs1_hex
        rs2_hex = step.rs2_hex
        if rs1_hex == "__TMP__":
            if not tmp_hex:
                raise RuntimeError("missing tmp for chain step")
            rs1_hex = tmp_hex
        rs1 = oracle.unpack_motor(int(rs1_hex, 16))
        rs2 = oracle.unpack_motor(int(rs2_hex, 16))
        if step.op == "V_GEO_PROD":
            rd_hex = oracle.geo_prod_hex(rs1, rs2)
        elif step.op == "V_SANDWICH":
            rd_hex = oracle.sandwich_hex(rs1, rs2)
        elif step.op == "NORM":
            rd_hex = oracle.norm_hex(rs1)
        else:
            raise AlgebraModeViolation(f"unsupported op {step.op}")
        tmp_hex = rd_hex
    return rd_hex
