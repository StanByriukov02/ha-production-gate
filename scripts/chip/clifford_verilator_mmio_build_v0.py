"""Build Verilator MMIO session binary for Rust clifford_device H3."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_FIX = _REPO / "fixtures" / "chip"
_BUILD = _REPO / "results" / "platform_bpass" / "chip" / "verilator" / "clifford_mmio_session"
_EXE = _BUILD / "Vclifford_alu_mmio_v0.exe"
_MSYS_ROOT = Path(r"C:\msys64")
_MSYS_MINGW = _MSYS_ROOT / "mingw64" / "bin"
_MSYS_SHELL = _MSYS_ROOT / "msys2_shell.cmd"


def _posix(path: Path) -> str:
    s = str(path.resolve())
    if len(s) >= 2 and s[1] == ":":
        return "/" + s[0].lower() + s[2:].replace("\\", "/")
    return s.replace("\\", "/")


def _mmio_rtl_srcs() -> tuple[str, ...]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))
    from scripts.chip.clifford_alu_tb_hygiene_v1 import _ALU_RTL

    return tuple(s for s in _ALU_RTL if s != "clifford_alu_tb_v0.v") + ("clifford_alu_mmio_v0.v",)


def verilator_mmio_exe(*, force_rebuild: bool = False) -> Path | None:
    if _EXE.is_file() and not force_rebuild:
        return _EXE
    if not _MSYS_SHELL.is_file():
        return None
    _BUILD.mkdir(parents=True, exist_ok=True)
    fix_posix = _posix(_FIX)
    build_posix = _posix(_BUILD)
    cpp_posix = _posix(_FIX / "clifford_mmio_session.cpp")
    srcs = " ".join(_mmio_rtl_srcs())
    cmd = (
        f"cd '{fix_posix}' && "
        f"verilator --binary --top-module clifford_alu_mmio_v0 -Wall -Wno-fatal "
        f"-CFLAGS '-std=c++17 -D_GLIBCXX_USE_CXX11_ABI=0' -LDFLAGS '-lstdc++' "
        f"-I. --exe '{cpp_posix}' -Mdir '{build_posix}' {srcs}"
    )
    proc = subprocess.run(
        [str(_MSYS_SHELL), "-mingw64", "-defterm", "-no-start", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if proc.returncode != 0 or not _EXE.is_file():
        return None
    return _EXE


def build_status() -> dict[str, Any]:
    exe = verilator_mmio_exe()
    return {
        "exe": str(exe.relative_to(_REPO)).replace("\\", "/") if exe else None,
        "built": exe is not None,
        "rtl_src_count": len(_mmio_rtl_srcs()),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(build_status(), indent=2))
