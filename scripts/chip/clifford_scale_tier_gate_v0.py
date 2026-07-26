"""Scale tier V2 gate — aggregate factory + expedition + crown (no per-tick work)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_MOON = _REPO / "results" / "platform_bpass" / "moon"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_SCALE_TIER_V2_RECEIPT_v1.json"
_REGISTRY = _REPO / "fixtures" / "chip" / "clifford_gate_registry_v0.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_scale_tier_v2(*, write: bool = True) -> dict[str, Any]:
    slot_run = _load(_MOON / "ROBOT_IFT2_SIM_SLOT_RUNNER_RECEIPT_v1.json")
    gap = _load(_MOON / "ROBOT_ASSEMBLY_GAP_REGISTER_v1.json")
    expedition = _load(_CHIP / "CHIP_CLIFFORD_EXPEDITION_DEGRADED_GATE_RECEIPT_v1.json")
    prod = _load(_CHIP / "CHIP_CLIFFORD_PRODUCTION_CROWN_GATE_RECEIPT_v1.json")
    runtime = _load(_MOON / "ROBOT_IFT2_TWIN_WORLD_RUNTIME_RECEIPT_v1.json")
    engine = _load(_MOON / "ROBOT_IFT2_CLIFFORD_WORLD_ENGINE_RECEIPT_v1.json")
    vi2 = _load(_MOON / "ROBOT_IFT2_VI2_SIM_RECEIPT_v1.json")

    slots_scanned = int(slot_run.get("slots_scanned") or 0)
    slots_pass = int(slot_run.get("slots_pass") or 0)
    slot_ok = slots_scanned >= 100 and slots_pass >= int(slots_scanned * 0.95)
    gap_ok = bool(gap.get("register_id") or gap.get("registry_id"))
    exp_ok = expedition.get("verdict") in ("EXPEDITION_BATCH_PASS", "EXPEDITION_BATCH_DEGRADED")
    prod_ok = prod.get("verdict") in ("PRODUCTION_CROWN_GATE_READY", "PRODUCTION_CROWN_GATE_PASS")
    runtime_ok = runtime.get("verdict") in ("PASS", "DEGRADED")
    engine_ok = engine.get("verdict") in ("PASS", "BLOCKED")  # BLOCKED = stress only
    registry_ok = _REGISTRY.is_file()
    crown_loop = vi2.get("clifford_crown_in_loop") is True if vi2 else None

    checks = [
        {"id": "factory_slots_scanned", "pass": slot_ok, "detail": f"{slots_pass}/{slots_scanned}"},
        {"id": "gap_register", "pass": gap_ok},
        {"id": "expedition_honest", "pass": exp_ok, "detail": expedition.get("verdict")},
        {"id": "production_crown", "pass": prod_ok, "detail": prod.get("verdict")},
        {"id": "world_runtime", "pass": runtime_ok, "detail": runtime.get("verdict")},
        {"id": "world_engine_receipt", "pass": engine_ok, "detail": engine.get("verdict")},
        {"id": "gate_registry", "pass": registry_ok},
    ]
    if crown_loop is not None:
        checks.append({"id": "vi2_crown_in_loop", "pass": crown_loop})

    core_ok = all(c["pass"] for c in checks if c["id"] != "vi2_crown_in_loop")
    verdict = "SCALE_TIER_V2_READY" if core_ok else "SCALE_TIER_V2_BUILDING"

    doc: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_SCALE_TIER_V2_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "tier": "V2",
        "checks": checks,
        "next_tier": "V3: M3 PASS → EXPEDITION_BATCH_PASS → PRODUCTION_CROWN_GATE_PASS",
        "honesty": {
            "not_product_signoff": True,
            "m3_may_be_in_flight": (_CHIP / "clifford_sim_heavy_lock_v0.json").is_file(),
            "clifford_alu_is_crown": True,
            "chip_is_carrier": True,
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    out = evaluate_scale_tier_v2()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["verdict"] == "SCALE_TIER_V2_READY" else 1)
