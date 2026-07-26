"""ISR hot-path envelope iron — ISR_HOT_PATH_US sprint · trace_sim spread."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FIX = _REPO / "fixtures" / "chip"
_ENVELOPE = _CHIP / "CHIP_ISR_MULTI_PATH_ENVELOPE_DERIVED_BIND_v1.json"
_IRON_RECEIPT = _CHIP / "CHIP_ISR_HOT_PATH_ENVELOPE_IRON_RECEIPT_v1.json"

_RTL = ("lc2_isr_hot_path_envelope_tb_v0.v",)
_PASS = "TB_PASS"

_PATH_POLICIES = (
    ("sym-path-alternating", "alternating", "ISR_US_ALT"),
    ("sym-path-always-on", "always_on", "ISR_US_ON"),
    ("sym-path-sparse-duty", "sparse_one_third", "ISR_US_SPARSE"),
)

_BASE_ISR_US = 12
_TRANS_SLOPE_US = 25


def _isr_us_from_trace(policy: str) -> int:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from dogfood_platform.trace_sim import TraceConfig, extract_sp_af, simulate_foc_isr_trace

    cfg = TraceConfig(pwm_periods_slice=100_000)
    samples = simulate_foc_isr_trace(cfg, gate_policy=policy)
    metrics = extract_sp_af(samples, cfg=cfg, scale_to_episode=False)
    tpc = float(metrics["transitions_per_cycle"])
    return int(round(_BASE_ISR_US + _TRANS_SLOPE_US * tpc))


def _envelope_params() -> dict[str, int]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from dogfood_platform.chip_robot_body_memory_ledger_v1 import derive_body_memory_ledger

    ledger = derive_body_memory_ledger()
    pwm_budget = int(round(ledger["ring_model"]["pwm_period_us"]))
    isr_vals = {define: _isr_us_from_trace(policy) for _, policy, define in _PATH_POLICIES}
    return {"PWM_BUDGET_US": pwm_budget, **isr_vals}


def _run_iverilog_full(params: dict[str, int]) -> tuple[dict[str, Any], str]:
    iverilog = shutil.which("iverilog") or shutil.which("iverilog.exe")
    vvp = shutil.which("vvp") or shutil.which("vvp.exe")
    msys = Path(r"C:\msys64\mingw64\bin")
    if not iverilog and (msys / "iverilog.exe").is_file():
        iverilog = str(msys / "iverilog.exe")
    if not vvp and (msys / "vvp.exe").is_file():
        vvp = str(msys / "vvp.exe")
    if not iverilog or not vvp:
        return {"backend": "iverilog", "status": "SKIPPED", "reason": "iverilog missing"}, ""

    env = os.environ.copy()
    if msys.is_dir():
        env["PATH"] = f"{msys};{env.get('PATH', '')}"

    defines = [f"-D{k}={v}" for k, v in params.items()]
    with tempfile.TemporaryDirectory(prefix="isr_env_") as tmp:
        out_vvp = Path(tmp) / "sim.vvp"
        subprocess.run(
            [iverilog, "-g2012", *defines, "-o", str(out_vvp), "-I", str(_FIX), *[str(_FIX / r) for r in _RTL]],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        sim = subprocess.run([vvp, str(out_vvp)], check=True, capture_output=True, text=True, timeout=120, env=env)
        stdout = (sim.stdout or "") + (sim.stderr or "")
    status = "PASS" if _PASS in stdout else "FAIL"
    return {"backend": "iverilog", "status": status, "top": "lc2_isr_hot_path_envelope_tb_v0"}, stdout


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("ISR_PT "):
            continue
        pid = re.search(r"path_id=(\S+)", line)
        gp = re.search(r"gate_policy=(\S+)", line)
        us = re.search(r"isr_us=(\d+)", line)
        bp = re.search(r"budget_pass=(\d+)", line)
        rows.append(
            {
                "path_id": pid.group(1) if pid else None,
                "gate_policy": gp.group(1) if gp else None,
                "isr_us": int(us.group(1)) if us else None,
                "budget_pass": int(bp.group(1)) == 1 if bp else None,
            }
        )
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"ISR_SUMMARY spread_us=(\d+) min_us=(\d+) max_us=(\d+) paths=(\d+) trace_sim_derived=(\d+) pwm_budget_us=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "spread_us": int(m.group(1)),
        "min_us": int(m.group(2)),
        "max_us": int(m.group(3)),
        "paths": int(m.group(4)),
        "trace_sim_derived": int(m.group(5)) == 1,
        "pwm_budget_us": int(m.group(6)),
    }


def run_lc2_isr_hot_path_envelope_hil(*, write: bool = True) -> dict[str, Any]:
    params = _envelope_params()
    iron, stdout = _run_iverilog_full(params)
    path_rows = [
        {"path_id": pid, "gate_policy": policy, "isr_us": params[define]}
        for pid, policy, define in _PATH_POLICIES
    ]
    payload: dict[str, Any] = {
        "iron_id": "CHIP_ISR_HOT_PATH_ENVELOPE_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "params": params,
        "path_envelope": path_rows,
        "formula": f"isr_us = {_BASE_ISR_US} + {_TRANS_SLOPE_US} * transitions_per_cycle (trace_sim)",
        "points": _parse_pts(stdout),
        "summary": _parse_summary(stdout),
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "WCET spreadsheet single number → trace_sim path_id µs envelope iron",
        "axis": "control",
        "delete_falsifier": "faster C wish without multi-path ISR trace spread",
        "verdict": "ISR_HOT_PATH_ENVELOPE_IRON_PASS" if iron.get("status") == "PASS" and _parse_summary(stdout) else "ISR_HOT_PATH_ENVELOPE_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    doc = run_lc2_isr_hot_path_envelope_hil()
    print(json.dumps({"verdict": doc["verdict"], "path_envelope": doc.get("path_envelope"), "summary": doc.get("summary")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "ISR_HOT_PATH_ENVELOPE_IRON_PASS" else 1)
