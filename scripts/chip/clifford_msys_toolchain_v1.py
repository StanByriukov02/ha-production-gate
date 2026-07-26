"""Local MSYS64 iron toolchain — yosys · verilator · iverilog (T4 iron-first)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_MSYS_ROOT = Path(r"C:\msys64")
_MSYS_MINGW = _MSYS_ROOT / "mingw64" / "bin"
_MSYS_SHELL = _MSYS_ROOT / "msys2_shell.cmd"


def msys_available() -> bool:
    return _MSYS_SHELL.is_file() and (_MSYS_MINGW / "yosys.exe").is_file()


def mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    prefix = f"{_MSYS_MINGW};{_MSYS_ROOT / 'usr' / 'bin'}"
    env["PATH"] = f"{prefix};{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(_REPO)
    return env


def posix_path(path: Path) -> str:
    s = str(path.resolve())
    if len(s) >= 2 and s[1] == ":":
        return "/" + s[0].lower() + s[2:].replace("\\", "/")
    return s.replace("\\", "/")


def run_mingw_shell(command: str, *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_MSYS_SHELL), "-mingw64", "-defterm", "-no-start", "-c", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=mingw_env(),
    )


def yosys_path() -> str | None:
    for name in ("yosys", "yosys.exe"):
        p = shutil.which(name) or (_MSYS_MINGW / name if (_MSYS_MINGW / name).is_file() else None)
        if p:
            return str(p)
    return None


def verilator_available() -> bool:
    return _MSYS_SHELL.is_file() and (
        (_MSYS_MINGW / "verilator_bin.exe").is_file() or bool(shutil.which("verilator"))
    )


def parse_yosys_stat(out: str) -> dict[str, int | None]:
    cells: int | None = None
    cells_m = re.search(r"Number of cells:\s+(\d+)", out)
    if cells_m:
        cells = int(cells_m.group(1))
    else:
        cells_m2 = re.search(r"^\s+(\d+)\s+cells\s*$", out, re.MULTILINE)
        if cells_m2:
            cells = int(cells_m2.group(1))
    mul_m = re.search(r"^\s+(\d+)\s+\$mul\s*$", out, re.MULTILINE)
    if not mul_m:
        mul_m = re.search(r"\$mul\s+(\d+)", out)
    return {
        "cells": cells,
        "mul_cells": int(mul_m.group(1)) if mul_m else None,
    }


def run_yosys_stat(verilog: Path, *, cwd: Path | None = None) -> dict[str, Any]:
    """Local MSYS yosys stat on a single verilog file."""
    yp = yosys_path()
    if not yp:
        return {"status": "SKIPPED", "reason": "yosys missing", "host": "local"}
    cwd = cwd or _REPO
    try:
        vpath = verilog.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        vpath = str(verilog)
    cmd = [yp, "-p", f"read_verilog -sv -I fixtures/chip {vpath}; stat"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=300,
            env=mingw_env(),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        stats = parse_yosys_stat(out)
        ok = proc.returncode == 0 and (stats["cells"] or stats["mul_cells"])
        return {
            "status": "PASS" if ok else "FAIL",
            "host": "local",
            "returncode": proc.returncode,
            **stats,
            "tail": out[-400:],
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"status": "FAIL", "host": "local", "reason": str(exc)[-300:]}


def run_yosys_script(ys: Path, *, cwd: Path | None = None) -> dict[str, Any]:
    yp = yosys_path()
    if not yp:
        return {"status": "SKIPPED", "reason": "yosys missing"}
    cwd = cwd or _REPO
    try:
        proc = subprocess.run(
            [yp, str(ys)],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=600,
            env=mingw_env(),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        stats = parse_yosys_stat(out)
        return {
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "script": str(ys.resolve().relative_to(_REPO.resolve())).replace("\\", "/"),
            "returncode": proc.returncode,
            **stats,
            "tail": out[-500:],
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"status": "FAIL", "reason": str(exc)[-300:]}
