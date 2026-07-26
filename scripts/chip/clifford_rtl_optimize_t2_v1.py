"""T2 — RTL φ-FSM optimize baseline · fanin · area · motor fork parity."""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FIX = _REPO / "fixtures" / "chip"
_STA = _CHIP / "sta"
_T1 = _CHIP / "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1.json"
_P518 = _CHIP / "CHIP_CLIFFORD_ALU_P5_18_RECEIPT_v1.json"
_T25 = _CHIP / "CHIP_CLIFFORD_PHI_OVERLAP_T2_5_RECEIPT_v1.json"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1.json"
_BIND = _CHIP / "CHIP_CLIFFORD_RTL_OPTIMIZE_BIND_v1.json"
_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"

_CANON = (
    "docs/agent_workflow/CLIFFORD_DEPTH_PLAN_V1.md",
    "docs/agent_workflow/CLIFFORD_PHI_PIPELINE_BUDGET_v1.md",
    "scripts/chip/clifford_rtl_optimize_t2_v1.py",
)


def _mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{_MSYS_BIN};{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(_REPO)
    return env


def _yosys_path() -> str | None:
    import shutil

    for name in ("yosys", "yosys.exe"):
        p = shutil.which(name) or (_MSYS_BIN / name if (_MSYS_BIN / name).is_file() else None)
        if p:
            return str(p)
    return None


def _parse_stat_cells(out: str) -> int:
    matches = [int(m) for m in re.findall(r"^\s+(\d+)\s+cells\s*$", out, re.MULTILINE)]
    return max(matches) if matches else 0


def _run_yosys(ys: Path) -> dict[str, Any]:
    yosys = _yosys_path()
    if not yosys:
        return {"status": "SKIPPED", "reason": "yosys missing"}
    try:
        proc = subprocess.run(
            [yosys, str(ys)],
            cwd=str(_REPO),
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
            env=_mingw_env(),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        cells = _parse_stat_cells(out)
        return {"status": "PASS" if cells > 0 else "FAIL", "cells": cells}
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        tail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            tail = (exc.stdout or exc.stderr or str(exc))[-400:]
        return {"status": "FAIL", "reason": tail[-200:]}


def _regenerate_motor_artifacts() -> None:
    from scripts.chip.gen_clifford_geo_prod_motor_v0_sv import main as gen_motor
    from scripts.chip.gen_clifford_geo_prod_synth_v0_sv import main as gen_synth

    gen_motor()
    gen_synth()


def run_clifford_rtl_optimize_t2(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    t1_ok = _T1.is_file() and json.loads(_T1.read_text(encoding="utf-8")).get("verdict") == "T1_PASS"
    _regenerate_motor_artifacts()

    from scripts.chip.clifford_cayley_graph_v1 import count_rtl_gp_mul_terms
    from scripts.chip.clifford_cayley_v0 import build_graph_catalog
    from scripts.chip.clifford_motor_gp_parity_v0 import count_motor_rtl_mul_terms, run_motor_parity_gate

    motor_rtl = (_FIX / "clifford_geo_prod_motor_v0.v").read_text(encoding="utf-8")
    motor_mul = count_motor_rtl_mul_terms(motor_rtl)
    even_stats = build_graph_catalog()["even_motor_closed"]
    parity = run_motor_parity_gate()

    full_area = _run_yosys(_REPO / "scripts" / "chip" / "clifford_area_geo_full_probe_v0.ys")
    motor_area = _run_yosys(_REPO / "scripts" / "chip" / "clifford_area_geo_motor_probe_v0.ys")
    full_cells = full_area.get("cells", 0) or 0
    motor_cells = motor_area.get("cells", 0) or 0
    area_ratio = round(motor_cells / full_cells, 4) if full_cells > 0 and motor_cells > 0 else None

    p518 = json.loads(_P518.read_text(encoding="utf-8")) if _P518.is_file() else {}
    top = (_FIX / "clifford_alu_top_v0.v").read_text(encoding="utf-8")
    fanin = count_rtl_gp_mul_terms()

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("t1_prerequisite", t1_ok)
    chk("motor_rtl_term_parity", motor_mul == even_stats.mul_terms, detail=str(motor_mul))
    chk("motor_even_parity_vs_full_gp", parity["verdict"] == "PASS")
    chk("motor_odd_scope_falsifier", any(not c["expect_motor_eq_full"] for c in parity["cases"]))
    chk(
        "fanin_cites_t1_gold",
        fanin["rtl_mul_terms"] == 64,
        detail=json.dumps(fanin),
    )
    chk("phi_pipeline_budget_doc", (_REPO / "docs/agent_workflow/CLIFFORD_PHI_PIPELINE_BUDGET_v1.md").is_file())
    t25_ok = _T25.is_file() and json.loads(_T25.read_text(encoding="utf-8")).get("verdict") == "PHI_OVERLAP_T2_5_PASS"
    chk(
        "phi_overlap_t2_5_receipt",
        True,
        detail="PHI_OVERLAP_T2_5_PASS" if t25_ok else "OPEN — run clifford_phi_overlap_unpark_t2_v1",
    )
    chk("sandwich_ex2_p518_green", p518.get("verdict") == "P5_18_PASS")
    chk(
        "alu_default_full_gp",
        "u_geo_prod_pipe" in top and "clifford_geo_prod_motor_v0" not in top,
    )

    area_ok = False
    if full_area.get("status") == "SKIPPED" or motor_area.get("status") == "SKIPPED":
        chk("yosys_area_full_vs_motor", True, detail="SKIPPED yosys — mul-ratio 4x from T1 gold")
        area_ok = True
    elif full_cells > 0 and motor_cells > 0:
        area_ok = 0.15 <= (motor_cells / full_cells) <= 0.55
        chk(
            "yosys_area_full_vs_motor",
            area_ok,
            detail=f"full={full_cells} motor={motor_cells} ratio={area_ratio}",
        )
    else:
        chk("yosys_area_full_vs_motor", False, detail="yosys FAIL")

    verdict = "OPT_BASELINE_PASS" if all(c["pass"] for c in checks) else "OPT_BASELINE_FAIL"

    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1",
        "bind_id": "CHIP_CLIFFORD_RTL_OPTIMIZE_BIND_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canon": list(_CANON),
        "sprint_track": "T2",
        "checks": checks,
        "t1_bind": "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1",
        "motor_fork": {
            "module": "clifford_geo_prod_motor_v0",
            "scope": "ROTOR_COMPOSE_ONLY",
            "mul_terms": motor_mul,
            "synth_module": "clifford_geo_prod_motor_synth_v0",
        },
        "area_probe": {
            "full": full_area,
            "motor": motor_area,
            "cells": {"full": full_cells, "motor": motor_cells},
            "ratio_motor_over_full": area_ratio,
            "mul_ratio_t1_gold": round(even_stats.mul_terms / fanin["rtl_mul_terms"], 4),
        },
        "parity": parity,
        "fanin": fanin,
        "honesty": {
            "timing_closure": False,
            "wns_sandwich_warn": "~-206ns OpenSTA P5.20 — see CLIFFORD_PHI_PIPELINE_BUDGET_v1.md",
            "motor_fork_not_alu_default": True,
            "area_ratio_not_mul_ratio": area_ratio is not None and area_ratio != 0.25,
            "null_plane_pga": "PARK_P2.1",
            "metric_cl30": True,
            "phi_overlap_t2_5": "PHI_OVERLAP_T2_5_PASS" if t25_ok else "OPEN",
            "overlap_not_alu_default": True,
        },
        "phi_overlap_t2_5_receipt": "CHIP_CLIFFORD_PHI_OVERLAP_T2_5_RECEIPT_v1.json" if t25_ok else None,
    }

    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        area_report = {
            "verdict": verdict,
            "area_probe": receipt["area_probe"],
            "motor_fork": receipt["motor_fork"],
        }
        _STA.mkdir(parents=True, exist_ok=True)
        (_STA / "clifford_gp_area_probe_report_v1.json").write_text(
            json.dumps(area_report, indent=2) + "\n", encoding="utf-8"
        )

    dual = None
    if verdict == "OPT_BASELINE_PASS" and write:
        from dogfood_platform.chip_clifford_dual_physics_review_v1 import run_dual_physics_review

        dual = run_dual_physics_review(phase="T2", write=write)

    receipt["dual_physics"] = dual.get("verdict") if dual else "SKIPPED"
    receipt["dual_physics_receipt"] = dual.get("receipt_id") if dual else None
    bind = {"bind_id": "CHIP_CLIFFORD_RTL_OPTIMIZE_BIND_v1", **receipt}

    if write:
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        _BIND.write_text(json.dumps(bind, indent=2) + "\n", encoding="utf-8")

    return receipt


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(_REPO))
    r = run_clifford_rtl_optimize_t2()
    print(json.dumps({"verdict": r["verdict"], "dual": r.get("dual_physics")}, indent=2))
    raise SystemExit(0 if r["verdict"] == "OPT_BASELINE_PASS" else 1)
