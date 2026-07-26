"""Chip carrier tier V4 — vendor flow stub + MMIO HIL host + post-crown twin."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_TWIN = _REPO / "results" / "platform_bpass" / "twin"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_chip_carrier_tier_v4(*, write: bool = True) -> dict[str, Any]:
    v3 = _load(_CHIP / "CHIP_CLIFFORD_CHIP_CARRIER_TIER_V3_RECEIPT_v1.json")
    hil = _load(_CHIP / "CHIP_CLIFFORD_MMIO_HIL_HOST_GATE_RECEIPT_v1.json")
    vendor = _load(_CHIP / "CHIP_CLIFFORD_FPGA_VENDOR_FLOW_RECEIPT_v1.json")
    twin = _load(_TWIN / "DOGFOOD_TWIN_POST_CROWN_GATE_RECEIPT_v1.json")

    checks = [
        {"id": "carrier_tier_v3", "pass": v3.get("verdict") == "CHIP_CARRIER_TIER_V3_READY"},
        {"id": "mmio_hil_host", "pass": hil.get("verdict") == "MMIO_HIL_HOST_GATE_PASS"},
        {"id": "vendor_flow_stub", "pass": vendor.get("verdict") == "FPGA_VENDOR_FLOW_STUB_READY"},
        {"id": "post_crown_twin", "pass": twin.get("verdict") == "POST_CROWN_TWIN_GATE_PASS"},
    ]
    verdict = "CHIP_CARRIER_TIER_V4_READY" if all(c["pass"] for c in checks) else "CHIP_CARRIER_TIER_V4_BUILDING"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_CHIP_CARRIER_TIER_V4_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "tier": "V4_carrier_bringup",
        "checks": checks,
        "next_tier": "V5: dev-board MMIO HIL measured · bitstream ERF (PARK)",
        "honesty": {
            "not_silicon_signoff": True,
            "sim_hil_only": True,
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        (_CHIP / "CHIP_CLIFFORD_CHIP_CARRIER_TIER_V4_RECEIPT_v1.json").write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8"
        )
    return doc


if __name__ == "__main__":
    out = evaluate_chip_carrier_tier_v4()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "CHIP_CARRIER_TIER_V4_READY" else 1)
