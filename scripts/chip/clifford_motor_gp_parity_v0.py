"""Motor GP parity — even×even vs full GP oracle (T2)."""
from __future__ import annotations

from scripts.chip.clifford_cayley_v0 import EVEN_MOTOR_INDICES
from scripts.chip.clifford_pga8_oracle_v0 import (
    BLADE_NAMES,
    bf16_to_f32,
    f32_to_bf16,
    geo_prod_coeffs,
    motor_from_blades,
    motor_hex,
)


def _is_even_motor(coeffs: list[int]) -> bool:
    for idx in (1, 2, 3, 7):
        if coeffs[idx]:
            return False
    return True


def geo_prod_motor_coeffs(a: list[int], b: list[int]) -> list[int]:
    """Even×even rotor compose — algebraically closed slice."""
    full = geo_prod_coeffs(a, b)
    out = [0] * 8
    for k in EVEN_MOTOR_INDICES:
        out[k] = full[k]
    return out


def geo_prod_motor_hex(rs1: list[int], rs2: list[int]) -> str:
    return motor_hex(geo_prod_motor_coeffs(rs1, rs2))


def count_motor_rtl_mul_terms(text: str) -> int:
    import re

    return len(re.findall(r"blade_real_\d+\([^)]+\)\s*\*\s*blade_real_\d+\([^)]+\)", text))


def parity_cases() -> list[dict]:
    import math

    cases: list[dict] = []

    def add(cid: str, a: list[int], b: list[int], *, expect_motor_eq_full: bool) -> None:
        full = geo_prod_coeffs(a, b)
        motor = geo_prod_motor_coeffs(a, b)
        cases.append(
            {
                "id": cid,
                "a_hex": motor_hex(a),
                "b_hex": motor_hex(b),
                "full_hex": motor_hex(full),
                "motor_hex": motor_hex(motor),
                "expect_motor_eq_full": expect_motor_eq_full,
                "motor_eq_full": motor == full,
            }
        )

    one = motor_from_blades(s=1.0)
    rot_z = motor_from_blades(s=math.cos(0.2), e12=math.sin(0.2))
    rot_x = motor_from_blades(s=math.cos(0.15), e23=math.sin(0.15))

    add("identity_left", one, rot_z, expect_motor_eq_full=True)
    add("identity_right", rot_z, one, expect_motor_eq_full=True)
    add("compose_zx", rot_z, rot_x, expect_motor_eq_full=True)
    add("chain_assoc", geo_prod_coeffs(geo_prod_coeffs(rot_z, rot_x), one), one, expect_motor_eq_full=True)

    e1 = motor_from_blades(e1=1.0)
    add("odd_operand_falsifier", e1, rot_z, expect_motor_eq_full=False)

    contaminated = list(rot_z)
    contaminated[1] = f32_to_bf16(1e-4)
    add("odd_contamination", contaminated, rot_x, expect_motor_eq_full=False)

    return cases


def run_motor_parity_gate() -> dict:
    cases = parity_cases()
    ok = all(c["motor_eq_full"] == c["expect_motor_eq_full"] for c in cases)
    return {"verdict": "PASS" if ok else "FAIL", "cases": cases, "n": len(cases)}
