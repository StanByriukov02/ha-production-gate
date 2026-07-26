"""T2.11 — sandwich gp2 blade split @ EX3 + STA delta vs T2.10."""
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
_RECEIPT = _CHIP / "CHIP_CLIFFORD_STA_T2_SANDWICH_EX3_BLADES_RECEIPT_v1.json"
_PRIOR = _CHIP / "CHIP_CLIFFORD_STA_T2_SANDWICH_EX2_STAGED_RECEIPT_v1.json"
_THERM = _CHIP / "CHIP_CLIFFORD_STA_T2_THERMOMETER_RECEIPT_v1.json"
_SCOPE = _REPO / "docs/agent_workflow/CLIFFORD_STA_SANDWICH_BINDING_PATH_v1.md"
_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"
_WNS_IMPROVE_FLOOR_NS = 10.0

_DUAL_RTL = (
    "clifford_geo_prod_v0.v",
    "clifford_geo_prod_low_blades_v0.v",
    "clifford_geo_prod_high_blades_v0.v",
    "clifford_f32_synth_v0.v",
    "clifford_geo_prod_synth_v0.v",
    "clifford_geo_prod_synth_low_blades_v0.v",
    "clifford_geo_prod_synth_high_blades_v0.v",
    "clifford_reverse_v0.v",
    "clifford_reverse_synth_v0.v",
    "clifford_norm_v0.v",
    "clifford_norm_synth_v0.v",
    "clifford_sandwich_ex_pipe_v0.v",
    "clifford_sandwich_ex_pipe_dual_tb_v0.v",
)


def _mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{_MSYS_BIN};{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(_REPO)
    return env


def _sim_dual_tb() -> dict[str, Any]:
    iverilog = shutil.which("iverilog") or (_MSYS_BIN / "iverilog.exe")
    vvp = shutil.which("vvp") or (_MSYS_BIN / "vvp.exe")
    if not Path(str(iverilog)).is_file() or not Path(str(vvp)).is_file():
        return {"verdict": "SKIPPED", "reason": "iverilog missing"}
    with tempfile.TemporaryDirectory(prefix="clifford_sandwich_ex3_vlt_") as tmp:
        out_vvp = Path(tmp) / "sim.vvp"
        try:
            subprocess.run(
                [str(iverilog), "-g2012", "-o", str(out_vvp), "-I", str(_FIX), *[_FIX / s for s in _DUAL_RTL]],
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
            ok = "TB_PASS sandwich_ex_pipe_dual_physics cases=9" in out
            return {
                "verdict": "IVERILOG_SANDWICH_EX3_BLADES_PASS" if ok else "IVERILOG_SANDWICH_EX3_BLADES_FAIL",
                "stdout_tail": out[-1200:],
            }
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            return {"verdict": "IVERILOG_SANDWICH_EX3_BLADES_FAIL", "reason": str(exc)[-400:]}


def run_sta_t2_sandwich_ex3_blades(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    from scripts.chip.run_clifford_alu_opensta_liberty_full_v0 import run_clifford_alu_opensta_liberty_full

    prior_ok = _PRIOR.is_file() and json.loads(_PRIOR.read_text(encoding="utf-8")).get("verdict") == "STA_T2_SANDWICH_EX2_STAGED_PASS"
    sw = (_FIX / "clifford_sandwich_ex_pipe_v0.v").read_text(encoding="utf-8")
    ex3_blades = (
        "lat_ara_low" in sw
        and "lat_ara_high" in sw
        and "u_ara_low_synth" in sw
        and "ara_motor_mux" in sw
    )
    sim = _sim_dual_tb()
    prior = json.loads(_PRIOR.read_text(encoding="utf-8")).get("timing", {}).get("ex2_staged_wns_ns") if _PRIOR.is_file() else None
    therm = json.loads(_THERM.read_text(encoding="utf-8")).get("timing", {}).get("wns_ns") if _THERM.is_file() else None
    lib = run_clifford_alu_opensta_liberty_full()
    sta = lib.get("opensta_liberty", {})
    wns = sta.get("wns_ns")
    delta_prior = round((wns - prior), 3) if wns is not None and prior is not None else None
    delta_therm = round((wns - therm), 3) if wns is not None and therm is not None else None
    tail = (sta.get("stdout_tail", "") or "") + (sta.get("reason", "") or "")
    binding = "sandwich_norm_comb" if "u_sandwich_pipe" in tail else "unknown"

    checks = [
        {"id": "t2_10_prerequisite", "pass": prior_ok},
        {"id": "binding_path_doc", "pass": _SCOPE.is_file()},
        {"id": "sandwich_gp2_blades_rtl", "pass": ex3_blades},
        {"id": "iverilog_sandwich_dual_9case", "pass": sim.get("verdict") == "IVERILOG_SANDWICH_EX3_BLADES_PASS"},
        {"id": "opensta_liberty_ran", "pass": sta.get("opensta_run") and sta.get("checks_ok")},
        {
            "id": "wns_improved_vs_t2_10",
            "pass": delta_prior is not None and delta_prior >= _WNS_IMPROVE_FLOOR_NS,
            "detail": f"prior={prior} ex3={wns} delta={delta_prior}",
        },
        {"id": "timing_not_closed", "pass": wns is not None and wns < 0},
    ]

    timing_closed = wns is not None and wns >= 0
    verdict = "STA_T2_SANDWICH_EX3_BLADES_PASS" if all(c["pass"] for c in checks) else "STA_T2_SANDWICH_EX3_BLADES_FAIL"
    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_STA_T2_SANDWICH_EX3_BLADES_RECEIPT_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "timing": {
            "t2_10_prior_wns_ns": prior,
            "ex3_blades_wns_ns": wns,
            "wns_delta_vs_t2_10_ns": delta_prior,
            "wns_delta_vs_thermometer_ns": delta_therm,
            "binding_path": binding,
            "timing_closure": timing_closed,
        },
        "sim": sim,
        "honesty": {
            "promote_not_signoff": not timing_closed,
            "staged_split": "gp2 low/high blades @ ex3 — REVERTED (STA regression)",
            "t2_11_falsifier": "ara_motor_mux deepens norm comb vs lat_ara register path",
            "rtl_reverted_to": "T2.10 gp1 blades + full gp2 @ ex3_eval",
            "dual_physics_phase": "T2_CLOSURE",
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(run_sta_t2_sandwich_ex3_blades(), indent=2))
