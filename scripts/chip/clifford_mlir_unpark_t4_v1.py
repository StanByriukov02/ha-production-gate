"""T4 — MLIR/CIRCT UNPARK receipt runner."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_MLIR = _REPO / "mlir" / "clifford"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_MLIR_UNPARK_T4_RECEIPT_v1.json"
_BIND = _CHIP / "CHIP_CLIFFORD_MLIR_UNPARK_T4_BIND_v1.json"
_T1 = _CHIP / "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1.json"
_T2 = _CHIP / "CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1.json"
_T3 = _CHIP / "CHIP_CLIFFORD_MOTOR_LERP_STUDY_RECEIPT_v1.json"
_FIX = _REPO / "fixtures" / "chip"

_CANON = (
    "docs/agent_workflow/CLIFFORD_DEPTH_PLAN_V1.md",
    "mlir/clifford/README.md",
    "scripts/chip/clifford_mlir_unpark_t4_v1.py",
)


def _circt_on_path() -> bool:
    return shutil.which("circt-opt") is not None or shutil.which("circt-opt.exe") is not None


def run_clifford_mlir_unpark_t4(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    t1_ok = _T1.is_file() and json.loads(_T1.read_text(encoding="utf-8")).get("verdict") == "T1_PASS"
    t2_ok = _T2.is_file() and json.loads(_T2.read_text(encoding="utf-8")).get("verdict") == "OPT_BASELINE_PASS"
    t3_ok = _T3.is_file() and json.loads(_T3.read_text(encoding="utf-8")).get("verdict") == "T3_PASS"

    from scripts.chip.clifford_circt_emit_v1 import run_cayley_regen_diff, run_circt_emit, run_netlist_diff
    from scripts.chip.clifford_circt_structural_diff_v1 import run_circt_structural_diff
    from scripts.chip.clifford_circt_verilator_smoke_v1 import run_verilator_emit_smoke
    from scripts.chip.clifford_mlir_legalize_v1 import run_gp_legalize_gate
    from scripts.chip.clifford_mlir_sandwich_norm_iron_v1 import run_clifford_mlir_sandwich_norm_iron

    legalize = run_gp_legalize_gate()
    structural = run_circt_structural_diff()
    regen = run_cayley_regen_diff()
    emit = run_circt_emit(write=write)
    netlist = run_netlist_diff(write=write)
    verilator = run_verilator_emit_smoke()
    sandwich_iron = run_clifford_mlir_sandwich_norm_iron(write=write)
    pin_path = _REPO / "toolchain" / "CIRCT_PIN_v1.json"

    dialect_td = _MLIR / "dialect" / "CliffordOps.td"
    mlir_examples = list((_MLIR / "examples").glob("*.mlir"))

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("unpark_gate_t1", t1_ok)
    chk("unpark_gate_t2", t2_ok)
    chk("unpark_gate_t3_carry", t3_ok, detail="motion law locked RUNTIME_ONLY")
    chk("gp_legalize_bitmatch", legalize["verdict"] == "LEGALIZE_PASS", detail=str(legalize["n_pass"]))
    chk("mlir_tree_present", _MLIR.is_dir() and dialect_td.is_file())
    chk("dialect_stub_t4_1", dialect_td.is_file() and "CliffordGpOp" in dialect_td.read_text(encoding="utf-8"))
    chk("mlir_examples", len(mlir_examples) >= 2, detail=str(len(mlir_examples)))
    chk("circt_structural_diff_t4_2", structural["verdict"] == "STRUCTURAL_DIFF_PASS")
    chk("compile_rail_doc", (_MLIR / "README.md").is_file())
    chk("toolchain_pin_vps", pin_path.is_file())
    chk("cayley_regen_identical", regen["verdict"] == "REGEN_IDENTICAL")
    chk("circt_emit_vps", emit["verdict"] == "EMIT_PASS", detail=emit.get("emit_path", ""))
    chk("netlist_diff_yosys", netlist["verdict"] == "NETLIST_DIFF_PASS")
    chk(
        "yosys_local_msys",
        netlist.get("yosys_host") == "local_msys" or netlist.get("circt_emit", {}).get("yosys", {}).get("host")
        == "local_msys",
        detail=netlist.get("yosys_host", ""),
    )
    vlt_ok = verilator["verdict"] in ("VERILATOR_SMOKE_PASS", "SKIPPED")
    chk("verilator_emit_smoke", vlt_ok, detail=verilator.get("verdict", ""))
    chk(
        "sandwich_norm_iron",
        sandwich_iron["verdict"] == "SANDWICH_NORM_IRON_PASS",
        detail=sandwich_iron.get("verdict", ""),
    )

    circt_avail = _circt_on_path()
    chk("circt_binary_local_optional", True, detail="vps_remote" if not circt_avail else "local+vps")

    core_ids = {
        "circt_binary_local_optional",
        "yosys_local_msys",
    }
    verdict = (
        "T4_EMIT_PASS"
        if all(c["pass"] for c in checks if c["id"] not in core_ids)
        else "T4_UNPARK_FAIL"
    )

    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_MLIR_UNPARK_T4_RECEIPT_v1",
        "bind_id": "CHIP_CLIFFORD_MLIR_UNPARK_T4_BIND_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canon": list(_CANON),
        "sprint_track": "T4",
        "checks": checks,
        "unpark_gate": {
            "t1_cayley_gold": t1_ok,
            "t2_rtl_optimize": t2_ok,
            "gp_legalize": legalize["verdict"],
            "dual_physics_compile_rail": "pending_merge",
        },
        "t4_1_dialect_stub": {
            "path": str(dialect_td.relative_to(_REPO)).replace("\\", "/"),
            "ops": ["clifford.constant", "clifford.gp", "clifford.sandwich", "clifford.norm"],
            "mlir_examples": [str(p.relative_to(_REPO)).replace("\\", "/") for p in mlir_examples],
        },
        "t4_2_structural_diff": structural,
        "legalize": legalize,
        "emit": emit,
        "netlist_diff": netlist,
        "verilator_smoke": verilator,
        "sandwich_norm_iron": sandwich_iron,
        "cayley_regen": regen,
        "toolchain_pin": str(pin_path.relative_to(_REPO)).replace("\\", "/"),
        "t1_bind": "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1",
        "t2_bind": "CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1",
        "t3_bind": "CHIP_CLIFFORD_MOTOR_LERP_STUDY_RECEIPT_v1",
        "honesty": {
            "iron_crown": "hand SV clifford_geo_prod_v0.v",
            "mlir_replaces_sv": False,
            "circt_opt_ran": emit["verdict"] == "EMIT_PASS",
            "circt_host": "ubuntu@3.123.254.209",
            "yosys_host": netlist.get("yosys_host", "local_msys"),
            "firtool_pin": "1.146.0",
            "structural_diff_only": False,
            "bf16_functional_on_circt_emit": False,
            "verilator_emit_smoke": verilator.get("verdict"),
            "sandwich_norm_lower": sandwich_iron.get("verdict"),
            "timing_closure": False,
            "null_plane_pga": "PARK_P2.1",
        },
    }

    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        _BIND.write_text(
            json.dumps(
                {
                    "bind_id": receipt["bind_id"],
                    "receipt_id": receipt["receipt_id"],
                    "verdict": verdict,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        fixture = _FIX / "clifford_mlir_unpark_v1.json"
        fixture.write_text(
            json.dumps(
                {
                    "legalize_summary": {
                        "verdict": legalize["verdict"],
                        "n_cases": legalize["n_cases"],
                    },
                    "structural_summary": {
                        "verdict": structural["verdict"],
                        "mul_terms": structural["hand_rtl"]["mul_terms"],
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return receipt


if __name__ == "__main__":
    print(json.dumps(run_clifford_mlir_unpark_t4(write=True), indent=2))
