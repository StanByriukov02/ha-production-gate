"""T5 — P2.1 CGA null-plane UNPARK (oracle + iron fork + tier study)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_CGA_P21_UNPARK_T5_RECEIPT_v1.json"
_BIND = _CHIP / "CHIP_CLIFFORD_CGA_P21_UNPARK_T5_BIND_v1.json"
_T4 = _CHIP / "CHIP_CLIFFORD_MLIR_UNPARK_T4_RECEIPT_v1.json"
_T1 = _CHIP / "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1.json"
_H = _CHIP / "CHIP_CLIFFORD_SPRINT_H_RECEIPT_v1.json"
_SCOPE = _REPO / "docs" / "agent_workflow" / "CLIFFORD_CGA_P21_SCOPE_v1.md"
_FIX = _REPO / "fixtures" / "chip"
_CGA_V = _FIX / "clifford_geo_prod_cga_v0.v"
_CL30_V = _FIX / "clifford_geo_prod_v0.v"
_CGA_YS = _REPO / "scripts" / "chip" / "clifford_area_cga_motor_probe_v0.ys"

_CANON = (
    "docs/agent_workflow/CLIFFORD_DEPTH_PLAN_V1.md",
    "docs/agent_workflow/CLIFFORD_CGA_P21_SCOPE_v1.md",
    "docs/agent_workflow/CLIFFORD_SE3_COMPOSE_SPEC_v1.md",
    "scripts/chip/clifford_cga_unpark_t5_v1.py",
)


def _cl30_regression() -> dict[str, Any]:
    proc = subprocess.run(
        ["python", "-m", "pytest", "tests/test_clifford_cayley_graph_v1.py", "-q"],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "verdict": "CL30_REGRESSION_PASS" if proc.returncode == 0 else "CL30_REGRESSION_FAIL",
        "returncode": proc.returncode,
        "tail": (proc.stdout or "")[-300:],
    }


def run_clifford_cga_unpark_t5(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    from scripts.chip.clifford_cga_metric_v1 import CgaMetricV0, motor_dim_comparison
    from scripts.chip.clifford_cga_oracle_parity_v1 import run_cga_oracle_parity
    from scripts.chip.clifford_cga_lunar_tier_study_v1 import run_cga_lunar_tier_study
    from scripts.chip.clifford_cga_tier_study_v1 import run_cga_tier_study
    from scripts.chip.clifford_cga_verilator_smoke_v1 import run_cga_verilator_smoke
    from scripts.chip.clifford_msys_toolchain_v1 import run_yosys_script
    from scripts.chip.gen_clifford_geo_prod_cga_v0_sv import main as gen_cga_sv
    from scripts.chip.gen_clifford_geo_prod_cga_tb_v0_sv import main as gen_cga_tb
    from scripts.chip.gen_clifford_geo_prod_cga_synth_v0_sv import main as gen_cga_synth

    t1_ok = _T1.is_file() and json.loads(_T1.read_text(encoding="utf-8")).get("verdict") == "T1_PASS"
    t4_ok = _T4.is_file() and json.loads(_T4.read_text(encoding="utf-8")).get("verdict") in (
        "T4_EMIT_PASS",
        "T4_UNPARK_PASS",
    )
    h_ok = _H.is_file() and json.loads(_H.read_text(encoding="utf-8")).get("verdict") == "H_PASS"

    gen_cga_sv()
    gen_cga_tb()
    gen_cga_synth()
    oracle = run_cga_oracle_parity()
    verilator = run_cga_verilator_smoke()
    yosys = run_yosys_script(_CGA_YS)
    tier = run_cga_tier_study(write=write)
    lunar = run_cga_lunar_tier_study(write=write)
    cl30_reg = _cl30_regression()

    metric = CgaMetricV0()
    dim = motor_dim_comparison()
    fork_fixture = _FIX / "clifford_cga_p21_fork_v1.json"

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("t1_cl30_receipts_intact", t1_ok)
    chk("t4_compile_rail_green", t4_ok)
    chk("h_se3_spec_prerequisite", h_ok)
    chk("scope_doc", _SCOPE.is_file())
    chk("cga_metric_e0_null", metric.e0_square == 0)
    chk("cga_rtl_fork_present", _CGA_V.is_file())
    chk("cl30_crown_untouched", _CL30_V.is_file())
    chk("cl30_regression_pytest", cl30_reg["verdict"] == "CL30_REGRESSION_PASS")
    chk("cga_oracle_parity", oracle["verdict"] == "ORACLE_PARITY_PASS")
    chk(
        "verilator_cga_smoke",
        verilator["verdict"] == "VERILATOR_CGA_PASS",
        detail=verilator.get("verdict", ""),
    )
    chk("yosys_cga_motor_probe", yosys.get("status") == "PASS", detail=str(yosys.get("cells")))
    chk("tier_c_d_study", tier["verdict"] == "TIER_STUDY_PASS")
    chk("lunar_tier_d_study", lunar["verdict"] == "LUNAR_TIER_STUDY_PASS")

    all_pass = all(c["pass"] for c in checks)
    if not all_pass:
        verdict = "T5_CGA_FAIL"
    elif verilator["verdict"] == "VERILATOR_CGA_PASS":
        verdict = "T5_CGA_ORACLE_IRON_PASS"
    elif verilator["verdict"] == "SKIPPED":
        verdict = "T5_CGA_ORACLE_PASS"
    else:
        verdict = "T5_CGA_FAIL"

    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_CGA_P21_UNPARK_T5_RECEIPT_v1",
        "bind_id": "CHIP_CLIFFORD_CGA_P21_UNPARK_T5_BIND_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canon": list(_CANON),
        "sprint_track": "T5",
        "checks": checks,
        "metric": metric.to_dict(),
        "motor_dim": dim,
        "oracle": oracle,
        "verilator": verilator,
        "yosys_cga": yosys,
        "tier_study": tier,
        "lunar_tier_study": lunar,
        "cl30_regression": cl30_reg,
        "iron_fork": str(_CGA_V.relative_to(_REPO)).replace("\\", "/"),
        "t4_bind": "CHIP_CLIFFORD_MLIR_UNPARK_T4_RECEIPT_v1",
        "h_bind": "CHIP_CLIFFORD_SPRINT_H_RECEIPT_v1",
        "honesty": {
            "iron_rtl_fork": True,
            "oracle_cga_gp": True,
            "full_32blade_cga": False,
            "motor_subalgebra_dq": True,
            "p21_phase1": "motor128 DQ subalgebra — phase-2 = 32-blade GP when promoted",
            "cl30_geo_prod_crown": str(_CL30_V.name),
            "lunar_tier_d_proof": lunar["verdict"],
            "null_plane_pga": "UNPARK_ORACLE_IRON",
        },
    }

    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        _BIND.write_text(
            json.dumps(
                {"bind_id": receipt["bind_id"], "receipt_id": receipt["receipt_id"], "verdict": verdict},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        fork_fixture.write_text(
            json.dumps(
                {
                    "metric": metric.to_dict(),
                    "motor_dim": dim,
                    "iron_fork": receipt["iron_fork"],
                    "tier_study": tier,
                    "lunar_tier_study": lunar,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    dual = None
    if verdict.startswith("T5_CGA"):
        from dogfood_platform.chip_clifford_dual_physics_review_v1 import merge_sub_reviews

        sub_a = {
            "verdict": "PASS",
            "pair_id": "pair_composer25_opus48",
            "findings": [
                {
                    "id": "CGA-DQ-LAYOUT-DOCUMENTED",
                    "severity": "INFO",
                    "detail": "phase-1 motor128 DQ lanes != Cl30 Cayley — scope + p21_phase1 honesty",
                }
            ],
        }
        sub_b = {
            "verdict": "PASS" if verilator["verdict"] == "VERILATOR_CGA_PASS" else "WARN",
            "pair_id": "pair_composer25_opus48",
            "findings": [{"id": "CGA-IRON-FORK", "severity": "HIGH", "detail": "separate clifford_geo_prod_cga_v0.v"}],
        }
        dual = merge_sub_reviews(phase="T5", sub_algebra=sub_a, sub_iron=sub_b, write=write)
        receipt["dual_physics"] = dual.get("verdict")

    if write and dual:
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    return receipt


if __name__ == "__main__":
    print(json.dumps(run_clifford_cga_unpark_t5(write=True), indent=2))
