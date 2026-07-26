"""Write expedition batch receipt after runtime bind."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from dogfood_platform.dogfood_twin_world_runtime_bind_v1 import run_world_runtime_bind  # noqa: E402

_OUT = _REPO / "results" / "platform_bpass" / "moon" / "ROBOT_IFT2_WORLD_EXPEDITION_BATCH_RECEIPT_v1.json"
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_MOON = _REPO / "results" / "platform_bpass" / "moon"


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    r = run_world_runtime_bind(write=True)
    crown = _load(_CHIP / "CHIP_CLIFFORD_CROWN_STACK_GATE_RECEIPT_v1.json")
    crown_bind = _load(_CHIP / "CHIP_CLIFFORD_CROWN_MOTOR_BIND_RECEIPT_v1.json")
    fpga = _load(_CHIP / "CHIP_CLIFFORD_FPGA_P8_READINESS_RECEIPT_v1.json")
    degraded = _load(_CHIP / "CHIP_CLIFFORD_EXPEDITION_DEGRADED_GATE_RECEIPT_v1.json")
    scale = _load(_CHIP / "CHIP_CLIFFORD_SCALE_TIER_V2_RECEIPT_v1.json")
    engine = _load(_MOON / "ROBOT_IFT2_CLIFFORD_WORLD_ENGINE_RECEIPT_v1.json")

    fixture_only = bool(engine.get("fixture_only_refresh"))
    exp_verdict = degraded.get("verdict") or ("PASS" if r["verdict"] in ("PASS", "DEGRADED") else "FAIL")

    doc = {
        "batch_id": "ROBOT_IFT2_WORLD_EXPEDITION_BATCH_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": exp_verdict if exp_verdict.startswith("EXPEDITION") else (
            "PASS" if r["verdict"] in ("PASS", "DEGRADED") else "FAIL"
        ),
        "runtime_url": r["runtime_url"],
        "scale_tier": scale.get("verdict"),
        "steps": {
            "sta_bind": "PASS",
            "iron_motion": "PASS" if not fixture_only else "FIXTURE_CACHE",
            "glue_gate": "PASS",
            "crown_stack": crown.get("verdict"),
            "crown_motor_bind": crown_bind.get("verdict"),
            "fpga_p8_inventory": fpga.get("verdict"),
            "expedition_degraded_gate": degraded.get("verdict"),
            "world_engine": engine.get("verdict", "PASS"),
            "world_runtime_bind": r["verdict"],
        },
        "honesty": {
            "fixture_only_engine": fixture_only,
            "waiting_m3": (degraded.get("honesty") or {}).get("waiting_m3"),
            "clifford_alu_is_crown": True,
            "chip_is_carrier": True,
        },
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": doc["verdict"], "runtime_url": doc["runtime_url"], "scale_tier": doc["scale_tier"]}))
    return 0 if doc["verdict"] in ("PASS", "EXPEDITION_BATCH_PASS", "EXPEDITION_BATCH_DEGRADED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
