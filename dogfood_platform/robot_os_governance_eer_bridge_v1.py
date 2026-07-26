"""Bridge dogfood governance traces → evidence_engine eer-0.1 receipts.

Optional sibling package: ../evidence_engine (not required for Production Gate).
TABU: claim receipt without verify · treat optional sibling as this clone's install.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_EE_ROOT = _REPO.parent / "evidence_engine"
_DEFAULT_ENVELOPE = _EE_ROOT / "fixtures" / "envelope_lunar_crater_5km.json"
_DEFAULT_TRACE = _REPO / "fixtures" / "robot" / "policy_traces" / "smolvla_trace_live_libero_v1.jsonl"


def evidence_engine_available() -> bool:
    return (_EE_ROOT / "src" / "evidence_engine" / "runner.py").is_file()


def export_trace_to_eer_receipt(
    trace_path: Path | str,
    *,
    envelope_path: Path | str | None = None,
    out_path: Path | str | None = None,
    policy_source_id: str = "smolvla_trace_live_libero_v1",
) -> dict[str, Any]:
    """Run evidence_engine on a JSONL trace; return + optionally write eer-0.1 receipt."""
    if not evidence_engine_available():
        raise FileNotFoundError(f"evidence_engine not found at {_EE_ROOT}")

    trace_path = Path(trace_path)
    envelope_path = Path(envelope_path or _DEFAULT_ENVELOPE)
    if not trace_path.is_file():
        raise FileNotFoundError(trace_path)
    if not envelope_path.is_file():
        raise FileNotFoundError(envelope_path)

    sys.path.insert(0, str(_EE_ROOT / "src"))
    from evidence_engine.receipt import verify_receipt_dict, write_receipt  # noqa: WPS433
    from evidence_engine.runner import run_trace  # noqa: WPS433

    receipt = run_trace(
        trace_path,
        envelope_path,
        mode="trace_replay",
        policy_source_id=policy_source_id,
    )
    if not verify_receipt_dict(receipt, envelope=json.loads(envelope_path.read_text(encoding="utf-8"))):
        raise RuntimeError("eer-0.1 self-verify failed after export")

    if out_path:
        write_receipt(receipt, Path(out_path))

    return receipt


def export_via_cli(
    trace_path: Path | str,
    out_path: Path | str,
    *,
    envelope_path: Path | str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Subprocess fallback — no import path mutation."""
    envelope = envelope_path or _DEFAULT_ENVELOPE
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "evidence_engine",
            "run",
            "--trace",
            str(trace_path),
            "--envelope",
            str(envelope),
            "--out",
            str(out_path),
            "--mode",
            "trace_replay",
        ],
        cwd=str(_EE_ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**dict(**__import__("os").environ), "PYTHONPATH": str(_EE_ROOT / "src")},
    )


def run_bridge_gate(
    *,
    trace_path: Path | str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    trace = Path(trace_path or _DEFAULT_TRACE)
    harness: dict[str, Any] = {
        "harness_id": "governance_eer_bridge_v1",
        "proof_tier": "GOVERNANCE_EER_BRIDGE_SLICE",
        "evidence_engine_available": evidence_engine_available(),
    }
    if not harness["evidence_engine_available"]:
        harness["verdict"] = "GOVERNANCE_EER_BRIDGE_SKIP"
        harness["fail"] = ["F_evidence_engine_missing"]
        return harness

    out = _REPO / "results" / "platform_bpass" / "chip" / "ROBOT_OS_GOVERNANCE_EER_BRIDGE_RECEIPT_v1.json"
    receipt = export_trace_to_eer_receipt(trace, out_path=out if write else None)
    counters = receipt["counters"]
    checks = {
        "F_receipt_schema": receipt.get("schema_version") == "eer-0.1",
        "F_steps_positive": int(counters.get("steps") or 0) > 0,
        "F_chain_present": bool(receipt.get("chain_final_hash")),
        "F_verify_self": True,
    }
    fail = [k for k, v in checks.items() if not v]
    harness.update(
        {
            "checks": checks,
            "fail": fail,
            "eer_steps": counters.get("steps"),
            "eer_vetoes": counters.get("vetoes"),
            "eer_per_rule": counters.get("per_rule"),
            "trace_source": str(trace.relative_to(_REPO)).replace("\\", "/")
            if trace.is_relative_to(_REPO)
            else str(trace),
            "verdict": "GOVERNANCE_EER_BRIDGE_PASS" if not fail else "GOVERNANCE_EER_BRIDGE_FAIL",
            "honesty": receipt.get("honesty"),
            "tabu": "claim live robot · claim MEASURED field safety",
        }
    )
    if write:
        wrapper = {
            "receipt_id": "ROBOT_OS_GOVERNANCE_EER_BRIDGE_RECEIPT_v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **harness,
            "eer_receipt_path": str(out.relative_to(_REPO)).replace("\\", "/"),
        }
        out.write_text(json.dumps(wrapper, indent=2) + "\n", encoding="utf-8")
    return harness


if __name__ == "__main__":
    print(json.dumps(run_bridge_gate(), indent=2))
