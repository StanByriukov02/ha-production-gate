"""T2.8 — sandwich EX3 staged promote (gp2 @ ex3_eval · norm @ ex3_latch) + STA delta."""
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
_RECEIPT = _CHIP / "CHIP_CLIFFORD_STA_T2_SANDWICH_STAGED_PROMOTE_RECEIPT_v1.json"
_THERM = _CHIP / "CHIP_CLIFFORD_STA_T2_THERMOMETER_RECEIPT_v1.json"
_SCOPE = _REPO / "docs/agent_workflow/CLIFFORD_STA_SANDWICH_BINDING_PATH_v1.md"
_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"
_WNS_IMPROVE_FLOOR_NS = 25.0

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
    with tempfile.TemporaryDirectory(prefix="clifford_sandwich_staged_vlt_") as tmp:
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
                "verdict": "IVERILOG_SANDWICH_STAGED_PASS" if ok else "IVERILOG_SANDWICH_STAGED_FAIL",
                "stdout_tail": out[-1200:],
            }
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            return {"verdict": "IVERILOG_SANDWICH_STAGED_FAIL", "reason": str(exc)[-400:]}


def _baseline_wns() -> float | None:
    if not _THERM.is_file():
        return None
    return json.loads(_THERM.read_text(encoding="utf-8")).get("timing", {}).get("wns_ns")


def run_sta_t2_sandwich_closure_promote(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    from scripts.chip.run_clifford_alu_opensta_liberty_full_v0 import run_clifford_alu_opensta_liberty_full

    therm_ok = _THERM.is_file() and json.loads(_THERM.read_text(encoding="utf-8")).get("verdict") == "STA_T2_THERMOMETER_PASS"
    sw = (_FIX / "clifford_sandwich_ex_pipe_v0.v").read_text(encoding="utf-8")
    staged_ok = "lat_ara" in sw and "lat_rev" in sw and "if (ex3_eval)" in sw
    sim = _sim_dual_tb()
    baseline = _baseline_wns()
    lib = run_clifford_alu_opensta_liberty_full()
    sta = lib.get("opensta_liberty", {})
    wns = sta.get("wns_ns")
    delta = round((wns - baseline), 3) if wns is not None and baseline is not None else None
    tail = (sta.get("stdout_tail", "") or "") + (sta.get("reason", "") or "")
    binding = "sandwich_norm_comb" if "u_sandwich_pipe" in tail else "unknown"

    checks = [
        {"id": "t2_thermometer_prerequisite", "pass": therm_ok},
        {"id": "binding_path_doc", "pass": _SCOPE.is_file()},
        {"id": "sandwich_staged_rtl", "pass": staged_ok},
        {"id": "alu_top_ex3_eval_wired", "pass": ".ex3_eval(ex3_eval)" in (_FIX / "clifford_alu_top_v0.v").read_text(encoding="utf-8")},
        {"id": "iverilog_sandwich_dual_9case", "pass": sim.get("verdict") == "IVERILOG_SANDWICH_STAGED_PASS"},
        {"id": "opensta_liberty_ran", "pass": sta.get("opensta_run") and sta.get("checks_ok")},
        {
            "id": "wns_improved_vs_baseline",
            "pass": delta is not None and delta >= _WNS_IMPROVE_FLOOR_NS,
            "detail": f"baseline={baseline} staged={wns} delta={delta}",
        },
        {
            "id": "timing_not_closed",
            "pass": wns is not None and wns < 0,
            "detail": "negative WNS expected — promote ≠ signoff",
        },
    ]

    timing_closed = wns is not None and wns >= 0
    verdict = (
        "STA_T2_SANDWICH_STAGED_PROMOTE_PASS"
        if all(c["pass"] for c in checks)
        else "STA_T2_SANDWICH_STAGED_PROMOTE_FAIL"
    )
    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_STA_T2_SANDWICH_STAGED_PROMOTE_RECEIPT_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "timing": {
            "baseline_wns_ns": baseline,
            "staged_wns_ns": wns,
            "wns_delta_ns": delta,
            "binding_path": binding,
            "timing_closure": timing_closed,
        },
        "sim": sim,
        "liberty_full_verdict": lib.get("verdict"),
        "honesty": {
            "promote_not_signoff": not timing_closed,
            "staged_split": "gp2 @ ex3_eval · norm @ ex3_latch",
            "overlap_untouched": True,
            "dual_physics_phase": "T2_CLOSURE",
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(run_sta_t2_sandwich_closure_promote(), indent=2))
