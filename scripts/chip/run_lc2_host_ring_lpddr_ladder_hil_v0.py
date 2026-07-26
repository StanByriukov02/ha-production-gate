"""LC2 host ring LPDDR ladder iron — invent_lpddr_offchip sprint.

Axis: Data host (N×Tier-J ring → host SoC). NOT DRAM txn log · NOT bus-width sweep.
DELETE falsifier: 192 MB/s MCU floor = twin fidelity.
"""
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
_IRON_RECEIPT = _CHIP / "CHIP_LPDDR_HOST_RING_IRON_RECEIPT_v1.json"

_RTL = ("lc2_host_ring_lpddr_ladder_tb_v0.v",)
_PASS = "TB_PASS"


def _ledger_params() -> dict[str, int]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))
    from dogfood_platform.chip_robot_aggregate_memory_pressure_v1 import derive_aggregate_memory_pressure
    from dogfood_platform.chip_robot_body_memory_ledger_v1 import derive_body_memory_ledger

    ledger = derive_body_memory_ledger()
    pressure = derive_aggregate_memory_pressure()
    ring = ledger["ring_model"]
    tj = ledger["tier_j"]
    return {
        "CLK_HZ": int(tj["f_clock_hz"]),
        "MCU_FLOOR_MBPS": int(pressure["today_mcu_floor_mbps"]),
        "HOST_INGRESS_MBPS": int(round(pressure["host_ingress_mbps"])),
        "LPDDR_REF_MBPS": int(pressure["lpddr_reference_mbps"]),
        "TWIN_MBPS": int(pressure["moon_twin_mbps"]),
        "AGGREGATE_RING_BYTES": int(ring["aggregate_ring_bytes"]),
        "TWIN_CHUNK_BYTES": 65536,
        "PWM_PERIOD_US": int(round(ring["pwm_period_us"])),
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

    defines = [f"-D{k}={v}" for k, v in params.items()]
    with tempfile.TemporaryDirectory(prefix="lpddr_ladder_") as tmp:
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
    return {"backend": "iverilog", "status": status, "top": "lc2_host_ring_lpddr_ladder_tb_v0"}, stdout


def _parse_ladder(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("LPDDR_LADDER "):
            continue
        rung = re.search(r"rung=(\S+)", line)
        mbps = re.search(r"mbps=(\d+)", line)
        axis = re.search(r"axis=(\S+)", line)
        scope = re.search(r"scope=(\S+)", line)
        rows.append(
            {
                "rung": rung.group(1) if rung else None,
                "mbps": int(mbps.group(1)) if mbps else None,
                "axis": axis.group(1) if axis else None,
                "scope": scope.group(1) if scope else None,
            }
        )
    return rows


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("LPDDR_PT "):
            continue
        path = re.search(r"path=(\S+)", line)
        row: dict[str, Any] = {"path": path.group(1) if path else None}
        for key in ("backlog", "mcu_cycles", "lpddr_cycles", "step_visible", "pwm_budget", "falsify_mcu_for_twin"):
            m = re.search(rf"{key}=(\d+)", line)
            if m:
                row[key] = int(m.group(1))
        rows.append(row)
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"LPDDR_SUMMARY body_under_lpddr=(\d+) twin_exceeds_lpddr=(\d+) mcu_not_twin=(\d+) host_step=(\d+) aggregate_ring_b=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "body_under_lpddr": int(m.group(1)) == 1,
        "twin_exceeds_lpddr": int(m.group(2)) == 1,
        "mcu_not_twin": int(m.group(3)) == 1,
        "host_step_visible": int(m.group(4)) == 1,
        "aggregate_ring_bytes": int(m.group(5)),
    }


def run_lc2_host_ring_lpddr_ladder_hil(*, write: bool = True) -> dict[str, Any]:
    params = _ledger_params()
    iron, stdout = _run_iverilog_full(params)
    payload: dict[str, Any] = {
        "iron_id": "CHIP_LPDDR_HOST_RING_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "params": params,
        "ladder": _parse_ladder(stdout),
        "points": _parse_pts(stdout),
        "summary": _parse_summary(stdout),
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "LPDDR PHY SI package signoff → host ring MMIO ladder iron (earth vs host tier step)",
        "axis": "data_host",
        "delete_falsifier": "192 MB/s MCU joint floor = twin fidelity",
        "verdict": "LPDDR_HOST_RING_IRON_PASS" if iron.get("status") == "PASS" and _parse_summary(stdout) else "LPDDR_HOST_RING_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    doc = run_lc2_host_ring_lpddr_ladder_hil()
    print(json.dumps({"verdict": doc["verdict"], "ladder": doc.get("ladder"), "summary": doc.get("summary")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "LPDDR_HOST_RING_IRON_PASS" else 1)
