"""H1 — clifford_alu_tb_v0 9-case · gp_synth_en=0 · retire_pipe/rd two-phase."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FIX = _REPO / "fixtures" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_ALU_TB_HYGIENE_RECEIPT_v1.json"
_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"

_ALU_RTL = (
    "clifford_phi_fsm_v0.v",
    "clifford_geo_prod_v0.v",
    "clifford_geo_prod_low_blades_v0.v",
    "clifford_geo_prod_low_lo_blades_v0.v",
    "clifford_geo_prod_low_hi_blades_v0.v",
    "clifford_geo_prod_high_blades_v0.v",
    "clifford_geo_prod_high_lo_blades_v0.v",
    "clifford_geo_prod_high_hi_blades_v0.v",
    "clifford_geo_prod_synth_v0.v",
    "clifford_geo_prod_synth_low_blades_v0.v",
    "clifford_geo_prod_synth_low_lo_blades_v0.v",
    "clifford_geo_prod_synth_low_hi_blades_v0.v",
    "clifford_geo_prod_synth_high_blades_v0.v",
    "clifford_geo_prod_synth_high_lo_blades_v0.v",
    "clifford_geo_prod_synth_high_hi_blades_v0.v",
    "clifford_reverse_v0.v",
    "clifford_reverse_synth_v0.v",
    "clifford_norm_v0.v",
    "clifford_f32_synth_v0.v",
    "clifford_f32_nr_v0.v",
    "clifford_norm_synth_acc_low_v0.v",
    "clifford_norm_synth_acc_tail_v0.v",
    "clifford_norm_synth_scale_v0.v",
    "clifford_geo_prod_ex_pipe_v0.v",
    "clifford_sandwich_ex_pipe_v0.v",
    "clifford_norm_ex_pipe_v0.v",
    "clifford_geo_prod_cga_v0.v",
    "clifford_geo_prod_cga_synth_v0.v",
    "clifford_geo_prod_cga_ex_pipe_v0.v",
    "clifford_alu_top_v0.v",
    "clifford_alu_tb_v0.v",
)


def _mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{_MSYS_BIN};{env.get('PATH', '')}"
    return env


def run_alu_tb_hygiene(*, write: bool = True) -> dict[str, Any]:
    gen = _REPO / "scripts" / "chip" / "gen_clifford_alu_tb_v0_sv.py"
    subprocess.run([__import__("sys").executable, str(gen)], check=True, cwd=str(_REPO))

    tb = (_FIX / "clifford_alu_tb_v0.v").read_text(encoding="utf-8")
    top = (_FIX / "clifford_alu_top_v0.v").read_text(encoding="utf-8")
    rtl_ok = (
        "gp_synth_en" in tb
        and "gp_synth_en = 1'b0" in tb
        and "while (!saw_wb)" in tb
        and "retire_pipe_q" in top
        and "retire_rd_q" in top
        and "wire retire_capture = retire_pipe_q" in top
    )

    iverilog = shutil.which("iverilog") or (_MSYS_BIN / "iverilog.exe")
    vvp = shutil.which("vvp") or (_MSYS_BIN / "vvp.exe")
    sim: dict[str, Any] = {"verdict": "SKIPPED", "reason": "iverilog missing"}
    if Path(str(iverilog)).is_file() and Path(str(vvp)).is_file():
        with tempfile.TemporaryDirectory(prefix="clifford_alu_tb_h1_") as tmp:
            out_vvp = Path(tmp) / "alu_tb.vvp"
            try:
                subprocess.run(
                    [str(iverilog), "-g2012", "-o", str(out_vvp), "-I", str(_FIX), *[_FIX / s for s in _ALU_RTL]],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    env=_mingw_env(),
                )
                run = subprocess.run(
                    [str(vvp), str(out_vvp)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    env=_mingw_env(),
                )
                out = (run.stdout or "") + (run.stderr or "")
                ok = "TB_PASS cases=9" in out
                sim = {
                    "verdict": "IVERILOG_ALU_TB_PASS" if ok else "IVERILOG_ALU_TB_FAIL",
                    "stdout_tail": out[-2000:],
                }
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                sim = {"verdict": "IVERILOG_ALU_TB_FAIL", "reason": str(exc)[-500:]}

    checks = [
        {"id": "alu_tb_gp_synth_en_tied", "pass": "gp_synth_en = 1'b0" in tb},
        {"id": "alu_tb_wait_wb_done", "pass": "while (!saw_wb)" in tb},
        {"id": "alu_top_retire_two_phase", "pass": rtl_ok},
        {"id": "iverilog_alu_tb_9case", "pass": sim.get("verdict") == "IVERILOG_ALU_TB_PASS"},
    ]
    promote = all(c["pass"] for c in checks)
    verdict = "ALU_TB_HYGIENE_PASS" if promote else "ALU_TB_HYGIENE_FAIL"

    receipt: dict[str, Any] = {
        "schema": "CHIP_CLIFFORD_ALU_TB_HYGIENE_RECEIPT_v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "hop": "H1",
        "checks": checks,
        "sim": sim,
    }
    if write:
        _RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(run_alu_tb_hygiene(), indent=2))
