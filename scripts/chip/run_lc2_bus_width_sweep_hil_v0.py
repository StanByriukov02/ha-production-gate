"""LC2 bus-width G1 sweep iron — invent_wider_bus_tile sprint."""
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
_IRON_RECEIPT = _CHIP / "CHIP_WIDER_BUS_TILE_IRON_RECEIPT_v1.json"
_G1_BIND = _CHIP / "CHIP_G1_PR_RND_BIND_v1.json"

_RTL = ("lc2_bus_width_congestion_v0.v", "lc2_bus_width_sweep_tb_v0.v")
_PASS = "TB_PASS"


def _g1_params() -> dict[str, int]:
    if _G1_BIND.is_file():
        doc = json.loads(_G1_BIND.read_text(encoding="utf-8"))
        placement = doc.get("placement_model") or {}
        raw = float(placement.get("occupied_um2") or 0)
        logic_routed = float(placement.get("logic_routed_um2") or 0)
        base = int(round(max(raw, logic_routed, 51000)))
    else:
        base = 51000
    return {
        "BASE_AREA_UM2": base,
        "TILE_AREA_UM2": 159600,
        "INVENT_F_MHZ": 200,
        "TODAY_F_MHZ": 48,
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
    with tempfile.TemporaryDirectory(prefix="bus_width_") as tmp:
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
    return {"backend": "iverilog", "status": status, "top": "lc2_bus_width_sweep_tb_v0"}, stdout


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("BUS_PT "):
            continue
        w = re.search(r"width_bit=(\d+)", line)
        fm = re.search(r"f_mhz=(\d+)", line)
        area = re.search(r"area_um2=(\d+)", line)
        route = re.search(r"routing_um2=(\d+)", line)
        mbps = re.search(r"mbps=(\d+)", line)
        cong = re.search(r"congestion=(\d+)", line)
        rows.append(
            {
                "width_bit": int(w.group(1)) if w else None,
                "f_mhz": int(fm.group(1)) if fm else None,
                "area_um2": int(area.group(1)) if area else None,
                "routing_um2": int(route.group(1)) if route else None,
                "peak_mbps": int(mbps.group(1)) if mbps else None,
                "congestion": int(cong.group(1)) == 1 if cong else None,
            }
        )
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"BUS_SUMMARY invent_peak_mbps=(\d+) today_floor_mbps=(\d+) congestion_at_128=(\d+) monotone=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "invent_peak_mbps": int(m.group(1)),
        "today_floor_mbps": int(m.group(2)),
        "congestion_at_128": int(m.group(3)) == 1,
        "monotone": int(m.group(4)) == 1,
    }


def run_lc2_bus_width_sweep_hil(*, write: bool = True) -> dict[str, Any]:
    params = _g1_params()
    iron, stdout = _run_iverilog_full(params)
    pts = _parse_pts(stdout)
    summary = _parse_summary(stdout)
    payload: dict[str, Any] = {
        "iron_id": "CHIP_WIDER_BUS_TILE_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "params": params,
        "points": pts,
        "summary": summary,
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "floorplan feasibility signoff → G1 bus-width sweep + routing congestion proxy iron",
        "verdict": "WIDER_BUS_TILE_IRON_PASS" if iron.get("status") == "PASS" and summary else "WIDER_BUS_TILE_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    doc = run_lc2_bus_width_sweep_hil()
    print(json.dumps({"verdict": doc["verdict"], "summary": doc.get("summary"), "points": doc.get("points")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "WIDER_BUS_TILE_IRON_PASS" else 1)
