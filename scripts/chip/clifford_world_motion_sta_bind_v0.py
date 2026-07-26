"""World motion ↔ STA mapped netlist bind (Nangate45 · honest thermometer)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_MOON = _REPO / "results" / "platform_bpass" / "moon"
_STA_REPORT = _CHIP / "sta" / "clifford_alu_opensta_liberty_full_report_v0.json"
_MAPPED = _CHIP / "sta" / "clifford_sta_alu_slice_mapped_v0.v"
_IRON_RCPT = _CHIP / "CHIP_CLIFFORD_WORLD_MOTION_IRON_RECEIPT_v1.json"
_BIND_RCPT = _CHIP / "CHIP_CLIFFORD_WORLD_MOTION_STA_BIND_RECEIPT_v1.json"
_CLOCK = _REPO / "fixtures" / "twin" / "dogfood_twin_iron_clock_feed_v1.json"
_BINDING = "u_geo_prod_pipe/u_high_hi_synth"
_CHECKPOINT = "docs/agent_workflow/CLIFFORD_STA_T2_BRINGUP_CHECKPOINT_v1.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_world_motion_sta_bind(*, write: bool = True) -> dict[str, Any]:
    issues: list[str] = []
    iron = _load(_IRON_RCPT) if _IRON_RCPT.is_file() else {}
    sta = _load(_STA_REPORT) if _STA_REPORT.is_file() else {}

    if iron.get("verdict") != "PASS":
        issues.append(f"iron_receipt={iron.get('verdict', 'missing')}")
    if not _MAPPED.is_file():
        issues.append("mapped_netlist_missing")
    if sta.get("verdict") != "OPENSTA_LIBERTY_FULL_PASS":
        issues.append(f"opensta_report={sta.get('verdict', 'missing')}")

    ys = sta.get("yosys_mapped") or {}
    ost = sta.get("opensta_liberty") or {}
    if ys.get("status") != "PASS":
        issues.append("yosys_mapped_not_pass")
    wns = ost.get("wns_ns")
    if wns is None:
        issues.append("wns_missing")

    tail = str(ost.get("stdout_tail") or "")
    binding_ok = _BINDING.replace("/", "/") in tail or iron.get("sta_binding") == _BINDING
    if not binding_ok:
        issues.append("sta_binding_path_mismatch")

    phi_period_ns = 10.0
    study_anchor_mhz = round(1000.0 / phi_period_ns, 1)
    bringup_mhz = round(1000.0 / (phi_period_ns - float(wns)) if wns is not None else 39.6, 1)

    doc = {
        "receipt_id": "CHIP_CLIFFORD_WORLD_MOTION_STA_BIND_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS" if not issues else "FAIL",
        "issues": issues,
        "world_motion_iron": {
            "receipt": str(_IRON_RCPT.relative_to(_REPO)).replace("\\", "/"),
            "iron_sim_backend": iron.get("iron_sim_backend"),
            "ticks": iron.get("ticks"),
            "iron_cxx_rmse_m": iron.get("iron_cxx_rmse_m"),
        },
        "sta_mapped": {
            "opensta_report": str(_STA_REPORT.relative_to(_REPO)).replace("\\", "/"),
            "mapped_netlist": str(_MAPPED.relative_to(_REPO)).replace("\\", "/"),
            "mapped_netlist_sha256": _sha256(_MAPPED) if _MAPPED.is_file() else None,
            "yosys_cells": ys.get("cells"),
            "yosys_dff": ys.get("dff_count"),
            "wns_ns": wns,
            "binding": _BINDING,
            "phi_period_ns": phi_period_ns,
            "study_anchor_mhz": study_anchor_mhz,
            "bringup_mhz_ceiling": bringup_mhz,
            "timing_closed": False,
        },
        "parity_rule": "world_motion_verilator_poses bound to STA WNS thermometer (not 100MHz claim)",
        "checkpoint": _CHECKPOINT,
        "honesty": {
            "mapped_sim_not_world_tb": False,
            "mapped_slice_geo_prod_smoke": True,
            "structural_synth_mmio_enabled": True,
            "behavioral_verilator_primary_for_poses": True,
            "sta_structural_smoke": True,
            "not_fpga_signoff": True,
        },
    }

    if write:
        _BIND_RCPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        if _CLOCK.is_file() and not issues:
            clock = _load(_CLOCK)
            clock["world_motion_sta_bind"] = {
                "receipt": str(_BIND_RCPT.relative_to(_REPO)).replace("\\", "/"),
                "mapped_netlist_sha256": doc["sta_mapped"]["mapped_netlist_sha256"],
                "iron_sim_backend": iron.get("iron_sim_backend"),
                "macro_compose_ns": clock.get("macro_compose_ns"),
            }
            clock["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
            _CLOCK.write_text(json.dumps(clock, indent=2) + "\n", encoding="utf-8")
    return doc


def run_world_motion_sta_bind(*, write: bool = True) -> dict[str, Any]:
    doc = build_world_motion_sta_bind(write=write)
    return {"verdict": doc["verdict"], "bind": doc}


if __name__ == "__main__":
    out = run_world_motion_sta_bind()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 1)
