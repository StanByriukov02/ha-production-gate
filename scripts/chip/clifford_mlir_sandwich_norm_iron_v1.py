"""Sandwich/norm MLIR lower + hand iron yosys/STA smoke (T4 post-emit)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_MLIR_SANDWICH_NORM_IRON_RECEIPT_v1.json"
_LOWER = _REPO / "mlir" / "clifford" / "lower"
_SANDWICH_YS = _REPO / "scripts" / "chip" / "clifford_area_sandwich_probe_sim_v0.ys"


def run_clifford_mlir_sandwich_norm_iron(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    from scripts.chip.clifford_msys_toolchain_v1 import run_yosys_script
    from scripts.chip.gen_clifford_sandwich_norm_circt_mlir_v1 import main as gen_mlir
    from scripts.chip.run_clifford_alu_opensta_smoke_v0 import run_clifford_alu_opensta_smoke

    gen_mlir()
    mlir_files = {
        "reverse": str((_LOWER / "reverse_hw.mlir").relative_to(_REPO)).replace("\\", "/"),
        "sandwich_chain": str((_LOWER / "sandwich_gp_chain_hw.mlir").relative_to(_REPO)).replace("\\", "/"),
        "norm_stub": str((_LOWER / "norm_stub_hw.mlir").relative_to(_REPO)).replace("\\", "/"),
    }

    sandwich_probe = run_yosys_script(_SANDWICH_YS)
    sta_smoke = run_clifford_alu_opensta_smoke()

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("mlir_reverse_lower", (_LOWER / "reverse_hw.mlir").is_file())
    chk("mlir_sandwich_chain_lower", (_LOWER / "sandwich_gp_chain_hw.mlir").is_file())
    chk("mlir_norm_stub_lower", (_LOWER / "norm_stub_hw.mlir").is_file())
    chk(
        "yosys_sandwich_area_probe",
        sandwich_probe.get("status") == "PASS",
        detail=str(sandwich_probe.get("cells")),
    )
    chk(
        "yosys_sta_netlist",
        sta_smoke.get("yosys_netlist", {}).get("status") == "PASS",
        detail=sta_smoke.get("yosys_netlist", {}).get("netlist", ""),
    )
    chk(
        "sdc_netlist_linkage",
        sta_smoke.get("sdc_netlist_linkage", {}).get("verdict") == "SDC_NETLIST_LINK_PASS",
    )
    sta_cli = sta_smoke.get("opensta_cli", {})
    chk(
        "opensta_structural_smoke",
        sta_cli.get("status") in ("PASS", "SKIPPED"),
        detail=sta_cli.get("status", ""),
    )

    verdict = "SANDWICH_NORM_IRON_PASS" if all(c["pass"] for c in checks) else "SANDWICH_NORM_IRON_FAIL"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_MLIR_SANDWICH_NORM_IRON_RECEIPT_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mlir_lower": mlir_files,
        "sandwich_area_probe": sandwich_probe,
        "sta_smoke": sta_smoke,
        "checks": checks,
        "honesty": {
            "pose_sandwich_tabu": True,
            "norm_bf16_sqrt_park": True,
            "mlir_structural_only": True,
            "iron_crown_hand_sv": True,
            "circt_emit_sandwich": "PARK — mlir stub + hand yosys/STA",
        },
    }

    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    print(json.dumps(run_clifford_mlir_sandwich_norm_iron(write=True), indent=2))
