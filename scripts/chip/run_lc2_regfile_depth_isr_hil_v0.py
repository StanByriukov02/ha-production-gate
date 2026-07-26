"""LC2 regfile depth ISR curve iron — REGFILE_DEPTH sprint · control axis."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FIX = _REPO / "fixtures" / "chip"
_HEATMAP = _CHIP / "CHIP_COMBINATION_CELLS_HEATMAP_BIND_v1.json"
_IRON_RECEIPT = _CHIP / "CHIP_REGFILE_DEPTH_ISR_IRON_RECEIPT_v1.json"

_RTL = ("lc2_regfile_depth_isr_curve_tb_v0.v",)
_PASS = "TB_PASS"


def _control_params() -> dict[str, int]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))
    from dogfood_platform.chip_robot_aggregate_memory_pressure_v1 import derive_aggregate_memory_pressure
    from dogfood_platform.chip_robot_body_memory_ledger_v1 import derive_body_memory_ledger

    pressure = derive_aggregate_memory_pressure()
    ledger = derive_body_memory_ledger()
    tj = ledger["tier_j"]
    max_depth = 16
    if _HEATMAP.is_file():
        depths = [
            int(c.get("overrides", {}).get("REGFILE_DEPTH") or 0)
            for c in json.loads(_HEATMAP.read_text(encoding="utf-8")).get("cells", [])
            if c.get("overrides", {}).get("REGFILE_DEPTH")
        ]
        if depths:
            max_depth = max(depths)
    return {
        "CLK_HZ": int(tj["f_clock_hz"]),
        "PWM_BUDGET_US": int(round(tj["isr_budget_us"])),
        "FOC_LIVE_VARS": 16,
        "JOINTS_N": int(pressure["joints_n"]),
        "BASE_ISR_CYCLES": 720,
        "SPILL_CYCLES_PER_VAR": 60,
        "REGCELL_UM2": 85,
        "HEATMAP_CORNER_DEPTH": max_depth,
    }


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

    defines = [f"-D{k}={v}" for k, v in params.items() if not k.startswith("HEATMAP")]
    with tempfile.TemporaryDirectory(prefix="regfile_isr_") as tmp:
        out_vvp = Path(tmp) / "sim.vvp"
        subprocess.run(
            [
                iverilog,
                "-g2012",
                *defines,
                "-o",
                str(out_vvp),
                "-I",
                str(_FIX),
                *[str(_FIX / r) for r in _RTL],
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        sim = subprocess.run(
            [vvp, str(out_vvp)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        stdout = (sim.stdout or "") + (sim.stderr or "")
    status = "PASS" if _PASS in stdout else "FAIL"
    return {"backend": "iverilog", "status": status, "top": "lc2_regfile_depth_isr_curve_tb_v0"}, stdout


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("REG_PT "):
            continue
        row: dict[str, Any] = {}
        for key in (
            "depth",
            "spills",
            "isr_cycles",
            "isr_us",
            "area_um2",
            "budget_pass",
            "per_joint_us",
            "serial_isr_us",
            "pwm_period_us",
            "path",
        ):
            m = re.search(rf"{key}=(\w+)", line)
            if m:
                val = m.group(1)
                row[key] = int(val) if val.isdigit() else val
        rows.append(row)
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"REG_SUMMARY policy_depth=(\d+) depth8_fail_budget=(\d+) depth16_pass=(\d+) serial_mcu_fail=(\d+) area_cost_visible=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "policy_depth": int(m.group(1)),
        "depth8_fail_budget": int(m.group(2)) == 1,
        "depth16_pass": int(m.group(3)) == 1,
        "serial_mcu_fail": int(m.group(4)) == 1,
        "area_cost_visible": int(m.group(5)) == 1,
    }


def run_lc2_regfile_depth_isr_hil(*, write: bool = True) -> dict[str, Any]:
    params = _control_params()
    iron, stdout = _run_iverilog_full(params)
    payload: dict[str, Any] = {
        "iron_id": "CHIP_REGFILE_DEPTH_ISR_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "params": params,
        "points": _parse_pts(stdout),
        "summary": _parse_summary(stdout),
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "uarch spreadsheet regfile pick → ISR µs vs depth curve + policy bind iron",
        "axis": "control",
        "delete_falsifier": "REGFILE_DEPTH without ISR spill cost on FOC hot path",
        "verdict": "REGFILE_DEPTH_ISR_IRON_PASS" if iron.get("status") == "PASS" and _parse_summary(stdout) else "REGFILE_DEPTH_ISR_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    doc = run_lc2_regfile_depth_isr_hil()
    print(json.dumps({"verdict": doc["verdict"], "summary": doc.get("summary"), "points": doc.get("points")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "REGFILE_DEPTH_ISR_IRON_PASS" else 1)
