"""FPGA carrier — yosys elaboration smoke (synth datapath + mapped replay)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FPGA = _CHIP / "fpga"
_FIX = _REPO / "fixtures" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_FPGA_YOSYS_ELAB_RECEIPT_v1.json"
_OUT_V = _FPGA / "clifford_fpga_yosys_elab_v0.v"
_MSYS = Path(r"C:\msys64\mingw64")

_SYNTH_RTL = (
    "clifford_f32_synth_v0.v",
    "clifford_geo_prod_synth_low_blades_v0.v",
    "clifford_geo_prod_synth_low_lo_blades_v0.v",
    "clifford_geo_prod_synth_low_hi_blades_v0.v",
    "clifford_geo_prod_synth_high_blades_v0.v",
    "clifford_geo_prod_synth_high_lo_blades_v0.v",
    "clifford_geo_prod_synth_high_hi_blades_v0.v",
    "clifford_geo_prod_synth_v0.v",
)


def _synth_carrier_files() -> tuple[list[Path], str]:
    paths = [_FIX / name for name in _SYNTH_RTL]
    return [p for p in paths if p.is_file()], "clifford_geo_prod_synth_v0"


def _mapped_replay_files() -> tuple[list[Path], str, Path | None]:
    mapped = _REPO / "results/platform_bpass/chip/sta/clifford_sta_geo_prod_slice_mapped_funcsim_v0.v"
    simcells = _MSYS / "share/yosys/simcells.v"
    if mapped.is_file() and simcells.is_file():
        return [mapped], "clifford_sta_geo_prod_slice_top_v0", simcells
    return [], "clifford_sta_geo_prod_slice_top_v0", None


def _find_yosys() -> str | None:
    for name in ("yosys", "yosys.exe"):
        p = shutil.which(name)
        if p:
            return p
    msys = _MSYS / "bin/yosys.exe"
    return str(msys) if msys.is_file() else None


def _write_tcl(
    paths: list[Path],
    tcl_path: Path,
    *,
    top: str,
    simcells: Path | None = None,
) -> None:
    lines = ["# Auto-generated yosys carrier smoke"]
    if simcells is not None:
        rel_lib = simcells.relative_to(_REPO).as_posix() if simcells.is_relative_to(_REPO) else str(simcells).replace("\\", "/")
        lines.append(f'read_verilog -lib "{rel_lib}"')
    for p in paths:
        rel = p.relative_to(_REPO).as_posix() if p.is_relative_to(_REPO) else str(p).replace("\\", "/")
        define = "-D YOSYS_SYNTH=1 " if "fixtures/chip" in rel else ""
        lines.append(f'read_verilog -sv {define}-I fixtures/chip "{rel}"')
    out_rel = _OUT_V.relative_to(_REPO).as_posix()
    lines.extend(
        [
            f"hierarchy -check -top {top}",
            "proc",
            "opt",
            "memory",
            "fsm",
            "opt",
            "stat",
            f'write_verilog "{out_rel}"',
        ]
    )
    tcl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_stat_cells(text: str) -> int:
    matches = [int(m) for m in re.findall(r"^\s+(\d+)\s+cells\s*$", text, re.MULTILINE)]
    return max(matches) if matches else 0


def _run_elab(yosys: str, paths: list[Path], *, top: str, simcells: Path | None) -> tuple[bool, str, int]:
    _FPGA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tcl = Path(tmp) / "smoke.tcl"
        _write_tcl(paths, tcl, top=top, simcells=simcells)
        proc = subprocess.run(
            [yosys, "-q", "-s", str(tcl)],
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            timeout=600,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        cells = _parse_stat_cells(out)
        ok = proc.returncode == 0 and _OUT_V.is_file() and _OUT_V.stat().st_size > 1000
        detail = (out[-400:]) if not ok else f"cells={cells}"
        lines = sum(1 for _ in _OUT_V.open(encoding="utf-8", errors="replace")) if _OUT_V.is_file() else 0
        return ok, detail, lines if ok else cells


def evaluate_fpga_yosys_smoke(*, write: bool = True) -> dict[str, Any]:
    yosys = _find_yosys()
    elab_ok = False
    detail = "yosys_missing"
    cell_lines = 0
    stat_cells = 0
    paths: list[Path] = []
    top = "clifford_geo_prod_synth_v0"
    elab_mode = "synth_datapath_geo_prod"

    if yosys:
        paths, top = _synth_carrier_files()
        if paths:
            elab_ok, detail, cell_lines = _run_elab(yosys, paths, top=top, simcells=None)
            if elab_ok:
                stat_cells = _parse_stat_cells(detail)
        if not elab_ok:
            paths, top, simcells = _mapped_replay_files()
            if paths:
                elab_mode = "mapped_replay_simcells"
                elab_ok, detail, cell_lines = _run_elab(yosys, paths, top=top, simcells=simcells)

    checks = [
        {"id": "yosys_present", "pass": yosys is not None},
        {"id": "rtl_closure_present", "pass": len(paths) >= 1},
        {"id": "elab_netlist_written", "pass": elab_ok},
    ]
    verdict = "FPGA_YOSYS_ELAB_PASS" if all(c["pass"] for c in checks) else "FPGA_YOSYS_ELAB_FAIL"
    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_FPGA_YOSYS_ELAB_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "rtl_file_count": len(paths),
        "elab_line_count": cell_lines,
        "yosys_stat_cells": stat_cells,
        "output": str(_OUT_V.relative_to(_REPO)).replace("\\", "/") if _OUT_V.is_file() else None,
        "honesty": {
            "crown_rtl": top,
            "elab_mode": elab_mode,
            "chip_role": "carrier_synth_smoke_only",
            "not_fpga_signoff": True,
            "not_bitstream": True,
        },
        "detail": detail,
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_fpga_yosys_smoke()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "FPGA_YOSYS_ELAB_PASS" else 1)
