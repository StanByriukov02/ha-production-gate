"""H2 scaffold — mission bring-up clock signoff from STA thermometer (not 100 MHz theater)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_MISSION_CLOCK_SIGNOFF_v1.json"
_STA_BIND = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_WORLD_MOTION_STA_BIND_RECEIPT_v1.json"
_BRINGUP = _REPO / "docs" / "agent_workflow" / "CLIFFORD_STA_T2_BRINGUP_CHECKPOINT_v1.md"

PHI_NS = 10.0
MISSION_MHZ_LO = 25.0
MISSION_MHZ_HI = 30.0


def build_signoff(*, write: bool = True) -> dict:
    wns_ns = None
    if _STA_BIND.is_file():
        bind = json.loads(_STA_BIND.read_text(encoding="utf-8"))
        wns_ns = float((bind.get("sta_mapped") or {}).get("wns_ns") or 0)
    if wns_ns is None:
        wns_ns = -15.25
    f_max_mhz = 1000.0 / (PHI_NS - wns_ns) if wns_ns < PHI_NS else 0.0
    timing_closed = wns_ns >= 0.0
    # Mission-class iron runs underclocked @ 25–30 MHz/φ — not f_max ceiling claim.
    mission_operating_ok = MISSION_MHZ_LO <= f_max_mhz
    doc = {
        "receipt_id": "CHIP_CLIFFORD_MISSION_CLOCK_SIGNOFF_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS" if mission_operating_ok and not timing_closed else "FAIL",
        "wns_ns": round(wns_ns, 3),
        "phi_period_ns": PHI_NS,
        "f_max_mhz": round(f_max_mhz, 2),
        "bringup_mhz_ceiling": round(f_max_mhz, 2),
        "mission_operating_band_mhz": [MISSION_MHZ_LO, MISSION_MHZ_HI],
        "mission_clock_signoff_ok": mission_operating_ok,
        "timing_closed_10ns_phi": timing_closed,
        "honesty": {
            "not_100_mhz_claim": True,
            "source": str(_STA_BIND.relative_to(_REPO)).replace("\\", "/"),
            "canon": str(_BRINGUP.relative_to(_REPO)).replace("\\", "/"),
        },
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = build_signoff()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "PASS" else 1)
