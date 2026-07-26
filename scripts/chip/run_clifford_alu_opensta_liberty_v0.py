"""P5.15 — OpenSTA liberty timing hop (Nangate45 mapped geo_prod slice)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STA_OUT = _CHIP / "sta"
_LIBERTY = _REPO / "tools" / "opensta" / "src" / "test" / "nangate45" / "Nangate45_typ.lib"
_MAPPED = _STA_OUT / "clifford_sta_geo_prod_slice_mapped_v0.v"
_YS = _REPO / "scripts" / "chip" / "clifford_sta_geo_prod_slice_mapped_v0.ys"
_SDC = _REPO / "fixtures" / "chip" / "sta" / "clifford_sta_geo_prod_slice_v0.sdc"
_TCL = _REPO / "scripts" / "chip" / "clifford_sta_liberty_geo_prod_slice_v0.tcl"
_MANIFEST = _REPO / "fixtures" / "chip" / "sta" / "clifford_alu_sta_liberty_manifest_v1.json"

_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"
_MSYS_BASH = Path(r"C:\msys64") / "usr" / "bin" / "bash.exe"
_CUDD_BIN = _REPO / "tools" / "opensta" / "cudd" / "bin"


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


def _run_yosys_mapped() -> dict[str, Any]:
    yosys = _yosys_path()
    if not yosys:
        return {"status": "SKIPPED", "reason": "yosys missing"}
    if not _LIBERTY.is_file():
        return {"status": "FAIL", "reason": "Nangate45_typ.lib missing"}
    _STA_OUT.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [yosys, str(_YS)],
            cwd=str(_REPO),
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
            env=_mingw_env(),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if not _MAPPED.is_file():
            return {"status": "FAIL", "reason": "mapped netlist not written"}
        text = _MAPPED.read_text(encoding="utf-8", errors="replace")
        cells = 0
        for pat in (
            r"Number of cells:\s*(\d+)",
            r"^\s+(\d+)\s+cells\s*$",
        ):
            m = re.search(pat, out, re.MULTILINE)
            if m:
                cells = max(cells, int(m.group(1)))
        if cells == 0:
            cells = len(re.findall(r"\bDFF_X1\b", text))
        has_stdcell = "DFF_X1" in text and "INV_X1" in text
        return {
            "status": "PASS" if has_stdcell else "FAIL",
            "netlist": str(_MAPPED.relative_to(_REPO)),
            "cells": cells,
            "stdcell_mapped": has_stdcell,
            "stdout_tail": out[-400:],
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        tail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            tail = (exc.stdout or exc.stderr or str(exc))[-500:]
        return {"status": "FAIL", "reason": tail}


def _parse_timing_report(out: str) -> dict[str, Any]:
    checks_ok = "LIBERTY_TIMING_CHECKS_OK" in out
    wns_ns: float | None = None
    tns_ns: float | None = None
    for line in out.splitlines():
        m_ws = re.search(r"worst slack\s+(-?\d+(?:\.\d+)?)", line, re.I)
        if m_ws:
            wns_ns = float(m_ws.group(1))
        m_slack = re.search(r"^\s*(-?\d+(?:\.\d+)?)\s+slack", line)
        if m_slack:
            wns_ns = float(m_slack.group(1))
    violated = "slack (VIOLATED)" in out or (wns_ns is not None and wns_ns < 0)
    mcp_warn = out.count("Warning 363:") + out.count("Warning 471:")
    return {
        "checks_ok": checks_ok,
        "wns_ns": wns_ns,
        "tns_ns": tns_ns,
        "timing_violated": violated,
        "sdc_warnings": mcp_warn,
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
                timeout=300,
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
                timeout=300,
                env=env,
            )
        out = (proc.stdout or "") + (proc.stderr or "")
        parsed = _parse_timing_report(out)
        ok = parsed["checks_ok"]
        return {
            "status": "PASS" if ok else "FAIL",
            "opensta_run": True,
            "liberty": str(_LIBERTY.relative_to(_REPO)),
            "mapped_netlist": str(_MAPPED.relative_to(_REPO)),
            **parsed,
            "stdout_tail": out[-1200:],
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        tail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            tail = (exc.stdout or exc.stderr or str(exc))[-800:]
        parsed = _parse_timing_report(tail)
        return {
            "status": "FAIL",
            "opensta_run": True,
            "reason": tail[-400:],
            **parsed,
        }


def run_clifford_alu_opensta_liberty() -> dict[str, Any]:
    ys = _run_yosys_mapped()
    sta = _run_opensta_liberty()

    ys_ok = ys.get("status") == "PASS"
    sta_ok = sta.get("status") == "PASS"
    sta_skip = sta.get("status") == "SKIPPED"

    if ys_ok and sta_ok:
        verdict = "OPENSTA_LIBERTY_PASS"
    elif ys_ok and sta_skip:
        verdict = "OPENSTA_LIBERTY_SKIP"
    else:
        verdict = "OPENSTA_LIBERTY_FAIL"

    result: dict[str, Any] = {
        "verdict": verdict,
        "yosys_mapped": ys,
        "opensta_liberty": sta,
        "honesty": {
            "scope": "geo_prod ex_pipe slice · Nangate45_typ reference lib · NOT signoff",
            "structural_smoke_unchanged": True,
            "not_timing_signoff": True,
            "wns_negative_expected": True,
            "full_alu_mapped": False,
            "multicycle_sdc": "net-pin based on mapped netlist — partial vs RTL contract",
        },
    }

    _STA_OUT.mkdir(parents=True, exist_ok=True)
    (_STA_OUT / "clifford_alu_opensta_liberty_report_v0.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run_clifford_alu_opensta_liberty(), indent=2))
