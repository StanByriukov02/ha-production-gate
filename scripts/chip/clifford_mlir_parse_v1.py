"""Parse Clifford MLIR stub text — constants + clifford.gp + check_hex."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_HEX_RE = re.compile(r'hex\("([0-9a-fA-F]+)"\)')
_GP_RE = re.compile(
    r"%(\w+)\s*=\s*clifford\.gp\s+%(\w+)\s*,\s*%(\w+)\s*:\s*!clifford\.motor128"
)
_CONST_RE = re.compile(
    r"%(\w+)\s*=\s*clifford\.constant\s+hex\(\"([0-9a-fA-F]+)\"\)\s*:\s*!clifford\.motor128"
)
_CHECK_RE = re.compile(
    r"clifford\.check_hex\s+%(\w+)\s*,\s*hex\(\"([0-9a-fA-F]+)\"\)\s*:\s*!clifford\.motor128"
)


@dataclass(frozen=True)
class GpCase:
    case_id: str
    rs1_hex: str
    rs2_hex: str
    expected_rd_hex: str
    source: str


def parse_mlir_gp_cases(text: str, *, source: str = "") -> list[GpCase]:
    """Extract gp+check_hex triples from stub MLIR (per func.func scope)."""
    cases: list[GpCase] = []
    blocks = re.split(r"func\.func\s+@\w+\s*\(\)\s*\{", text)
    for block in blocks[1:]:
        body = block.split("return", 1)[0]
        consts = {m.group(1): m.group(2).lower() for m in _CONST_RE.finditer(body)}
        for i, chk in enumerate(_CHECK_RE.finditer(body)):
            result_var = chk.group(1)
            expected = chk.group(2).lower()
            gp_match = None
            for gm in _GP_RE.finditer(body):
                if gm.group(1) == result_var:
                    gp_match = gm
                    break
            if gp_match is None:
                continue
            a_var, b_var = gp_match.group(2), gp_match.group(3)
            rs1 = consts.get(a_var, "")
            rs2 = consts.get(b_var, "")
            if not rs1 or not rs2:
                continue
            cases.append(
                GpCase(
                    case_id=f"mlir_{len(cases)}",
                    rs1_hex=rs1,
                    rs2_hex=rs2,
                    expected_rd_hex=expected,
                    source=source,
                )
            )
    return cases


def load_mlir_cases(path: Path) -> list[GpCase]:
    return parse_mlir_gp_cases(path.read_text(encoding="utf-8"), source=str(path))
