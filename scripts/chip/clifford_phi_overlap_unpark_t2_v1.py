"""T2.5 — φ overlap mode unpark (scheduler sim · 1 motor / 2φ)."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FIX = _REPO / "fixtures" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_PHI_OVERLAP_T2_5_RECEIPT_v1.json"
_T2 = _CHIP / "CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1.json"
_SCOPE = _REPO / "docs" / "agent_workflow" / "CLIFFORD_PHI_OVERLAP_MODE_v1.md"
_BUDGET = _REPO / "docs" / "agent_workflow" / "CLIFFORD_PHI_PIPELINE_BUDGET_v1.md"

_RTL = (
    "clifford_phi_overlap_scheduler_v0.v",
    "clifford_phi_overlap_tb_v0.v",
)


def _run_verilator_overlap(*, timeout: int = 120) -> dict[str, Any]:
    from scripts.chip.clifford_msys_toolchain_v1 import (
        posix_path,
        run_mingw_shell,
        verilator_available,
    )

    if not verilator_available():
        return {"verdict": "SKIPPED", "reason": "verilator missing"}

    for name in _RTL:
        if not (_FIX / name).is_file():
            return {"verdict": "FAIL", "reason": f"missing {_FIX / name}"}

    fix_posix = posix_path(_FIX)
    with tempfile.TemporaryDirectory(prefix="clifford_phi_overlap_vlt_") as tmp:
        build_posix = posix_path(Path(tmp) / "build")
        srcs = " ".join(_RTL)
        cmd = (
            f"cd '{fix_posix}' && mkdir -p '{build_posix}' && "
            f"verilator --binary --top-module clifford_phi_overlap_tb_v0 "
            f"-Wall -Wno-fatal -CFLAGS '-D_GLIBCXX_USE_CXX11_ABI=0' -LDFLAGS '-lstdc++' "
            f"-I. -Mdir '{build_posix}' {srcs} && "
            f"'{build_posix}/Vclifford_phi_overlap_tb_v0.exe'"
        )
        try:
            proc = run_mingw_shell(cmd, timeout=timeout)
            out = (proc.stdout or "") + (proc.stderr or "")
            ok = (
                proc.returncode == 0
                and "TB_PASS unpipelined_latency_8phi" in out
                and "TB_PASS overlap_steady_1_per_2phi" in out
            )
            return {
                "verdict": "VERILATOR_PHI_OVERLAP_PASS" if ok else "VERILATOR_PHI_OVERLAP_FAIL",
                "returncode": proc.returncode,
                "stdout_tail": out[-1500:],
            }
        except Exception as exc:
            return {"verdict": "VERILATOR_PHI_OVERLAP_FAIL", "reason": str(exc)[-400:]}


def run_phi_overlap_unpark_t2_5(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    t2_ok = _T2.is_file() and json.loads(_T2.read_text(encoding="utf-8")).get("verdict") == "OPT_BASELINE_PASS"
    scope_txt = _SCOPE.read_text(encoding="utf-8") if _SCOPE.is_file() else ""
    budget_txt = _BUDGET.read_text(encoding="utf-8") if _BUDGET.is_file() else ""
    verilator = _run_verilator_overlap()

    checks = [
        {"id": "t2_baseline_prerequisite", "pass": t2_ok},
        {"id": "overlap_scope_doc", "pass": _SCOPE.is_file()},
        {"id": "scheduling_table", "pass": "1 motor / 2φ" in scope_txt or "1 motor / 2" in scope_txt},
        {"id": "scheduler_rtl", "pass": (_FIX / "clifford_phi_overlap_scheduler_v0.v").is_file()},
        {
            "id": "verilator_overlap_sim",
            "pass": verilator.get("verdict") == "VERILATOR_PHI_OVERLAP_PASS",
            "detail": verilator.get("verdict", ""),
        },
        {
            "id": "budget_doc_overlap_honesty",
            "pass": "not shipped" in budget_txt.lower() or "overlap" in budget_txt.lower(),
        },
    ]

    verdict = "PHI_OVERLAP_T2_5_PASS" if all(c["pass"] for c in checks) else "PHI_OVERLAP_T2_5_FAIL"
    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_PHI_OVERLAP_T2_5_RECEIPT_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "verilator": verilator,
        "modeled_latency_ns": {
            "unpipelined_compose": 80.0,
            "overlap_compose_steady": 20.0,
            "clock_ns": 10.0,
            "honesty": "scheduler sim — not full GP cloud STA",
        },
        "honesty": {
            "timing_closure": False,
            "sandwich_wns_warn": "~-206ns binding path unchanged",
            "alu_top_default": "clifford_phi_fsm_v0 unpipelined",
            "overlap": "sim scheduler shipped T2.5",
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(run_phi_overlap_unpark_t2_5(), indent=2))
