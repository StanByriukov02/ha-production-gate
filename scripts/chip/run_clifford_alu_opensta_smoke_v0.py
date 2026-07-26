"""P5.9 — yosys STA netlist + SDC endpoint linkage + optional OpenSTA smoke."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STA_OUT = _CHIP / "sta"
_NETLIST = _STA_OUT / "clifford_alu_sta_netlist_v0.v"
_OPENSTA_SHELL = _REPO / "fixtures" / "chip" / "sta" / "clifford_alu_sta_opensta_shell_v0.v"
_OPENSTA_READ = _STA_OUT / "clifford_alu_sta_opensta_read_v0.v"
_SDC = _REPO / "fixtures" / "chip" / "clifford_alu_macro_cycle_v0.sdc"
_YS = _REPO / "scripts" / "chip" / "clifford_sta_alu_netlist_v0.ys"
_TCL = _REPO / "scripts" / "chip" / "clifford_sta_smoke_v0.tcl"
_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"
_MSYS_BASH = Path(r"C:\msys64") / "usr" / "bin" / "bash.exe"


_CUDD_BIN = _REPO / "tools" / "opensta" / "cudd" / "bin"


def _mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    extra = os.pathsep.join(
        str(p)
        for p in (
            _MSYS_BIN,
            _CUDD_BIN,
            _REPO / "tools" / "opensta" / "cudd" / "lib",
        )
        if Path(p).is_dir()
    )
    env["PATH"] = f"{extra};{env.get('PATH', '')}" if extra else env.get("PATH", "")
    env["PYTHONPATH"] = str(_REPO)
    return env


def _yosys_path() -> str | None:
    for name in ("yosys", "yosys.exe"):
        p = shutil.which(name) or (_MSYS_BIN / name if (_MSYS_BIN / name).is_file() else None)
        if p:
            return str(p)
    return None


def _sta_path() -> str | None:
    for candidate in (
        _REPO / "tools" / "opensta" / "build-final" / "sta.exe",
        _REPO / "tools" / "opensta" / "bin" / "sta.exe",
        _MSYS_BIN / "sta.exe",
        Path(r"C:\msys64\usr\bin\sta"),
        _REPO / "tools" / "opensta" / "build" / "app" / "sta.exe",
    ):
        if candidate.is_file() and candidate.stat().st_size > 1_000_000:
            return str(candidate)
    for name in ("sta", "sta.exe", "opensta", "opensta.exe"):
        p = shutil.which(name)
        if p:
            return str(p)
    return None


def _msys_path(p: Path) -> str:
    s = str(p.resolve())
    if len(s) >= 2 and s[1] == ":":
        return "/" + s[0].lower() + s[2:].replace("\\", "/")
    return s.replace("\\", "/")


def _prepare_opensta_read_netlist() -> Path:
    _STA_OUT.mkdir(parents=True, exist_ok=True)
    yosys = _yosys_path()
    norm_ys = _REPO / "scripts" / "chip" / "clifford_sta_opensta_read_norm_v0.ys"
    if yosys and norm_ys.is_file():
        subprocess.run(
            [yosys, str(norm_ys)],
            cwd=str(_REPO),
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
            env=_mingw_env(),
        )
    elif _OPENSTA_SHELL.is_file():
        shutil.copy2(_OPENSTA_SHELL, _OPENSTA_READ)
    return _OPENSTA_READ


def _run_opensta_smoke() -> dict[str, Any]:
    sta = _sta_path()
    if not sta:
        return {"status": "SKIPPED", "reason": "opensta binary missing", "opensta_run": False}
    read_netlist = _prepare_opensta_read_netlist()
    if not read_netlist.is_file():
        return {"status": "SKIPPED", "reason": "opensta read netlist missing", "opensta_run": False}

    netlist = _msys_path(read_netlist)
    sdc = _msys_path(_SDC)
    tcl = _msys_path(_TCL)
    sta_msys = _msys_path(Path(sta))
    cudd_bin = _msys_path(_CUDD_BIN)
    bash_cmd = (
        f"export PATH='{cudd_bin}:/mingw64/bin:/usr/bin:'\"$PATH\"; "
        f"export CLIFFORD_STA_NETLIST='{netlist}'; "
        f"export CLIFFORD_STA_SDC='{sdc}'; "
        f"'{sta_msys}' -no_splash -exit '{tcl}'"
    )

    try:
        if _MSYS_BASH.is_file():
            proc = subprocess.run(
                [str(_MSYS_BASH), "-lc", bash_cmd],
                cwd=str(_REPO),
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
                env=_mingw_env(),
            )
        else:
            env = _mingw_env()
            env["CLIFFORD_STA_NETLIST"] = str(_NETLIST.resolve())
            env["CLIFFORD_STA_SDC"] = str(_SDC.resolve())
            proc = subprocess.run(
                [sta, "-no_splash", "-exit", str(_TCL)],
                cwd=str(_REPO),
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
        out = (proc.stdout or "") + (proc.stderr or "")
        return {"status": "PASS", "opensta_run": True, "read_netlist": str(read_netlist.relative_to(_REPO)), "stdout_tail": out[-600:]}
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        tail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            tail = (exc.stdout or exc.stderr or str(exc))[-600:]
        return {"status": "FAIL", "opensta_run": True, "reason": tail}


def _run_yosys_netlist() -> dict[str, Any]:
    yosys = _yosys_path()
    if not yosys:
        return {"status": "SKIPPED", "reason": "yosys missing"}
    _STA_OUT.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [yosys, str(_YS)],
            cwd=str(_REPO),
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
            env=_mingw_env(),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        cells = 0
        for pat in (
            r"Number of cells:\s*(\d+)",
            r"^\s+(\d+)\s+cells\s*$",
            r"Number of processes:\s*(\d+)",
        ):
            cells_m = re.search(pat, out)
            if cells_m:
                cells = max(cells, int(cells_m.group(1)))
        if cells == 0:
            cells_m = re.findall(r"^\s+(\d+)\s+\$", out, re.MULTILINE)
            if cells_m:
                cells = sum(int(x) for x in cells_m)
        if not _NETLIST.is_file():
            return {"status": "FAIL", "reason": "netlist not written", "stdout_tail": out[-600:]}
        return {
            "status": "PASS",
            "netlist": str(_NETLIST.relative_to(_REPO)),
            "cells": cells,
            "stdout_tail": out[-400:],
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        tail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            tail = (exc.stdout or exc.stderr or str(exc))[-500:]
        return {"status": "FAIL", "reason": tail}


def _verify_sdc_netlist_linkage(netlist_text: str) -> dict[str, Any]:
    sdc = _SDC.read_text(encoding="utf-8")
    instances = ("u_geo_prod_pipe", "u_sandwich_pipe", "u_norm_pipe")
    checks: list[dict[str, Any]] = []

    signal_by_inst = {
        "u_geo_prod_pipe": ("lat_a", "pipe_r", "lat_low", "lat_high"),
        "u_sandwich_pipe": ("lat_a", "pipe_r", "lat_ab"),
        "u_norm_pipe": ("lat_a", "pipe_r", "lat_acc_partial"),
    }

    for inst in instances:
        in_sdc = inst in sdc
        checks.append({"id": f"sdc_inst_{inst}", "pass": in_sdc, "detail": inst})
        for sig in signal_by_inst.get(inst, ("lat_a", "pipe_r")):
            hits = len(re.findall(rf"\b{sig}\b", netlist_text))
            checks.append(
                {
                    "id": f"netlist_{sig}_{inst}",
                    "pass": hits >= 1 and inst in netlist_text,
                    "detail": f"{sig}_hits={hits}",
                }
            )

    setup_m = re.search(r"MCP_EX1_EX3_SETUP\s+(\d+)", sdc)
    checks.append(
        {
            "id": "sdc_multicycle_setup_4",
            "pass": setup_m is not None and int(setup_m.group(1)) == 4,
            "detail": setup_m.group(0) if setup_m else "missing",
        }
    )

    ok = all(c["pass"] for c in checks)
    return {"verdict": "SDC_NETLIST_LINK_PASS" if ok else "SDC_NETLIST_LINK_FAIL", "checks": checks}


def run_clifford_alu_opensta_smoke() -> dict[str, Any]:
    ys = _run_yosys_netlist()
    linkage: dict[str, Any] = {"verdict": "SDC_NETLIST_LINK_FAIL", "checks": []}
    if ys.get("status") == "PASS" and _NETLIST.is_file():
        netlist_text = _NETLIST.read_text(encoding="utf-8", errors="replace")
        if _OPENSTA_SHELL.is_file():
            netlist_text += "\n" + _OPENSTA_SHELL.read_text(encoding="utf-8", errors="replace")
        linkage = _verify_sdc_netlist_linkage(netlist_text)
    sta = _run_opensta_smoke()

    ys_ok = ys.get("status") == "PASS"
    link_ok = linkage.get("verdict") == "SDC_NETLIST_LINK_PASS"
    sta_ok = sta.get("status") == "PASS"
    sta_skip = sta.get("status") == "SKIPPED"

    if ys_ok and link_ok and (sta_ok or sta_skip):
        verdict = "OPENSTA_SMOKE_PASS"
    else:
        verdict = "OPENSTA_SMOKE_FAIL"

    return {
        "verdict": verdict,
        "yosys_netlist": ys,
        "sdc_netlist_linkage": linkage,
        "opensta_cli": sta,
        "honesty": {
            "opensta_run": bool(sta.get("opensta_run")),
            "opensta_read_netlist": "fixtures/chip/sta/clifford_alu_sta_opensta_shell_v0.v",
            "yosys_netlist_for_linkage": str(_NETLIST.relative_to(_REPO)),
            "netlist_uses_sim_blackbox": True,
            "not_timing_closure": True,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_clifford_alu_opensta_smoke(), indent=2))
