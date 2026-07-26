"""Verilator iron smoke — CGA32 motor512 geo_prod (phase-2)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_FIX = _REPO / "fixtures" / "chip"

_SOURCES = (
    "clifford_alu_v0_pkg.vh",
    "clifford_bf16_ops_v0.vh",
    "clifford_cga_motor_bf16_ops_v0.vh",
    "clifford_geo_prod_cga32_v0.v",
    "clifford_geo_prod_cga32_tb_v0.v",
)


def run_cga32_verilator_smoke(*, timeout: int = 900) -> dict[str, Any]:
    from scripts.chip.clifford_msys_toolchain_v1 import (
        posix_path,
        run_mingw_shell,
        verilator_available,
    )

    if not verilator_available():
        return {"verdict": "SKIPPED", "reason": "verilator missing"}

    for name in _SOURCES:
        if not (_FIX / name).is_file():
            return {"verdict": "FAIL", "reason": f"missing {_FIX / name}"}

    fix_posix = posix_path(_FIX)
    with tempfile.TemporaryDirectory(prefix="clifford_cga32_vlt_") as tmp:
        build_posix = posix_path(Path(tmp) / "build")
        srcs = " ".join(_SOURCES)
        cmd = (
            f"cd '{fix_posix}' && mkdir -p '{build_posix}' && "
            f"verilator --binary --top-module clifford_geo_prod_cga32_tb_v0 "
            f"-Wall -Wno-fatal -CFLAGS '-D_GLIBCXX_USE_CXX11_ABI=0' -LDFLAGS '-lstdc++' "
            f"-I. -Mdir '{build_posix}' {srcs} && "
            f"'{build_posix}/Vclifford_geo_prod_cga32_tb_v0.exe'"
        )
        try:
            proc = run_mingw_shell(cmd, timeout=timeout)
            out = (proc.stdout or "") + (proc.stderr or "")
            ok = proc.returncode == 0 and "TB_PASS cga32_motor_smoke" in out
            return {
                "verdict": "VERILATOR_CGA32_PASS" if ok else "VERILATOR_CGA32_FAIL",
                "returncode": proc.returncode,
                "stdout_tail": out[-2000:],
            }
        except Exception as exc:
            return {"verdict": "VERILATOR_CGA32_FAIL", "reason": str(exc)[-400:]}


if __name__ == "__main__":
    import json

    print(json.dumps(run_cga32_verilator_smoke(), indent=2))
