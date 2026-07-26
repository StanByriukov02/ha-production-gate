"""P5.20 — OpenSTA liberty timing hop (full ALU mapped slice)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STA_OUT = _CHIP / "sta"
_LIBERTY = _REPO / "tools" / "opensta" / "src" / "test" / "nangate45" / "Nangate45_typ.lib"
_MAPPED = _STA_OUT / "clifford_sta_alu_slice_mapped_v0.v"
_YS = _REPO / "scripts" / "chip" / "clifford_sta_alu_slice_mapped_v0.ys"
_SDC = _REPO / "fixtures" / "chip" / "sta" / "clifford_sta_alu_slice_v0.sdc"
_TCL = _REPO / "scripts" / "chip" / "clifford_sta_liberty_alu_slice_v0.tcl"
_MANIFEST = _REPO / "fixtures" / "chip" / "sta" / "clifford_alu_sta_liberty_full_manifest_v1.json"
_TOP = "clifford_sta_alu_liberty_top_v0"

_RTL_FILES = (
    "fixtures/chip/sta/clifford_sta_sim_blackbox_v0.v",
    "fixtures/chip/clifford_f32_synth_v0.v",
    "fixtures/chip/clifford_geo_prod_synth_v0.v",
    "fixtures/chip/clifford_geo_prod_synth_low_blades_v0.v",
    "fixtures/chip/clifford_geo_prod_synth_low_lo_blades_v0.v",
    "fixtures/chip/clifford_geo_prod_synth_low_hi_blades_v0.v",
    "fixtures/chip/clifford_geo_prod_synth_high_blades_v0.v",
    "fixtures/chip/clifford_geo_prod_synth_high_lo_blades_v0.v",
    "fixtures/chip/clifford_geo_prod_synth_high_hi_blades_v0.v",
    "fixtures/chip/clifford_reverse_synth_v0.v",
    "fixtures/chip/clifford_f32_nr_v0.v",
    "fixtures/chip/clifford_norm_synth_acc_low_v0.v",
    "fixtures/chip/clifford_norm_synth_acc_tail_v0.v",
    "fixtures/chip/clifford_norm_synth_scale_v0.v",
    "fixtures/chip/clifford_norm_synth_v0.v",
    "fixtures/chip/clifford_geo_prod_ex_pipe_v0.v",
    "fixtures/chip/clifford_sandwich_ex_pipe_v0.v",
    "fixtures/chip/clifford_norm_ex_pipe_v0.v",
    "fixtures/chip/clifford_geo_prod_cga_v0.v",
    "fixtures/chip/clifford_geo_prod_cga_synth_v0.v",
    "fixtures/chip/clifford_geo_prod_cga_ex_pipe_v0.v",
    "fixtures/chip/clifford_phi_fsm_v0.v",
    "fixtures/chip/clifford_alu_top_v0.v",
    "fixtures/chip/clifford_alu_sta_top_v0.v",
    "fixtures/chip/sta/clifford_sta_alu_liberty_top_v0.v",
)

_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"
_MSYS_BASH = Path(r"C:\msys64") / "usr" / "bin" / "bash.exe"
_CUDD_BIN = _REPO / "tools" / "opensta" / "cudd" / "bin"

_CELL_FLOOR = 5000
_DFF_FLOOR = 50


def _mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    extra = os.pathsep.join(
        str(p)
        for p in (_MSYS_BIN, _CUDD_BIN, _REPO / "tools" / "opensta" / "cudd" / "lib")
        if Path(p).is_dir()
    )
    env["PATH"] = f"{extra};{env.get('PATH', '')}" if extra else env.get("PATH", "")
    env["PYTHONPATH"] = str(_REPO)
    return env


def _msys_path(p: Path) -> str:
    s = str(p.resolve())
    if len(s) >= 2 and s[1] == ":":
        return "/" + s[0].lower() + s[2:].replace("\\", "/")
    return s.replace("\\", "/")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _git_sha() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(_REPO),
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _tool_version(cmd: list[str]) -> str | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=_mingw_env())
        out = (proc.stdout or proc.stderr or "").strip().splitlines()
        return out[0] if out else None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _yosys_path() -> str | None:
    for name in ("yosys", "yosys.exe"):
        p = shutil.which(name) or (_MSYS_BIN / name if (_MSYS_BIN / name).is_file() else None)
        if p:
            return str(p)
    return None


def _sta_path() -> str | None:
    candidate = _REPO / "tools" / "opensta" / "build-final" / "sta.exe"
    if candidate.is_file() and candidate.stat().st_size > 1_000_000:
        return str(candidate)
    return shutil.which("sta") or shutil.which("sta.exe")


def _count_mapped_cells(text: str) -> tuple[int, int]:
    insts = re.findall(r"^\s+(\w+)\s+(_\d+_|\\[^\s]+)\s*\(", text, re.MULTILINE)
    cells = len(insts)
    dff = sum(1 for cell, _ in insts if cell.startswith("DFF_"))
    return cells, dff


def _provenance() -> dict[str, Any]:
    rtl_hashes = []
    for rel in _RTL_FILES:
        p = _REPO / rel
        if p.is_file():
            rtl_hashes.append({"path": rel, "sha256": _sha256(p)})
    prov: dict[str, Any] = {
        "yosys_version": _tool_version([_yosys_path() or "yosys", "-V"]) if _yosys_path() else None,
        "opensta_version": _tool_version([_sta_path() or "sta", "-version"]) if _sta_path() else None,
        "liberty_path": str(_LIBERTY.relative_to(_REPO)),
        "liberty_sha256": _sha256(_LIBERTY) if _LIBERTY.is_file() else None,
        "liberty_corner": "NangateOpenCellLibrary typical 25C 1.1V",
        "git_sha": _git_sha(),
        "rtl_files": rtl_hashes,
        "sdc_path": str(_SDC.relative_to(_REPO)),
        "sdc_sha256": _sha256(_SDC) if _SDC.is_file() else None,
        "tcl_path": str(_TCL.relative_to(_REPO)),
        "top_module": _TOP,
    }
    return prov


def _run_yosys_mapped() -> dict[str, Any]:
    yosys = _yosys_path()
    if not yosys:
        return {"status": "SKIPPED", "reason": "yosys missing", "top": _TOP}
    if not _LIBERTY.is_file():
        return {"status": "FAIL", "reason": "Nangate45_typ.lib missing", "top": _TOP}
    _STA_OUT.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [yosys, str(_YS)],
            cwd=str(_REPO),
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
            env=_mingw_env(),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if not _MAPPED.is_file():
            return {"status": "FAIL", "reason": "mapped netlist not written", "top": _TOP}
        text = _MAPPED.read_text(encoding="utf-8", errors="replace")
        cells, dff = _count_mapped_cells(text)
        has_stdcell = "DFF_X1" in text and "INV_X1" in text
        top_ok = _TOP in text or "clifford_sta_alu_liberty_top_v0" in text
        sane = cells >= _CELL_FLOOR and dff >= _DFF_FLOOR
        return {
            "status": "PASS" if has_stdcell and sane and top_ok else "FAIL",
            "top": _TOP,
            "netlist": str(_MAPPED.relative_to(_REPO)),
            "cells": cells,
            "dff_count": dff,
            "stdcell_mapped": has_stdcell,
            "cell_count_sane": sane,
            "stdout_tail": out[-600:],
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        tail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            tail = (exc.stdout or exc.stderr or str(exc))[-800:]
        return {"status": "FAIL", "reason": tail, "top": _TOP}


def _parse_timing_report(out: str) -> dict[str, Any]:
    checks_ok = "LIBERTY_TIMING_CHECKS_OK" in out
    wns_ns: float | None = None
    mcp_resolved = 0
    mcp_groups = 0
    for line in out.splitlines():
        m_ws = re.search(r"worst slack\s+(-?\d+(?:\.\d+)?)", line, re.I)
        if m_ws:
            wns_ns = float(m_ws.group(1))
        m_slack = re.search(r"^\s*(-?\d+(?:\.\d+)?)\s+slack", line)
        if m_slack:
            wns_ns = float(m_slack.group(1))
        m_mcp = re.search(r"LIBERTY_MCP_PINS_RESOLVED\s+(.+)", line)
        if m_mcp:
            parts = re.findall(r"(\w+)=(\d+)", m_mcp.group(1))
            mcp_resolved = sum(int(v) for _, v in parts if _ != "total")
        m_grp = re.search(r"LIBERTY_MCP_GROUPS_APPLIED\s+(\d+)", line)
        if m_grp:
            mcp_groups = int(m_grp.group(1))
    violated = "slack (VIOLATED)" in out or (wns_ns is not None and wns_ns < 0)
    return {
        "checks_ok": checks_ok,
        "wns_ns": wns_ns,
        "timing_violated": violated,
        "multicycle_pins_resolved": mcp_resolved,
        "multicycle_groups_applied": mcp_groups,
        "multicycle_applied": mcp_groups > 0,
    }


def _run_opensta_liberty() -> dict[str, Any]:
    sta = _sta_path()
    if not sta:
        return {"status": "SKIPPED", "reason": "opensta missing", "opensta_run": False}
    if not _MAPPED.is_file():
        return {"status": "FAIL", "reason": "mapped netlist missing", "opensta_run": False}
    if not _LIBERTY.is_file():
        return {"status": "FAIL", "reason": "liberty missing", "opensta_run": False}

    bash_cmd = (
        f"export PATH='{_msys_path(_CUDD_BIN)}:/mingw64/bin:/usr/bin:'\"$PATH\"; "
        f"export CLIFFORD_STA_LIBERTY='{_msys_path(_LIBERTY)}'; "
        f"export CLIFFORD_STA_NETLIST='{_msys_path(_MAPPED)}'; "
        f"export CLIFFORD_STA_SDC='{_msys_path(_SDC)}'; "
        f"cd '{_msys_path(_REPO)}'; "
        f"'{_msys_path(Path(sta))}' -no_splash -exit '{_msys_path(_TCL)}'"
    )
    try:
        if _MSYS_BASH.is_file():
            proc = subprocess.run(
                [str(_MSYS_BASH), "-lc", bash_cmd],
                cwd=str(_REPO),
                check=True,
                capture_output=True,
                text=True,
                timeout=900,
                env=_mingw_env(),
            )
        else:
            env = _mingw_env()
            env["CLIFFORD_STA_LIBERTY"] = str(_LIBERTY.resolve())
            env["CLIFFORD_STA_NETLIST"] = str(_MAPPED.resolve())
            env["CLIFFORD_STA_SDC"] = str(_SDC.resolve())
            proc = subprocess.run(
                [sta, "-no_splash", "-exit", str(_TCL)],
                cwd=str(_REPO),
                check=True,
                capture_output=True,
                text=True,
                timeout=900,
                env=env,
            )
        out = (proc.stdout or "") + (proc.stderr or "")
        parsed = _parse_timing_report(out)
        ok = parsed["checks_ok"] and parsed.get("multicycle_applied")
        return {
            "status": "PASS" if ok else "FAIL",
            "opensta_run": True,
            "liberty": str(_LIBERTY.relative_to(_REPO)),
            "mapped_netlist": str(_MAPPED.relative_to(_REPO)),
            **parsed,
            "stdout_tail": out[-3000:],
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        tail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            tail = (exc.stdout or exc.stderr or str(exc))[-1200:]
        parsed = _parse_timing_report(tail)
        return {
            "status": "FAIL",
            "opensta_run": True,
            "reason": tail[-400:],
            **parsed,
        }


def run_clifford_alu_opensta_liberty_full() -> dict[str, Any]:
    ys = _run_yosys_mapped()
    sta = _run_opensta_liberty()
    prov = _provenance()

    ys_ok = ys.get("status") == "PASS"
    sta_ok = sta.get("status") == "PASS"
    sta_skip = sta.get("status") == "SKIPPED"

    if ys_ok and sta_ok:
        verdict = "OPENSTA_LIBERTY_FULL_PASS"
    elif ys_ok and sta_skip:
        verdict = "OPENSTA_LIBERTY_FULL_SKIP"
    else:
        verdict = "OPENSTA_LIBERTY_FULL_FAIL"

    result: dict[str, Any] = {
        "verdict": verdict,
        "yosys_mapped": ys,
        "opensta_liberty": sta,
        "provenance": prov,
        "honesty": {
            "scope": "full ALU (phi_fsm + 3 ex_pipes) · Nangate45_typ · NOT signoff",
            "full_alu_mapped": True,
            "structural_smoke_unchanged": True,
            "not_timing_signoff": True,
            "wns_negative_expected": True,
            "gp_synth_en_tied": True,
            "sdc_canon": "fixtures/chip/clifford_alu_macro_cycle_v0.sdc",
            "norm_sta_uses_norm_synth": True,
            "lat_acc_partial_dead_in_mapped": True,
            "triple_pipe_not_case_analyzed": True,
            "geo_prod_slice_separate": "P5.15 manifest unchanged",
        },
    }

    _STA_OUT.mkdir(parents=True, exist_ok=True)
    (_STA_OUT / "clifford_alu_opensta_liberty_full_report_v0.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run_clifford_alu_opensta_liberty_full(), indent=2))
