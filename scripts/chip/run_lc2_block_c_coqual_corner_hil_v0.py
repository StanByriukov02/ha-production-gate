"""Block C co-qual corner iron — L1 gate for chip↔robot↔world chain."""
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
_IRON_RECEIPT = _CHIP / "CHIP_BLOCK_C_COQUAL_IRON_RECEIPT_v1.json"

_RTL = ("lc2_block_c_coqual_corner_tb_v0.v",)
_PASS = "TB_PASS"


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
    with tempfile.TemporaryDirectory(prefix="block_c_") as tmp:
        out_vvp = Path(tmp) / "sim.vvp"
        subprocess.run(
            [iverilog, "-g2012", *defines, "-o", str(out_vvp), "-I", str(_FIX), str(_FIX / _RTL[0])],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        sim = subprocess.run([vvp, str(out_vvp)], check=True, capture_output=True, text=True, timeout=120, env=env)
        stdout = (sim.stdout or "") + (sim.stderr or "")
    status = "PASS" if _PASS in stdout else "FAIL"
    return {"backend": "iverilog", "status": status, "top": "lc2_block_c_coqual_corner_tb_v0"}, stdout


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("COQUAL_PT "):
            continue
        corner = re.search(r"corner=(\S+)", line)
        row: dict[str, Any] = {"corner": corner.group(1) if corner else None}
        for key in (
            "falsifier_detected",
            "mitigation_verified",
            "tier_j_ok",
            "tunnel_pass",
            "temporal_pass",
            "vi2_hash_aligned",
            "integrated_pass",
        ):
            m = re.search(rf"{key}=(\d+)", line)
            if m:
                row[key] = int(m.group(1)) == 1
        rows.append(row)
    return rows


def run_lc2_block_c_coqual_iron(*, flags: dict[str, bool], write: bool = True) -> dict[str, Any]:
    params = {k: 1 if v else 0 for k, v in flags.items()}
    iron, stdout = _run_iverilog_full(params)
    payload: dict[str, Any] = {
        "iron_id": "CHIP_BLOCK_C_COQUAL_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "flags": flags,
        "points": _parse_pts(stdout),
        "rtl": [f"fixtures/chip/{_RTL[0]}"],
        "verdict": "BLOCK_C_COQUAL_IRON_PASS" if iron.get("status") == "PASS" else "BLOCK_C_COQUAL_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    raise SystemExit("use chip_block_c_coqual_chain_v1")
