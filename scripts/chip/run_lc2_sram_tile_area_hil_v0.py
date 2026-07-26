"""LC2 SRAM tile weste area iron — iverilog for SRAM_TILE_KB sprint."""
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
_IRON_RECEIPT = _CHIP / "CHIP_SRAM_TILE_AREA_IRON_RECEIPT_v1.json"
_CLOSURE = _CHIP / "CHIP_SRAM_PHYSICAL_CLOSURE_BIND_v1.json"
_PR = _CHIP / "LC2_TILE_PR_SUMMARY_v1.json"

_RTL = ("lc2_sram_tile_weste_area_tb_v0.v",)
_PASS = "TB_PASS"


def _area_params() -> dict[str, int]:
    doc = json.loads(_CLOSURE.read_text(encoding="utf-8"))
    pr = json.loads(_PR.read_text(encoding="utf-8"))
    weste = doc["closure"]["P1_weste_tile_area_model"]
    hyp = weste["hypothesis_8kb_macro_on_tile"]
    netlist = weste["actual_tile_sram_netlist"]
    tile = pr["tile_um"]
    return {
        "TILE_W_UM": int(tile["width"]),
        "TILE_H_UM": int(tile["height"]),
        "NETLIST_AREA_UM2": int(round(float(netlist["bitcell_area_um2_est"]))),
        "WESTE_ARRAY_UM2": int(round(float(hyp["array_area_um2_est"]))),
        "LINKER_KB": 8,
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
    with tempfile.TemporaryDirectory(prefix="sram_area_") as tmp:
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
    return {"backend": "iverilog", "status": status, "top": "lc2_sram_tile_weste_area_tb_v0"}, stdout


def _parse_pts(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("SRAM_PT "):
            continue
        variant = re.search(r"variant=(\S+)", line)
        area = re.search(r"area_um2=(\d+|NA)", line)
        kb = re.search(r"kb_equiv=(\d+)", line)
        scope = re.search(r"scope=(\S+)", line)
        fits = re.search(r"fits=(\d+)", line)
        tile = re.search(r"tile_um2=(\d+)", line)
        rows.append(
            {
                "variant": variant.group(1) if variant else None,
                "area_um2": area.group(1) if area else None,
                "kb_equiv": int(kb.group(1)) if kb else None,
                "scope": scope.group(1) if scope else None,
                "fits": int(fits.group(1)) if fits else None,
                "tile_um2": int(tile.group(1)) if tile else None,
            }
        )
    return rows


def _parse_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"SRAM_SUMMARY linker_kb=(\d+) netlist_pct_tile_x100=(\d+) weste_macro_fits=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "linker_kb": int(m.group(1)),
        "netlist_pct_tile_x100": int(m.group(2)),
        "weste_macro_fits": int(m.group(3)) == 1,
    }


def run_lc2_sram_tile_area_hil(*, write: bool = True) -> dict[str, Any]:
    params = _area_params()
    iron, stdout = _run_iverilog_full(params)
    pts = _parse_pts(stdout)
    summary = _parse_summary(stdout)
    payload: dict[str, Any] = {
        "iron_id": "CHIP_SRAM_TILE_AREA_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "params": params,
        "points": pts,
        "summary": summary,
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "foundry SRAM report → weste area proxy + linker cite reconcile iron",
        "verdict": "SRAM_TILE_AREA_IRON_PASS" if iron.get("status") == "PASS" and summary else "SRAM_TILE_AREA_IRON_FAIL",
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    doc = run_lc2_sram_tile_area_hil()
    print(json.dumps({"verdict": doc["verdict"], "summary": doc.get("summary")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "SRAM_TILE_AREA_IRON_PASS" else 1)
