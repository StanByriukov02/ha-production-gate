"""Lunar corner mitigation iron — 60MHz operating point + tier-J temporal."""
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
_IRON_RECEIPT = _CHIP / "CHIP_LUNAR_CORNER_MITIGATION_IRON_RECEIPT_v1.json"
_RTL = ("lc2_lunar_mitigation_operating_point_tb_v0.v",)
_PASS = "TB_PASS"


def _run_iverilog(params: dict[str, int]) -> tuple[dict[str, Any], str]:
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
    with tempfile.TemporaryDirectory(prefix="lunar_mit_") as tmp:
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
    return {"backend": "iverilog", "status": status, "top": "lc2_lunar_mitigation_operating_point_tb_v0"}, stdout


def run_lc2_lunar_mitigation_iron(*, params: dict[str, int], write: bool = True) -> dict[str, Any]:
    iron, stdout = _run_iverilog(params)
    payload: dict[str, Any] = {
        "iron_id": "CHIP_LUNAR_CORNER_MITIGATION_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "params": params,
        "rtl": [f"fixtures/chip/{_RTL[0]}"],
        "verdict": "LUNAR_MITIGATION_IRON_PASS" if iron.get("status") == "PASS" else "LUNAR_MITIGATION_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    raise SystemExit("use chip_lunar_corner_mitigation_v1")
