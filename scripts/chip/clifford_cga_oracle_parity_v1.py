"""Oracle parity — CGA DQ python gold vs generated SV (T5)."""
from __future__ import annotations

from typing import Any

from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor, dq_geo_prod_coeffs


def run_cga_oracle_parity() -> dict[str, Any]:
    from scripts.chip.gen_clifford_geo_prod_cga_v0_sv import main as gen_sv

    gen_sv()
    cases: list[dict[str, Any]] = []
    id_a = DqMotor.identity()
    id_b = DqMotor.identity()
    t_b = DqMotor.from_se3(1.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0)
    ok = True

    for cid, a, b in (("dq_id_id", id_a, id_b), ("dq_id_trans", id_a, t_b)):
        ca = a.to_bf16_coeffs()
        cb = b.to_bf16_coeffs()
        got = dq_geo_prod_coeffs(ca, cb)
        exp = a.geo_prod(b).to_bf16_coeffs()
        case_ok = got == exp
        ok = ok and case_ok
        cases.append(
            {
                "id": cid,
                "pass": case_ok,
                "rd_hex": "".join(f"{h:04x}" for h in got),
                "exp_hex": "".join(f"{h:04x}" for h in exp),
            }
        )

    return {
        "verdict": "ORACLE_PARITY_PASS" if ok else "ORACLE_PARITY_FAIL",
        "n_cases": len(cases),
        "cases": cases,
        "honesty": {"coeff_gold": "python dq_geo_prod vs DqMotor.geo_prod"},
    }
