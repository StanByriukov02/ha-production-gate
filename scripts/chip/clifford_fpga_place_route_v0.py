"""FPGA place & route attempt — yosys → nextpnr-ecp5 → bit file (honest tier).

NOT signoff until: timing closed @ mission clock · measured MMIO HIL · ERF gate.
TABU: claim FPGA_SIGNOFF · claim 100 MHz.
"""
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
_RECEIPT = _CHIP / "CHIP_CLIFFORD_FPGA_PLACE_ROUTE_RECEIPT_v1.json"
_LPF = _FPGA / "clifford_carrier_bringup_v0.lpf"
_JSON_OUT = _FPGA / "clifford_fpga_nextpnr_v0.json"
_BIT_OUT = _FPGA / "clifford_fpga_bringup_v0.bit"
_MSYS = Path(r"C:\msys64")
_DEVICE = "LFE5U-85F-6BG381C"
_TOP = "clifford_fpga_bringup_top_v0"
_TOP_LOW_LO = "clifford_fpga_bringup_low_lo_top_v0"
_TOP_LOW_LO_PIPE = "clifford_fpga_bringup_low_lo_pipelined_top_v0"
_BRINGUP_RTL = _FIX / "clifford_fpga_bringup_top_v0.v"
_BRINGUP_LOW_LO_RTL = _FIX / "clifford_fpga_bringup_low_lo_top_v0.v"
_BRINGUP_LOW_LO_PIPE_RTL = _FIX / "clifford_fpga_bringup_low_lo_pipelined_top_v0.v"
_LPF_GEO = _FPGA / "clifford_fpga_bringup_geo_v0.lpf"

_SLICE_CFG: dict[str, dict[str, Any]] = {
    "full": {
        "top": _TOP,
        "bringup": _BRINGUP_RTL,
        "geo_modules": (
            "clifford_f32_synth_v0.v",
            "clifford_geo_prod_synth_low_blades_v0.v",
            "clifford_geo_prod_synth_low_lo_blades_v0.v",
            "clifford_geo_prod_synth_low_hi_blades_v0.v",
            "clifford_geo_prod_synth_high_blades_v0.v",
            "clifford_geo_prod_synth_high_lo_blades_v0.v",
            "clifford_geo_prod_synth_high_hi_blades_v0.v",
            "clifford_geo_prod_synth_v0.v",
        ),
        "json_out": _FPGA / "clifford_fpga_nextpnr_v0.json",
        "bit_out": _FPGA / "clifford_fpga_bringup_v0.bit",
        "textcfg": _FPGA / "clifford_fpga_bringup_v0.config",
    },
    "low_lo": {
        "top": _TOP_LOW_LO,
        "bringup": _BRINGUP_LOW_LO_RTL,
        "geo_modules": (
            "clifford_f32_synth_v0.v",
            "clifford_geo_prod_synth_low_lo_blades_v0.v",
        ),
        "json_out": _FPGA / "clifford_fpga_bringup_low_lo_v0.json",
        "bit_out": _FPGA / "clifford_fpga_bringup_low_lo_v0.bit",
        "textcfg": _FPGA / "clifford_fpga_bringup_low_lo_v0.config",
    },
    "low_lo_pipelined": {
        "top": _TOP_LOW_LO_PIPE,
        "bringup": _BRINGUP_LOW_LO_PIPE_RTL,
        "geo_modules": (
            "clifford_f32_synth_v0.v",
            "clifford_geo_prod_synth_low_lo_blades_v0.v",
        ),
        "json_out": _FPGA / "clifford_fpga_bringup_low_lo_pipelined_v0.json",
        "bit_out": _FPGA / "clifford_fpga_bringup_low_lo_pipelined_v0.bit",
        "textcfg": _FPGA / "clifford_fpga_bringup_low_lo_pipelined_v0.config",
    },
    "low_lo_multicycle": {
        "top": "clifford_fpga_bringup_low_lo_multicycle_top_v0",
        "bringup": _FIX / "clifford_fpga_bringup_low_lo_multicycle_top_v0.v",
        "geo_modules": (
            "clifford_f32_synth_v0.v",
            "clifford_fpga_low_lo_geo_mmio_fsm_v0.v",
        ),
        "json_out": _FPGA / "clifford_fpga_bringup_low_lo_multicycle_v0.json",
        "bit_out": _FPGA / "clifford_fpga_bringup_low_lo_multicycle_v0.bit",
        "textcfg": _FPGA / "clifford_fpga_bringup_low_lo_multicycle_v0.config",
    },
}


