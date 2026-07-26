"""CGA P2.1 null-plane metric stub — separate from Cl(3,0) spatial (T5 fork)."""
from __future__ import annotations

from dataclasses import dataclass

# R_{3,0,1}*: e0 null (e0²=0), e1,e2,e3 spatial (+1), e∞ optional PARK in v0 stub
CGA_BLADE_COUNT = 32
SPATIAL_CL30_BLADES = 8


@dataclass(frozen=True)
class CgaMetricV0:
    """Honesty: study stub — not iron RTL yet."""

    label: str = "R_3_0_1_CGA_stub"
    e0_square: int = 0
    e1_square: int = 1
    e_inf_park: bool = True

    def falsifier_cl30_isomorphism(self) -> str:
        return "spatial Cl(3,0) receipts must remain PASS when CGA fork enabled"

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "e0_square": self.e0_square,
            "e1_square": self.e1_square,
            "e_inf_park": self.e_inf_park,
            "blade_count_target": CGA_BLADE_COUNT,
            "spatial_subset_blades": SPATIAL_CL30_BLADES,
        }


def motor_dim_comparison() -> dict:
    return {
        "cl30_motor128": {"blades": 8, "payload_bits": 128},
        "cga_motor_stub": {"blades": 32, "payload_bits": 512, "status": "FORK_ONLY"},
        "se3_without_matrix_seam": "target — not measured in this stub",
    }
