"""Pope scratchpad law iron — POPE_SCRATCHPAD_LAW sprint · trace_sim duty bands."""
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
_HAL = _REPO / "fixtures" / "chip" / "lc2_hal_memory.h"
_IRON_RECEIPT = _CHIP / "CHIP_POPE_SCRATCHPAD_LAW_IRON_RECEIPT_v1.json"

_RTL = ("lc2_pope_scratchpad_law_gate_v0.v", "lc2_pope_scratchpad_law_tb_v0.v")
_PASS = "TB_PASS"

_POLICIES = (
    ("alternating", "DUTY_ALT_X100"),
    ("always_on", "DUTY_ON_X100"),
    ("sparse_one_third", "DUTY_SPARSE_X100"),
)


def _parse_hal_bytes() -> tuple[int, int]:
    text = _HAL.read_text(encoding="utf-8")
    foc = int(re.search(r"LC2_FOC_SCRATCHPAD_BYTES\s+(\d+)u", text).group(1))
    crown = int(re.search(r"LC2_CROWN_STAGING_BYTES\s+(\d+)u", text).group(1))
    return foc, crown


def _trace_sim_duties() -> dict[str, int]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from dogfood_platform.trace_sim import TraceConfig, extract_sp_af, simulate_foc_isr_trace

    cfg = TraceConfig(pwm_periods_slice=100_000)
    out: dict[str, int] = {}
    for policy, define in _POLICIES:
        samples = simulate_foc_isr_trace(cfg, gate_policy=policy)
        metrics = extract_sp_af(samples, cfg=cfg, scale_to_episode=False)
        out[define] = int(round(float(metrics["duty_on"]) * 100))
    return out


def _law_params() -> dict[str, int]:
    foc_b, crown_b = _parse_hal_bytes()
    duties = _trace_sim_duties()
    return {
        "LAW_TOP_BYTES": foc_b + crown_b,
        "TILE_BYTES": 8192,
        "MAP_BASE_BYTES": 512,
        "MAP_SPAN_BYTES": 4096,
        **duties,
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
    with tempfile.TemporaryDirectory(prefix="pope_law_") as tmp:
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
    return {"backend": "iverilog", "status": status, "top": "lc2_pope_scratchpad_law_tb_v0"}, stdout


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("POPE_PT "):
            continue
        band = re.search(r"band=(\S+)", line)
        duty = re.search(r"duty_x100=(\d+)", line)
        path = re.search(r"path=(\S+)", line)
        gp = re.search(r"gate_pass=(\d+)", line)
        viol = re.search(r"violation=(\d+)", line)
        rows.append(
            {
                "band": band.group(1) if band else None,
                "duty_x100": int(duty.group(1)) if duty else None,
                "path": path.group(1) if path else None,
                "gate_pass": int(gp.group(1)) == 1 if gp else None,
                "violation": int(viol.group(1)) == 1 if viol else None,
            }
        )
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"POPE_SUMMARY law_top_b=(\d+) tile_b=(\d+) joint_l1_kb=(\d+) map_violate_loud=(\d+) trace_sim_bands=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "law_top_bytes": int(m.group(1)),
        "tile_bytes": int(m.group(2)),
        "joint_l1_kb": int(m.group(3)),
        "map_violate_loud": int(m.group(4)) == 1,
        "trace_sim_bands": int(m.group(5)),
    }


def run_lc2_pope_scratchpad_law_hil(*, write: bool = True) -> dict[str, Any]:
    params = _law_params()
    iron, stdout = _run_iverilog_full(params)
    trace_bands = [
        {"policy": p, "duty_x100": params[d]}
        for p, d in _POLICIES
    ]
    payload: dict[str, Any] = {
        "iron_id": "CHIP_POPE_SCRATCHPAD_LAW_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "params": params,
        "trace_sim_bands": trace_bands,
        "points": _parse_pts(stdout),
        "summary": _parse_summary(stdout),
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "firmware style guide → scratchpad law trace_sim gate policy per duty band",
        "axis": "firmware_partition",
        "delete_falsifier": "map buffer in SRAM_TILE scratchpad — Pope P6 violate silent",
        "verdict": "POPE_SCRATCHPAD_LAW_IRON_PASS" if iron.get("status") == "PASS" and _parse_summary(stdout) else "POPE_SCRATCHPAD_LAW_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    doc = run_lc2_pope_scratchpad_law_hil()
    print(json.dumps({"verdict": doc["verdict"], "trace_sim_bands": doc.get("trace_sim_bands"), "summary": doc.get("summary")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "POPE_SCRATCHPAD_LAW_IRON_PASS" else 1)
