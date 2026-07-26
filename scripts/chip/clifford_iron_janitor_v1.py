#!/usr/bin/env python3
"""Iron janitor — run chip gate batch locally, heartbeat, optional VPS sync.

Local-first (iverilog/Windows). Hermes on VPS reads synced heartbeat + Telegram.

Canon: docs/agent_workflow/CHIP_IRON_JANITOR_V1.md
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_STOP = _REPO / "results" / "platform_bpass" / "chip" / "clifford_agent_stop_v0.flag"
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_IRON_JANITOR_RECEIPT_v1.json"
_BATCH_PS1 = _REPO / "scripts" / "chip" / "run_clifford_iron_janitor_batch_v0.ps1"
_SYNC_PS1 = _REPO / "infra" / "hermes" / "vps_gateway" / "sync_chip_batch_heartbeat_vps.ps1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _no_window_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return 0


def _emit_observer(verdict: str, detail: dict) -> None:
    sys.path.insert(0, str(_REPO / "scripts" / "observer"))
    try:
        from observer_events import append_event

        append_event("chip.iron_janitor", {"verdict": verdict, **detail}, source="iron_janitor")
    except Exception as exc:
        print(f"WARN observer emit: {exc}", file=sys.stderr)


def _sync_heartbeat_vps() -> bool:
    if not _SYNC_PS1.is_file():
        return False
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(_SYNC_PS1)],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        creationflags=_no_window_flags(),
    )
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr, file=sys.stderr)
        return False
    print(proc.stdout.strip())
    return True


def run_janitor(*, light_only: bool = False, skip_batch: bool = False) -> int:
    if _STOP.is_file():
        msg = _STOP.read_text(encoding="utf-8").strip() or "stop flag set"
        doc = {
            "receipt_id": "CHIP_CLIFFORD_IRON_JANITOR_RECEIPT_v1",
            "timestamp_utc": _utc_now(),
            "verdict": "JANITOR_STOPPED",
            "reason": msg,
        }
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"STOP: {msg}")
        return 0

    batch_rc = 0
    batch_log = ""
    if not skip_batch:
        if not _BATCH_PS1.is_file():
            print(f"FAIL: missing {_BATCH_PS1}", file=sys.stderr)
            return 1
        env = {**os.environ, "PYTHONPATH": str(_REPO)}
        if light_only:
            env["CLIFFORD_JANITOR_LIGHT_ONLY"] = "1"
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-File", str(_BATCH_PS1)],
            cwd=str(_REPO),
            env=env,
            capture_output=True,
            text=True,
            creationflags=_no_window_flags(),
        )
        batch_rc = proc.returncode
        batch_log = (proc.stdout or "") + (proc.stderr or "")
        print(batch_log)
        if batch_rc != 0:
            _emit_observer("batch_fail", {"exit_code": batch_rc, "tail": batch_log[-2000:]})

    sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_batch_heartbeat_v1 import build_heartbeat

    heartbeat = build_heartbeat(
        batch_id="iron_janitor",
        last_action="batch_run" if not skip_batch else "heartbeat_only",
    )
    synced = _sync_heartbeat_vps()

    verdict = "JANITOR_BATCH_PASS" if batch_rc == 0 and heartbeat["verdict"] == "JANITOR_HEARTBEAT_GREEN" else "JANITOR_BATCH_WARN"
    if batch_rc != 0:
        verdict = "JANITOR_BATCH_FAIL"

    doc = {
        "receipt_id": "CHIP_CLIFFORD_IRON_JANITOR_RECEIPT_v1",
        "timestamp_utc": _utc_now(),
        "verdict": verdict,
        "batch_exit_code": batch_rc,
        "heartbeat_verdict": heartbeat["verdict"],
        "summary": heartbeat["summary"],
        "vps_synced": synced,
        "light_only": light_only,
    }
    _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    _emit_observer(verdict, doc)
    print(json.dumps(doc, indent=2))
    return 0 if verdict != "JANITOR_BATCH_FAIL" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Clifford iron janitor batch + heartbeat")
    ap.add_argument("--light-only", action="store_true", help="Skip heavy tier gates")
    ap.add_argument("--heartbeat-only", action="store_true", help="Refresh heartbeat without batch")
    args = ap.parse_args()
    return run_janitor(light_only=args.light_only, skip_batch=args.heartbeat_only)


if __name__ == "__main__":
    raise SystemExit(main())
