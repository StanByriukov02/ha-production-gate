"""LC2 carrier HBM MMIO iron — iverilog topology proof for invent_hbm_compute_die."""
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
_LOG = _CHIP / "CHIP_COMPUTE_CARRIER_HBM_MMIO_LOG_v1.json"
_IRON_RECEIPT = _CHIP / "CHIP_COMPUTE_CARRIER_HBM_MMIO_IRON_RECEIPT_v1.json"

_RTL = ("lc2_carrier_hbm_mmio_bridge_v0.v", "lc2_carrier_hbm_mmio_tb_v0.v")
_PASS = "TB_PASS"


def _run_iverilog_full(*, batch_bytes: int = 4096) -> tuple[dict[str, Any], str]:
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

    with tempfile.TemporaryDirectory(prefix="carrier_hbm_") as tmp:
        out_vvp = Path(tmp) / "sim.vvp"
        subprocess.run(
            [
                iverilog,
                "-g2012",
                f"-DBATCH_BYTES={batch_bytes}",
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
    return {"backend": "iverilog", "status": status, "top": "lc2_carrier_hbm_mmio_tb_v0"}, stdout


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("CARRIER_PT "):
            continue
        path = re.search(r"path=(\w+)", line)
        by = re.search(r"bytes=(\d+)", line)
        cy = re.search(r"cycles=(\d+)", line)
        bb = re.search(r"beat_bytes=(\d+)", line)
        rows.append(
            {
                "path": path.group(1) if path else None,
                "bytes": int(by.group(1)) if by else None,
                "cycles": int(cy.group(1)) if cy else None,
                "beat_bytes": int(bb.group(1)) if bb else None,
            }
        )
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"CARRIER_SUMMARY batch=(\d+) mcu_cycles=(\d+) hbm_cycles=(\d+) mcu_mbps=(\d+) hbm_mbps=(\d+) ratio=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "batch": int(m.group(1)),
        "mcu_cycles": int(m.group(2)),
        "hbm_cycles": int(m.group(3)),
        "mcu_mbps": int(m.group(4)),
        "hbm_mbps": int(m.group(5)),
        "cycle_ratio": int(m.group(6)),
    }


def run_lc2_carrier_hbm_mmio_hil(*, write: bool = True, batch_bytes: int = 4096) -> dict[str, Any]:
    iron, stdout = _run_iverilog_full(batch_bytes=batch_bytes)
    pts = _parse_pts(stdout)
    summary = _parse_summary(stdout)
    payload: dict[str, Any] = {
        "iron_id": "CHIP_COMPUTE_CARRIER_HBM_MMIO_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "points": pts,
        "summary": summary,
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "GPU HBM stack signoff slice → MMIO MCU vs carrier topology iron",
        "verdict": "CARRIER_HBM_MMIO_IRON_PASS" if iron.get("status") == "PASS" and summary else "CARRIER_HBM_MMIO_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _LOG.write_text(
            json.dumps(
                {"log_id": "CHIP_COMPUTE_CARRIER_HBM_MMIO_LOG_v1", "points": pts, "summary": summary},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    return payload


if __name__ == "__main__":
    doc = run_lc2_carrier_hbm_mmio_hil()
    print(json.dumps({"verdict": doc["verdict"], "summary": doc.get("summary")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "CARRIER_HBM_MMIO_IRON_PASS" else 1)
