"""T2.17 — norm tail split: sqrt/rcp @ ex3_recovery · scale @ retire_capture."""
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
_RECEIPT = _CHIP / "CHIP_CLIFFORD_STA_T2_NORM_TAIL_SPLIT_RECEIPT_v1.json"
_PRIOR = _CHIP / "CHIP_CLIFFORD_STA_T2_ACC7_SPLIT_RECEIPT_v1.json"
_SCOPE = _REPO / "docs/agent_workflow/CLIFFORD_STA_SANDWICH_BINDING_PATH_v1.md"
_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"
_WNS_IMPROVE_FLOOR_NS = 1.5  # scale-only decouple; sqrt/rcp remain @ ex3_recovery

_DUAL_RTL = (
    "clifford_geo_prod_v0.v",
    "clifford_geo_prod_low_blades_v0.v",
    "clifford_geo_prod_high_blades_v0.v",
    "clifford_f32_synth_v0.v",
    "clifford_f32_nr_v0.v",
    "clifford_norm_synth_acc_low_v0.v",
    "clifford_norm_synth_acc_tail_v0.v",
    "clifford_norm_synth_scale_v0.v",
    "clifford_geo_prod_synth_v0.v",
    "clifford_geo_prod_synth_low_blades_v0.v",
    "clifford_geo_prod_synth_high_blades_v0.v",
    "clifford_reverse_v0.v",
    "clifford_reverse_synth_v0.v",
    "clifford_norm_v0.v",
    "clifford_sandwich_ex_pipe_v0.v",
    "clifford_sandwich_ex_pipe_dual_tb_v0.v",
)

_NORM_RTL = (
    "clifford_f32_synth_v0.v",
    "clifford_f32_nr_v0.v",
    "clifford_norm_synth_acc_low_v0.v",
    "clifford_norm_synth_acc_tail_v0.v",
    "clifford_norm_synth_scale_v0.v",
    "clifford_norm_ex_pipe_v0.v",
    "clifford_norm_ex_pipe_tb_v0.v",
)


def _mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{_MSYS_BIN};{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(_REPO)
    return env


def _sim_iverilog(rtl: tuple[str, ...], pass_token: str) -> dict[str, Any]:
    iverilog = shutil.which("iverilog") or (_MSYS_BIN / "iverilog.exe")
    vvp = shutil.which("vvp") or (_MSYS_BIN / "vvp.exe")
    if not Path(str(iverilog)).is_file() or not Path(str(vvp)).is_file():
        return {"verdict": "SKIPPED", "reason": "iverilog missing"}
    with tempfile.TemporaryDirectory(prefix="clifford_t2_norm_tail_vlt_") as tmp:
        out_vvp = Path(tmp) / "sim.vvp"
        try:
            subprocess.run(
                [str(iverilog), "-g2012", "-o", str(out_vvp), "-I", str(_FIX), *[_FIX / s for s in rtl]],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
                env=_mingw_env(),
            )
            sim = subprocess.run(
                [str(vvp), str(out_vvp)],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
                env=_mingw_env(),
            )
            out = (sim.stdout or "") + (sim.stderr or "")
            ok = pass_token in out
            return {
                "verdict": "IVERILOG_PASS" if ok else "IVERILOG_FAIL",
                "stdout_tail": out[-1200:],
            }
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            return {"verdict": "IVERILOG_FAIL", "reason": str(exc)[-400:]}


def run_sta_t2_norm_tail_split(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    from scripts.chip.run_clifford_alu_opensta_liberty_full_v0 import run_clifford_alu_opensta_liberty_full

    prior_ok = _PRIOR.is_file()
    sw = (_FIX / "clifford_sandwich_ex_pipe_v0.v").read_text(encoding="utf-8")
    nm = (_FIX / "clifford_norm_ex_pipe_v0.v").read_text(encoding="utf-8")
    top = (_FIX / "clifford_alu_top_v0.v").read_text(encoding="utf-8")
    tail_rtl = (
        "retire_capture" in sw
        and "if (retire_capture)" in sw
        and "if (ex3_recovery)" in sw
        and "sw_mag" in sw
        and "sw_inv" in sw
        and "retire_capture" in nm
        and "if (wb_eval)" in nm
        and "lat_inv" in nm
        and "retire_capture" in top
    )
    sim_sw = _sim_iverilog(_DUAL_RTL, "TB_PASS sandwich_ex_pipe_dual_physics cases=7")
    sim_nm = _sim_iverilog(_NORM_RTL, "TB_PASS norm_ex_pipe_unit norm_scalar_two")
    prior = json.loads(_PRIOR.read_text(encoding="utf-8")).get("timing", {}).get("wns_ns") if _PRIOR.is_file() else None
    lib = run_clifford_alu_opensta_liberty_full()
    sta = lib.get("opensta_liberty", {})
    wns = sta.get("wns_ns")
    delta_prior = round((wns - prior), 3) if wns is not None and prior is not None else None
    tail = (sta.get("stdout_tail", "") or "") + (sta.get("reason", "") or "")
    binding = (
        "norm_tail_split"
        if ("u_sw_scale" in tail or "sw_inv" in tail or "u_norm_pipe/u_sqrt" in tail)
        else "unknown"
    )

    checks = [
        {"id": "t2_16_prerequisite", "pass": prior_ok},
        {"id": "binding_path_doc", "pass": _SCOPE.is_file()},
        {"id": "norm_tail_split_rtl", "pass": tail_rtl},
        {"id": "iverilog_sandwich_dual_7case", "pass": sim_sw.get("verdict") == "IVERILOG_PASS"},
        {"id": "iverilog_norm_unit", "pass": sim_nm.get("verdict") == "IVERILOG_PASS"},
        {"id": "opensta_liberty_ran", "pass": sta.get("opensta_run") and sta.get("checks_ok")},
        {
            "id": "wns_improved_vs_t2_16",
            "pass": delta_prior is not None and delta_prior >= _WNS_IMPROVE_FLOOR_NS,
            "detail": f"prior={prior} tail_split={wns} delta={delta_prior}",
        },
        {"id": "timing_not_closed", "pass": wns is not None and wns < 0},
    ]
    promote = all(c["pass"] for c in checks if c["id"] != "timing_not_closed")
    verdict = "STA_T2_NORM_TAIL_SPLIT_PASS" if promote else "STA_T2_NORM_TAIL_SPLIT_FAIL"

    receipt: dict[str, Any] = {
        "schema": "CHIP_CLIFFORD_STA_T2_NORM_TAIL_SPLIT_RECEIPT_v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "hop": "T2.17",
        "binding": binding,
        "checks": checks,
        "timing": {
            "wns_ns": wns,
            "prior_t2_16_wns_ns": prior,
            "delta_vs_t2_16_ns": delta_prior,
            "period_ns": 10.0,
        },
        "sim": {"sandwich_dual": sim_sw, "norm_unit": sim_nm},
        "opensta": {k: sta.get(k) for k in ("opensta_run", "checks_ok", "wns_ns")},
    }
    if write:
        _RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(run_sta_t2_norm_tail_split(), indent=2))
