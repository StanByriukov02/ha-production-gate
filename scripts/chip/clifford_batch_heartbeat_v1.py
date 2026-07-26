"""Iron janitor heartbeat — aggregate gate receipts for Hermes/Tony sync."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_REGISTRY = _REPO / "fixtures" / "chip" / "clifford_gate_registry_v0.json"
_HEARTBEAT = _REPO / "results" / "platform_bpass" / "chip" / "clifford_batch_heartbeat_remote.json"
_STOP = _REPO / "results" / "platform_bpass" / "chip" / "clifford_agent_stop_v0.flag"
_LOCK = _REPO / "results" / "platform_bpass" / "chip" / "clifford_sim_heavy_lock_v0.json"


def _verdict_from_receipt(data: dict[str, Any]) -> str:
    for key in ("verdict", "status", "glue_level"):
        if key in data and data[key] is not None:
            return str(data[key])
    latest = data.get("latest")
    steps = data.get("steps")
    if isinstance(latest, str) and isinstance(steps, dict) and latest in steps:
        step = steps[latest]
        if isinstance(step, dict):
            for key in ("verdict", "alu_status"):
                if step.get(key):
                    return str(step[key])
    return "UNKNOWN"


def _pass_from_verdict(verdict: str) -> bool:
    v = verdict.upper()
    if v.endswith("_FAIL") or v == "FAIL":
        return False
    if "DEGRADED" in v:
        return "PASS" in v or v == "SIM_SLOT_RUNNER_DEGRADED"
    if any(x in v for x in ("FAIL", "BLOCK", "OPEN")):
        return False
    return any(
        x in v
        for x in (
            "PASS",
            "READY",
            "NONE",
            "OK",
            "GATE_REGISTRY",
            "EXPEDITION_BATCH_PASS",
            "CROWN_STACK_PASS",
            "DEGRADED",
        )
    )


def build_heartbeat(
    *,
    batch_id: str = "iron_janitor",
    last_action: str = "heartbeat_only",
    write: bool = True,
) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    registry: dict[str, Any] = {}
    if _REGISTRY.is_file():
        registry = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    else:
        from scripts.chip.clifford_gate_registry_v0 import build_gate_registry

        registry = build_gate_registry()

    rows: list[dict[str, Any]] = []
    fail_count = 0
    missing_count = 0
    for gate in registry.get("gates", []):
        gid = gate.get("id", "?")
        receipt_rel = gate.get("receipt", "")
        receipt_path = _REPO / str(receipt_rel).replace("/", "\\")
        row: dict[str, Any] = {
            "id": gid,
            "tier": gate.get("tier"),
            "receipt": receipt_rel,
            "present": receipt_path.is_file(),
            "pass": False,
            "verdict": "MISSING",
        }
        if receipt_path.is_file():
            try:
                data = json.loads(receipt_path.read_text(encoding="utf-8"))
                verdict = _verdict_from_receipt(data)
                row["verdict"] = verdict
                row["pass"] = _pass_from_verdict(verdict)
                row["timestamp_utc"] = data.get("timestamp_utc")
            except (json.JSONDecodeError, OSError) as exc:
                row["verdict"] = f"READ_ERROR:{exc}"
                row["pass"] = False
        else:
            missing_count += 1
        if not row["pass"]:
            fail_count += 1
        rows.append(row)

    lock_state: dict[str, Any] | None = None
    if _LOCK.is_file():
        try:
            lock_state = json.loads(_LOCK.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            lock_state = {"raw": "parse_error"}

    doc: dict[str, Any] = {
        "schema": "CLIFFORD_BATCH_HEARTBEAT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "last_action": last_action,
        "stop_flag": _STOP.is_file(),
        "heavy_lock": lock_state,
        "summary": {
            "gates_total": len(rows),
            "gates_pass": sum(1 for r in rows if r["pass"]),
            "gates_fail": fail_count,
            "receipts_missing": missing_count,
        },
        "verdict": "JANITOR_HEARTBEAT_GREEN"
        if fail_count == 0 and not _STOP.is_file()
        else "JANITOR_HEARTBEAT_WARN",
        "gates": rows,
        "honesty": {
            "executor": "laptop_local",
            "hermes_reports_only": True,
            "clifford_alu_is_crown": True,
            "chip_is_carrier": True,
        },
    }
    if write:
        _HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
        _HEARTBEAT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    print(json.dumps(build_heartbeat(), indent=2))
