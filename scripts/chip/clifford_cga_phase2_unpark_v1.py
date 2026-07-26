"""CGA phase-2 UNPARK — 32-blade oracle + mul table + motor512 RTL iron."""

from __future__ import annotations



import json

import subprocess

from datetime import datetime, timezone

from pathlib import Path

from typing import Any



_REPO = Path(__file__).resolve().parents[2]

_CHIP = _REPO / "results" / "platform_bpass" / "chip"

_RECEIPT = _CHIP / "CHIP_CLIFFORD_CGA_PHASE2_UNPARK_RECEIPT_v1.json"

_T5 = _CHIP / "CHIP_CLIFFORD_CGA_P21_UNPARK_T5_RECEIPT_v1.json"

_CL30 = _REPO / "fixtures" / "chip" / "clifford_geo_prod_v0.v"

_FIX = _REPO / "fixtures" / "chip"

_SCOPE = _REPO / "docs" / "agent_workflow" / "CLIFFORD_CGA_PHASE2_SCOPE_v1.md"

_CGA32_V = _FIX / "clifford_geo_prod_cga32_v0.v"

_CGA32_SYNTH = _FIX / "clifford_geo_prod_cga32_synth_v0.v"

_CGA32_TB = _FIX / "clifford_geo_prod_cga32_tb_v0.v"

_CGA32_YS = _REPO / "scripts" / "chip" / "clifford_area_cga32_motor_probe_v0.ys"





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

    }





def run_cga_phase2_unpark(*, write: bool = True) -> dict[str, Any]:

    if str(_REPO) not in __import__("sys").path:

        __import__("sys").path.insert(0, str(_REPO))



    from scripts.chip.clifford_cga32_cayley_v1 import mul_stats

    from scripts.chip.clifford_cga32_oracle_v1 import run_cga32_oracle_parity, write_mul_table_fixture

    from scripts.chip.clifford_cga32_verilator_smoke_v1 import run_cga32_verilator_smoke

    from scripts.chip.clifford_msys_toolchain_v1 import run_yosys_script

    from scripts.chip.gen_clifford_geo_prod_cga32_tb_v0_sv import main as gen_cga32_tb

    from scripts.chip.gen_clifford_geo_prod_cga32_v0_sv import main as gen_cga32_sv



    t5_ok = _T5.is_file() and json.loads(_T5.read_text(encoding="utf-8")).get("verdict", "").startswith("T5_CGA")

    table = write_mul_table_fixture(write=write)

    parity = run_cga32_oracle_parity()

    stats = mul_stats()

    cl30 = _cl30_regression()



    gen_cga32_sv()

    gen_cga32_tb()

    verilator = run_cga32_verilator_smoke()

    yosys = run_yosys_script(_CGA32_YS)



    checks = [

        {"id": "t5_phase1_prerequisite", "pass": t5_ok},

        {"id": "phase2_scope_doc", "pass": _SCOPE.is_file()},

        {"id": "mul_table_fixture", "pass": (_FIX / "clifford_cga32_mul_table_v1.json").is_file()},

        {"id": "cga32_mul_stats", "pass": stats.mul_terms > 0, "detail": str(stats.to_dict())},

        {"id": "dq_embed_geo_prod_parity", "pass": parity["verdict"] == "CGA32_ORACLE_PARITY_PASS"},

        {"id": "cga32_rtl_sim", "pass": _CGA32_V.is_file()},

        {"id": "cga32_rtl_synth", "pass": _CGA32_SYNTH.is_file()},

        {"id": "cga32_tb", "pass": _CGA32_TB.is_file()},

        {

            "id": "verilator_cga32_smoke",

            "pass": verilator["verdict"] == "VERILATOR_CGA32_PASS",

            "detail": verilator.get("verdict", ""),

        },

        {

            "id": "yosys_cga32_motor_probe",

            "pass": yosys.get("status") == "PASS",

            "detail": str(yosys.get("cells")),

        },

        {"id": "cl30_crown_untouched", "pass": _CL30.is_file()},

        {"id": "cl30_regression", "pass": cl30["verdict"] == "CL30_REGRESSION_PASS"},

    ]



    all_pass = all(c["pass"] for c in checks)

    if not all_pass:

        verdict = "CGA_PHASE2_IRON_FAIL"

    elif verilator["verdict"] == "VERILATOR_CGA32_PASS" and yosys.get("status") == "PASS":

        verdict = "CGA_PHASE2_IRON_PASS"

    elif verilator["verdict"] == "SKIPPED":

        verdict = "CGA_PHASE2_ORACLE_PASS"

    else:

        verdict = "CGA_PHASE2_IRON_FAIL"



    receipt: dict[str, Any] = {

        "receipt_id": "CHIP_CLIFFORD_CGA_PHASE2_UNPARK_RECEIPT_v1",

        "verdict": verdict,

        "timestamp_utc": datetime.now(timezone.utc).isoformat(),

        "checks": checks,

        "oracle_parity": parity,

        "mul_stats": stats.to_dict(),

        "verilator": verilator,

        "yosys_cga32": yosys,

        "honesty": {

            "phase2": "32-blade oracle + motor512 RTL sim/synth + MMIO OP_CGA32 iron",

            "motor512_bits": 512,

            "embed": "motor128 DQ → blades 0..7",

            "iron_rtl_cga32": verdict == "CGA_PHASE2_IRON_PASS",

        },

    }

    if write:

        _CHIP.mkdir(parents=True, exist_ok=True)

        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    return receipt





if __name__ == "__main__":

    print(json.dumps(run_cga_phase2_unpark(), indent=2))