def _find_tool(names: tuple[str, ...]) -> str | None:
    for name in names:
        p = shutil.which(name)
        if p:
            return p
        msys = _MSYS / "mingw64" / "bin" / name
        if msys.is_file():
            return str(msys)
    return None


def _synth_rtl_paths(*, slice_id: str = "full") -> list[Path]:
    cfg = _SLICE_CFG.get(slice_id, _SLICE_CFG["full"])
    paths = [_FIX / name for name in cfg["geo_modules"]]
    paths = [p for p in paths if p.is_file()]
    bringup = cfg["bringup"]
    if bringup.is_file():
        paths = list(paths) + [bringup]
    return paths


def _active_slice_cfg(slice_id: str) -> dict[str, Any]:
    return _SLICE_CFG.get(slice_id, _SLICE_CFG["full"])


def _write_bringup_lpf() -> None:
    pinmap_path = _REPO / "fixtures" / "chip" / "clifford_carrier_ulx3s_pinmap_v0.json"
    clk_site = "A10"
    rst_site = "R1"
    if pinmap_path.is_file():
        pinmap = json.loads(pinmap_path.read_text(encoding="utf-8"))
        clk_site = pinmap.get("clock_source", {}).get("site", clk_site)
        rst_site = pinmap.get("reset", {}).get("site", rst_site)
    _FPGA.mkdir(parents=True, exist_ok=True)
    _LPF_GEO.write_text(
        f"""# geo_prod bring-up slice — clk + rst (vector IO virtual via nextpnr flag)
FREQUENCY PORT "clk" 27.5 MHz;
LOCATE COMP "clk" SITE "{clk_site}" ;
LOCATE COMP "rst" SITE "{rst_site}" ;
""",
        encoding="utf-8",
    )


