"""Verilator iron smoke — hand geo_prod oracle + circt emit compiles (T4)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_FIX = _REPO / "fixtures" / "chip"

_TB = "clifford_geo_prod_circt_emit_tb_v0.v"
_SOURCES = (
    "clifford_alu_v0_pkg.vh",
    "clifford_bf16_ops_v0.vh",
    "clifford_geo_prod_v0.v",
    "clifford_geo_prod_circt_emit_v0.sv",
    _TB,
)


def run_verilator_emit_smoke(*, timeout: int = 600) -> dict[str, Any]:
    from scripts.chip.clifford_msys_toolchain_v1 import (
        posix_path,
        run_mingw_shell,
        verilator_available,
    )

    if not verilator_available():
        return {"verdict": "SKIPPED", "reason": "verilator missing", "backend": "verilator"}

    for name in _SOURCES:
        if not (_FIX / name).is_file():
            return {"verdict": "FAIL", "reason": f"missing {_FIX / name}"}

    fix_posix = posix_path(_FIX)
    with tempfile.TemporaryDirectory(prefix="clifford_emit_vlt_") as tmp:
        build_posix = posix_path(Path(tmp) / "build")
        srcs = " ".join(_SOURCES)
        cmd = (
            f"cd '{fix_posix}' && mkdir -p '{build_posix}' && "
            f"verilator --binary --top-module clifford_geo_prod_circt_emit_tb_v0 "
            f"-Wall -Wno-fatal -CFLAGS '-D_GLIBCXX_USE_CXX11_ABI=0' -LDFLAGS '-lstdc++' "
            f"-I. -Mdir '{build_posix}' {srcs} && "
            f"'{build_posix}/Vclifford_geo_prod_circt_emit_tb_v0.exe'"
        )
        try:
            proc = run_mingw_shell(cmd, timeout=timeout)
            out = (proc.stdout or "") + (proc.stderr or "")
            ok = proc.returncode == 0 and "TB_PASS emit_smoke" in out and "TB_FAIL" not in out
            return {
                "verdict": "VERILATOR_SMOKE_PASS" if ok else "VERILATOR_SMOKE_FAIL",
                "backend": "verilator",
                "returncode": proc.returncode,
                "cases": out.count("TB_PASS p"),
                "stdout_tail": out[-1500:],
                "honesty": {
                    "hand_bf16_oracle": True,
                    "emit_functional_match": False,
                    "emit_compiles_and_runs": ok,
                },
            }
        except Exception as exc:
            return {"verdict": "VERILATOR_SMOKE_FAIL", "reason": str(exc)[-400:]}
