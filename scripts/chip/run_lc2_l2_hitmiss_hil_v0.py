"""LC2 L2 hit/miss iron — iverilog for CACHE_L2_KB sprint."""
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
_IRON_RECEIPT = _CHIP / "CHIP_CACHE_L2_HITMISS_IRON_RECEIPT_v1.json"

_RTL = ("lc2_l2_directmap_v0.v", "lc2_l2_hitmiss_tb_v0.v")
_PASS = "TB_PASS"


def _derived_params() -> dict[str, int]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))
    from dogfood_platform.chip_cache_l2_on_derived_bind_v1 import derive_cache_l2_on_bind

    spec = derive_cache_l2_on_bind()
    mt = spec["miss_threshold"]
    host_kb = int(spec["scope_split"]["host_lpddr_class"]["value_kb_derived"])
    return {
        "SCRATCH_BYTES": 8192,
        "L1_BYTES": int(mt["l1_fast_bytes"]),
        "HOST_L2_BYTES": host_kb * 1024,
        "STRETCHED_WS": int(mt["stretched_working_set_bytes"]),
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
    with tempfile.TemporaryDirectory(prefix="l2_hitmiss_") as tmp:
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
    return {"backend": "iverilog", "status": status, "top": "lc2_l2_hitmiss_tb_v0"}, stdout


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("L2_PT "):
            continue
        path = re.search(r"path=(\w+)", line)
        ws = re.search(r"ws=(\d+)", line)
        hits = re.search(r"hits=(\d+)", line)
        misses = re.search(r"misses=(\d+)", line)
        fast = re.search(r"fast=(\d+)", line)
        l2 = re.search(r"l2=(\d+)", line)
        miss = re.search(r"miss=(\d+)", line)
        l2_kb = re.search(r"l2_kb=(\d+)", line)
        rows.append(
            {
                "path": path.group(1) if path else None,
                "ws": int(ws.group(1)) if ws else None,
                "hits": int(hits.group(1)) if hits else None,
                "misses": int(misses.group(1)) if misses else None,
                "fast": int(fast.group(1)) if fast else None,
                "l2": int(l2.group(1)) if l2 else None,
                "miss": int(miss.group(1)) if miss else None,
                "l2_kb": int(l2_kb.group(1)) if l2_kb else None,
            }
        )
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"L2_SUMMARY scratch_b=(\d+) l1_b=(\d+) host_l2_kb=(\d+) stretched_ws=(\d+) joint_miss_beyond_scratch=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "scratch_bytes": int(m.group(1)),
        "l1_bytes": int(m.group(2)),
        "host_l2_kb": int(m.group(3)),
        "stretched_ws": int(m.group(4)),
        "joint_miss_beyond_scratch": int(m.group(5)) == 1,
    }


def run_lc2_l2_hitmiss_hil(*, write: bool = True) -> dict[str, Any]:
    params = _derived_params()
    iron, stdout = _run_iverilog_full(params)
    pts = _parse_pts(stdout)
    summary = _parse_summary(stdout)
    payload: dict[str, Any] = {
        "iron_id": "CHIP_CACHE_L2_HITMISS_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "params": params,
        "points": pts,
        "summary": summary,
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "SRAM compiler L2 signoff → hit/miss vs regfile16 derived threshold iron",
        "verdict": "CACHE_L2_HITMISS_IRON_PASS" if iron.get("status") == "PASS" and summary else "CACHE_L2_HITMISS_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    doc = run_lc2_l2_hitmiss_hil()
    print(json.dumps({"verdict": doc["verdict"], "summary": doc.get("summary")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "CACHE_L2_HITMISS_IRON_PASS" else 1)
