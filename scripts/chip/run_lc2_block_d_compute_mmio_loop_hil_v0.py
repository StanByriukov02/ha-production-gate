"""Block D compute MMIO loop iron — pose + M3 + session policy flags."""
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
_IRON_RECEIPT = _CHIP / "CHIP_BLOCK_D_COMPUTE_IRON_RECEIPT_v1.json"
_RTL = ("lc2_block_d_compute_mmio_loop_tb_v0.v",)
_PASS = "TB_PASS"


def run_lc2_block_d_compute_iron(*, flags: dict[str, bool], write: bool = True) -> dict[str, Any]:
    iverilog = shutil.which("iverilog") or shutil.which("iverilog.exe")
    vvp = shutil.which("vvp") or shutil.which("vvp.exe")
    msys = Path(r"C:\msys64\mingw64\bin")
    if not iverilog and (msys / "iverilog.exe").is_file():
        iverilog = str(msys / "iverilog.exe")
    if not vvp and (msys / "vvp.exe").is_file():
        vvp = str(msys / "vvp.exe")

    iron: dict[str, Any] = {"backend": "iverilog", "status": "SKIPPED", "reason": "iverilog missing"}
    stdout = ""
    if iverilog and vvp:
        env = os.environ.copy()
        if msys.is_dir():
            env["PATH"] = f"{msys};{env.get('PATH', '')}"
        defines = [f"-D{k}={1 if v else 0}" for k, v in flags.items()]
        with tempfile.TemporaryDirectory(prefix="block_d_") as tmp:
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
        iron = {
            "backend": "iverilog",
            "status": "PASS" if _PASS in stdout else "FAIL",
            "top": "lc2_block_d_compute_mmio_loop_tb_v0",
        }

    payload: dict[str, Any] = {
        "iron_id": "CHIP_BLOCK_D_COMPUTE_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "flags": flags,
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "rtl": [f"fixtures/chip/{_RTL[0]}"],
        "verdict": "BLOCK_D_COMPUTE_IRON_PASS" if iron.get("status") == "PASS" else "BLOCK_D_COMPUTE_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    raise SystemExit("use chip_block_d_compute_chain_v1")