def _write_yosys_tcl(tcl_path: Path, paths: list[Path], *, top: str, json_out: Path) -> None:
    lines = ["# Auto-generated FPGA carrier synth"]
    for p in paths:
        rel = p.relative_to(_REPO).as_posix()
        lines.append(f'read_verilog -sv -D YOSYS_SYNTH=1 -I fixtures/chip "{rel}"')
    out = json_out.relative_to(_REPO).as_posix()
    lines.extend(
        [
            f"hierarchy -check -top {top}",
            "proc; opt; memory; fsm; opt",
            f"synth_ecp5 -top {top}",
            "dfflegalize -cell $_DFF_PN0_ 0",
            f'write_json "{out}"',
            "stat",
        ]
    )
    tcl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_yosys(yosys: str, paths: list[Path], *, top: str, json_out: Path, timeout_s: int = 7200) -> tuple[bool, str, str | None]:
    _FPGA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tcl = Path(tmp) / "pnr_synth.tcl"
        _write_yosys_tcl(tcl, paths, top=top, json_out=json_out)
        try:
            proc = subprocess.run(
                [yosys, "-q", "-s", str(tcl)],
                cwd=str(_REPO),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return False, f"synth_ecp5_timeout_{timeout_s}s", "synth_ecp5_timeout"
        out = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0 and json_out.is_file() and json_out.stat().st_size > 500
        err = None if ok else f"yosys_exit_{proc.returncode}"
        return ok, out[-800:], err


def _run_ecppack(ecppack: str, textcfg: Path, *, bit_out: Path) -> tuple[bool, str]:
    if bit_out.is_file():
        bit_out.unlink()
    proc = subprocess.run(
        [ecppack, "--compress", str(textcfg), str(bit_out)],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and bit_out.is_file() and bit_out.stat().st_size > 100
    return ok, out[-800:]


def _parse_timing_report(report_path: Path, *, mission_mhz: float = 27.5) -> dict[str, Any]:
    if not report_path.is_file():
        return {}
    try:
        doc = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, Any] = {"report_parsed": True}

    fmax = doc.get("fmax") or {}
    if isinstance(fmax, dict):
        for key, val in fmax.items():
            if isinstance(val, dict):
                achieved = val.get("achieved")
                constraint = val.get("constraint")
                if achieved:
                    out["max_freq_mhz_clk"] = round(float(achieved), 2)
                    out["max_freq_mhz"] = out["max_freq_mhz_clk"]
                    out["timing_domain"] = "clk"
                    out["clk_port"] = str(key)
                    if constraint:
                        out["clk_constraint_mhz"] = round(float(constraint), 2)
                    break
            elif val and str(key).lower() in ("clk", "clock"):
                out["max_freq_mhz_clk"] = round(float(val), 2)
                out["max_freq_mhz"] = out["max_freq_mhz_clk"]
                out["timing_domain"] = "clk"
                break

    util = doc.get("utilization") or {}
    comb = util.get("TRELLIS_COMB") or {}
    if comb.get("available"):
        used = int(comb.get("used") or 0)
        avail = int(comb["available"])
        out["comb_used"] = used
        out["comb_budget"] = avail
        out["comb_util_frac"] = round(used / avail, 4)
    mult = util.get("MULT18X18D") or {}
    if mult.get("available"):
        out["mult18_used"] = int(mult.get("used") or 0)
        out["mult18_budget"] = int(mult["available"])

    worst_ns = 0.0
    async_worst = 0.0
    for cp in doc.get("critical_paths") or []:
        total = sum(float(hop.get("delay") or 0) for hop in cp.get("path") or [])
        worst_ns = max(worst_ns, total)
        if cp.get("from") == "<async>":
            async_worst = max(async_worst, total)
    if async_worst > 0:
        out["async_worst_path_ns"] = round(async_worst, 3)
    if worst_ns > 0 and "max_freq_mhz" not in out:
        out["max_delay_ns"] = round(worst_ns, 3)
        out["max_freq_mhz"] = round(1000.0 / worst_ns, 2)
        out["timing_domain"] = out.get("timing_domain", "async_comb")

    out["mission_clock_mhz"] = mission_mhz
    out["mission_clock_feasible"] = bool(out.get("max_freq_mhz_clk", out.get("max_freq_mhz", 0)) >= mission_mhz)
    return out


def _run_nextpnr(
    nextpnr: str, *, json_out: Path, textcfg: Path, bit_out: Path, report_out: Path | None = None
) -> tuple[bool, str, dict[str, Any]]:
    _write_bringup_lpf()
    lpf = _LPF_GEO if _LPF_GEO.is_file() else _LPF
    if bit_out.is_file():
        bit_out.unlink()
    args = [
        nextpnr,
        "--85k",
        "--package",
        "CABGA381",
        "--json",
        str(json_out),
        "--lpf",
        str(lpf),
        "--lpf-allow-unconstrained",
        "--textcfg",
        str(textcfg),
    ]
    if report_out is not None:
        args.extend(["--report", str(report_out)])
    proc = subprocess.run(
        args,
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    timing: dict[str, Any] = {}
    for pat, key in (
        (r"Max delay <[^>]*>: ([-\d.]+)", "max_delay_ns"),
        (r"Max frequency for clock '[^']+': ([\d.]+) MHz", "max_freq_mhz"),
    ):
        m = re.search(pat, out)
        if m:
            timing[key] = float(m.group(1))
    cfg_ok = proc.returncode == 0 and textcfg.is_file() and textcfg.stat().st_size > 50
    ecppack = _find_tool(("ecppack", "ecppack.exe"))
    bit_ok = False
    if cfg_ok and ecppack:
        bit_ok, pack_out = _run_ecppack(ecppack, textcfg, bit_out=bit_out)
        out = out + "\n" + pack_out
    ok = bit_ok or cfg_ok
    timing["textcfg_ok"] = cfg_ok
    timing["bitstream_ok"] = bit_ok
    timing["ecppack"] = ecppack
    if report_out is not None and report_out.is_file():
        timing.update(_parse_timing_report(report_out))
    return ok, out[-1200:], timing


def evaluate_fpga_place_route(
    *, write: bool = True, quick: bool = False, nextpnr_only: bool = False, slice_id: str = "full"
) -> dict[str, Any]:
    cfg = _active_slice_cfg(slice_id)
    top = cfg["top"]
    json_out: Path = cfg["json_out"]
    bit_out: Path = cfg["bit_out"]
    textcfg: Path = cfg["textcfg"]
    yosys = _find_tool(("yosys", "yosys.exe"))
    nextpnr = _find_tool(("nextpnr-ecp5", "nextpnr-ecp5.exe"))
    paths = _synth_rtl_paths(slice_id=slice_id)

    if quick:
        from scripts.chip.clifford_fpga_yosys_smoke_v0 import evaluate_fpga_yosys_smoke

        smoke = evaluate_fpga_yosys_smoke(write=False)
        doc: dict[str, Any] = {
            "receipt_id": "CHIP_CLIFFORD_FPGA_PLACE_ROUTE_RECEIPT_v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "verdict": "FPGA_PLACE_ROUTE_QUICK_READY" if yosys and nextpnr and smoke["verdict"] == "FPGA_YOSYS_ELAB_PASS" else "FPGA_PLACE_ROUTE_QUICK_FAIL",
            "quick": True,
            "tools": {"yosys": yosys, "nextpnr_ecp5": nextpnr},
            "yosys_smoke": smoke.get("verdict"),
            "blockers": [] if nextpnr else ["nextpnr_ecp5_missing"],
            "honesty": {"not_fpga_signoff": True, "full_pnr_parked_in_quick": True},
            "next": "python scripts/chip/clifford_fpga_place_route_v0.py  # full P&R ~10-30 min",
        }
        if write:
            _CHIP.mkdir(parents=True, exist_ok=True)
            _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        return doc

    yosys_ok = False
    yosys_detail = "yosys_missing"
    yosys_err: str | None = None
    if nextpnr_only and json_out.is_file() and json_out.stat().st_size > 500:
        yosys_ok = True
        yosys_detail = "skipped_nextpnr_only_json_on_disk"
    elif yosys and paths:
        yosys_ok, yosys_detail, yosys_err = _run_yosys(yosys, paths, top=top, json_out=json_out)

    pnr_ok = False
    pnr_detail = "nextpnr_missing"
    timing: dict[str, Any] = {}
    if yosys_ok and nextpnr:
        report_out = textcfg.with_suffix(".timing.rpt")
        pnr_ok, pnr_detail, timing = _run_nextpnr(
            nextpnr, json_out=json_out, textcfg=textcfg, bit_out=bit_out, report_out=report_out
        )
        if report_out.is_file():
            timing["report"] = str(report_out.relative_to(_REPO)).replace("\\", "/")
    elif yosys_ok:
        pnr_detail = "install: pacman -S mingw-w64-x86_64-nextpnr"

    bit_ok = bit_out.is_file() and bit_out.stat().st_size > 100
    textcfg_ok = textcfg.is_file() and textcfg.stat().st_size > 50
    mission_mhz = 27.5
    freq_ok = timing.get("mission_clock_feasible") is True or (
        timing.get("max_freq_mhz_clk", timing.get("max_freq_mhz", 0)) >= mission_mhz
    )

    checks = [
        {"id": "yosys_synth_json", "pass": yosys_ok},
        {"id": "nextpnr_present", "pass": nextpnr is not None},
        {"id": "place_route_textcfg", "pass": textcfg_ok or timing.get("textcfg_ok") is True},
        {"id": "place_route_bit", "pass": bit_ok},
        {"id": "mission_clock_feasible", "pass": freq_ok or not (bit_ok or textcfg_ok), "detail": str(timing)},
        {"id": "no_signoff_claim", "pass": True},
    ]
    if bit_ok and not freq_ok:
        checks.append(
            {
                "id": "timing_not_closed",
                "pass": False,
                "detail": f"need >={mission_mhz} MHz; got {timing}",
            }
        )

    blockers: list[str] = []
    if not yosys:
        blockers.append("yosys_missing")
    if not nextpnr:
        blockers.append("nextpnr_ecp5_missing")
    if not textcfg_ok and not bit_ok:
        blockers.append("no_textcfg_or_bitstream_artifact")
    if textcfg_ok and not bit_ok:
        blockers.append("ecppack_missing_for_bitstream")
    if "MULT18X18D" in pnr_detail or "no BELs remaining" in pnr_detail:
        blockers.append("device_capacity_overflow_geo_prod_85k")
    if yosys_err == "synth_ecp5_timeout":
        blockers.append("synth_ecp5_timeout_agent_or_wall_clock")
    if bit_ok and not freq_ok:
        blockers.append("timing_not_closed_mission_clock")
    blockers.extend(
        [
            "mmio_hil_unmeasured_on_board",
            "erf_gate_not_run",
            "full_mmio_top_not_routed_yet",
        ]
    )

    verdict = "FPGA_PLACE_ROUTE_PASS" if bit_ok and freq_ok else (
        "FPGA_PLACE_ROUTE_PARTIAL" if (textcfg_ok or yosys_ok or yosys_err == "synth_ecp5_timeout") else "FPGA_PLACE_ROUTE_FAIL"
    )

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_FPGA_PLACE_ROUTE_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "device": _DEVICE,
        "slice_id": slice_id,
        "top_module": top,
        "mission_clock_mhz": mission_mhz,
        "tools": {"yosys": yosys, "nextpnr_ecp5": nextpnr},
        "artifacts": {
            "yosys_json": str(json_out.relative_to(_REPO)).replace("\\", "/") if json_out.is_file() else None,
            "bitstream": str(bit_out.relative_to(_REPO)).replace("\\", "/") if bit_ok else None,
            "textcfg": str(textcfg.relative_to(_REPO)).replace("\\", "/") if textcfg_ok else None,
            "lpf": str(_LPF.relative_to(_REPO)).replace("\\", "/") if _LPF.is_file() else None,
        },
        "timing": timing,
        "checks": checks,
        "blockers": blockers,
        "honesty": {
            "not_fpga_signoff": True,
            "carrier_slice_only": True,
            "full_mmio_top_parked": True,
            "measured_hil_required": True,
        },
        "detail": {"yosys": yosys_detail, "nextpnr": pnr_detail, "yosys_error": yosys_err},
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    import sys

    slice_id = "full"
    for i, arg in enumerate(sys.argv):
        if arg == "--slice" and i + 1 < len(sys.argv):
            slice_id = sys.argv[i + 1]
    out = evaluate_fpga_place_route(
        nextpnr_only="--nextpnr-only" in sys.argv,
        slice_id=slice_id,
    )
    print(json.dumps({"verdict": out["verdict"], "blockers": out["blockers"]}, indent=2))
    raise SystemExit(0 if out["verdict"] == "FPGA_PLACE_ROUTE_PASS" else 1)
