"""Cryo power cold-start HIL — iverilog iron for NASA-CRYO-COTS-GAP sprint."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_CURVE = _CHIP / "CHIP_NASA_CRYO_POWER_CURVE_v1.json"
_IRON_RECEIPT = _CHIP / "CHIP_NASA_CRYO_POWER_HIL_IRON_RECEIPT_v1.json"

_RTL = ("lc2_cryo_ldo_behavioral_v0.v", "lc2_cryo_power_coldstart_tb_v0.v")
_PASS = "TB_PASS"


def _parse_cryo_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("CRYO_PT "):
            continue
        part = re.search(r"part=(\d+)", line)
        tk = re.search(r"T_k=(\d+)", line)
        drop = re.search(r"drop_pct=(\d+)\.(\d+)", line)
        vout = re.search(r"vout_mv=(\d+)", line)
        rows.append(
            {
                "part_class": int(part.group(1)) if part else None,
                "temp_k": int(tk.group(1)) if tk else None,
                "drop_pct": float(f"{drop.group(1)}.{drop.group(2)}") if drop else None,
                "vout_mv": int(vout.group(1)) if vout else None,
                "raw": line,
            }
        )
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"CRYO_SUMMARY cells=(\d+) pass=(\d+) screened_max_drop_pct_x100=(\d+) zener_max_drop_pct_x100=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "cells": int(m.group(1)),
        "pass": int(m.group(2)),
        "screened_max_drop_pct_x100": int(m.group(3)),
        "zener_max_drop_pct_x100": int(m.group(4)),
    }


def run_lc2_cryo_power_coldstart(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from dogfood_platform.chip_clifford_rtl_sim_v1 import sim_iverilog

    iron = sim_iverilog("lc2_cryo_power_coldstart_tb_v0", _RTL, _PASS, timeout=60)
    stdout = iron.get("stdout_full") or (iron.get("stdout_tail") or "") + str(iron.get("reason") or "")
    if iron.get("status") == "PASS" and "CRYO_PT part=0" not in stdout:
        import os
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path as P

        fix = _REPO / "fixtures" / "chip"
        iverilog = shutil.which("iverilog") or shutil.which("iverilog.exe")
        vvp = shutil.which("vvp") or shutil.which("vvp.exe")
        if iverilog and vvp:
            with tempfile.TemporaryDirectory(prefix="cryo_hil_") as tmp:
                out_vvp = P(tmp) / "sim.vvp"
                env = os.environ.copy()
                msys = P(r"C:\msys64\mingw64\bin")
                if msys.is_dir():
                    env["PATH"] = f"{msys};{env.get('PATH', '')}"
                subprocess.run(
                    [iverilog, "-g2012", "-o", str(out_vvp), "-I", str(fix), *[fix / r for r in _RTL]],
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
                    timeout=60,
                    env=env,
                )
                stdout = (sim.stdout or "") + (sim.stderr or "")
                iron = {**iron, "stdout_full": stdout}
    pts = _parse_cryo_pts(stdout)
    summary = _parse_summary(stdout)

    payload: dict[str, Any] = {
        "iron_id": "CHIP_NASA_CRYO_POWER_HIL_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "curve_points": pts,
        "summary": summary,
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "ICE PUCC / cryo vacuum LDO cold-start campaign slice",
        "cite": "results/platform_bpass/moon/LSIC_NASA_GRC_CRYO_ELECTRONICS_CAPTURE_v1.json",
        "verdict": "CRYO_POWER_HIL_IRON_PASS" if iron.get("status") == "PASS" and summary else "CRYO_POWER_HIL_IRON_FAIL",
    }

    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _CURVE.write_text(
            json.dumps(
                {
                    "curve_id": "CHIP_NASA_CRYO_POWER_CURVE_v1",
                    "timestamp_utc": payload["timestamp_utc"],
                    "points": pts,
                    "summary": summary,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    return payload


if __name__ == "__main__":
    doc = run_lc2_cryo_power_coldstart()
    print(json.dumps({"verdict": doc["verdict"], "summary": doc.get("summary")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "CRYO_POWER_HIL_IRON_PASS" else 1)
