"""Post-crown twin gate — unpark visual after CROWN_STACK + expedition PASS."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_TWIN = _REPO / "results" / "platform_bpass" / "twin"
_RECEIPT = _TWIN / "DOGFOOD_TWIN_POST_CROWN_GATE_RECEIPT_v1.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_post_crown_twin_gate(*, write: bool = True) -> dict[str, Any]:
    crown = _load(_CHIP / "CHIP_CLIFFORD_CROWN_STACK_GATE_RECEIPT_v1.json")
    prod = _load(_CHIP / "CHIP_CLIFFORD_PRODUCTION_CROWN_GATE_RECEIPT_v1.json")
    expedition = _load(_REPO / "results/platform_bpass/moon/ROBOT_IFT2_WORLD_EXPEDITION_BATCH_RECEIPT_v1.json")

    from dogfood_platform.dogfood_twin_bringup_unpark_v1 import run_twin_bringup_unpark

    unpark = run_twin_bringup_unpark(write=write)
    honesty = crown.get("honesty") or {}

    checks = [
        {"id": "crown_stack_pass", "pass": crown.get("verdict") == "CROWN_STACK_PASS"},
        {"id": "production_crown_pass", "pass": prod.get("verdict") == "PRODUCTION_CROWN_GATE_PASS"},
        {"id": "expedition_pass", "pass": expedition.get("verdict") == "EXPEDITION_BATCH_PASS"},
        {"id": "twin_visual_unparked", "pass": honesty.get("twin_visual_park_until_m3") is False},
        {"id": "twin_bringup_unpark", "pass": unpark.get("verdict") == "TWIN_BRINGUP_UNPARK_PASS"},
    ]
    verdict = "POST_CROWN_TWIN_GATE_PASS" if all(c["pass"] for c in checks) else "POST_CROWN_TWIN_GATE_DEGRADED"

    doc: dict[str, Any] = {
        "receipt_id": "DOGFOOD_TWIN_POST_CROWN_GATE_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "unpark_receipt": unpark.get("verdict"),
        "runtime_url": expedition.get("runtime_url"),
        "honesty": {
            "teaching_hud_ok": True,
            "not_measured_iron": True,
            "clifford_alu_is_crown": True,
        },
    }
    if write:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_post_crown_twin_gate()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "POST_CROWN_TWIN_GATE_PASS" else 1)
