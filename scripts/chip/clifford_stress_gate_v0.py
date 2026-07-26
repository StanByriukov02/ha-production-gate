"""Clifford ALU stress gate — machine state + hook injection (not md-only).

Canon: docs/agent_workflow/CLIFFORD_OP_SEMANTICS_LAW_V1.md
Writes: results/platform_bpass/chip/CLIFFORD_STRESS_STATE_v1.json
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STATE = _CHIP / "CLIFFORD_STRESS_STATE_v1.json"

_RECEIPTS = {
    "p5": _CHIP / "CHIP_CLIFFORD_ALU_P5_RECEIPT_v1.json",
    "p6": _CHIP / "CHIP_CLIFFORD_ALU_P6_RECEIPT_v1.json",
    "lc2": _CHIP / "CHIP_CLIFFORD_LC2_BENCH_POSE_PROBE_RECEIPT_v1.json",
    "dual_p5": _CHIP / "CHIP_CLIFFORD_DUAL_PHYSICS_REVIEW_P5_RECEIPT_v1.json",
}

_CLIFFORD_PROMPT = re.compile(
    r"clifford|geo_prod|sandwich|mmio|verilator|lc2.*pose|motor128|fixtures/chip|dogfood_twin_clifford|world.runtime|world.motion",
    re.I,
)
_SANDWICH_POSE_TABU = re.compile(
    r"sandwich.*(pose|landmark|joint|hip|rigid)|(pose|landmark|joint).*(sandwich)",
    re.I,
)

INJECT_WARN = """MODE: CLIFFORD_STRESS (warn)
Stress gate active — receipts or law spikes degraded.
STOP promote · run dual physics review · fix iron before new features.
State: results/platform_bpass/chip/CLIFFORD_STRESS_STATE_v1.json
Canon: CLIFFORD_OP_SEMANTICS_LAW_V1 · SANDWICH≠pose"""

INJECT_CRITICAL = """MODE: CLIFFORD_STRESS (critical)
Iron/law FAIL — investigation before any promote or pose bind.
Mandatory: hwatom-investigate · dual physics pair · no sandwich for pose.
TABU: py GP engine · receipt theater · silent opcode misuse
State: results/platform_bpass/chip/CLIFFORD_STRESS_STATE_v1.json"""


def _load_receipt(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _sim_fail(receipt: dict[str, Any]) -> bool:
    for b in receipt.get("sim_backends") or []:
        if b.get("status") == "FAIL":
            return True
    return False


def evaluate(*, prompt: str = "", refresh_law: bool = True) -> dict[str, Any]:
    triggers: list[str] = []
    level = "none"

    p5 = _load_receipt(_RECEIPTS["p5"])
    p6 = _load_receipt(_RECEIPTS["p6"])
    lc2 = _load_receipt(_RECEIPTS["lc2"])
    dual = _load_receipt(_RECEIPTS["dual_p5"])

    if p5.get("verdict") not in ("P5_PASS",):
        triggers.append(f"p5_verdict={p5.get('verdict', 'missing')}")
    if p6.get("verdict") not in ("P6_PASS",):
        triggers.append(f"p6_verdict={p6.get('verdict', 'missing')}")
    if lc2.get("verdict") not in ("LC2_POSE_PROBE_PASS",):
        triggers.append(f"lc2_verdict={lc2.get('verdict', 'missing')}")
    if dual.get("verdict") == "DUAL_PHYSICS_FAIL":
        triggers.append("dual_physics_FAIL")

    if _sim_fail(p5) or _sim_fail(p6):
        triggers.append("sim_backend_FAIL")

    iron_loop = (lc2.get("honesty") or {}).get("iron_rtl_in_loop")
    if iron_loop is False:
        triggers.append("iron_rtl_not_in_loop")

    law_failed: list[str] = []
    if refresh_law:
        import sys

        if str(_REPO) not in sys.path:
            sys.path.insert(0, str(_REPO))
        try:
            from scripts.chip.clifford_op_law_v0 import check_law_artifacts

            for s in check_law_artifacts():
                if not s["pass"]:
                    law_failed.append(s["id"])
        except ImportError:
            law_failed.append("law_import_fail")

    if law_failed:
        triggers.append("law_spikes:" + ",".join(law_failed))

    if prompt and _SANDWICH_POSE_TABU.search(prompt):
        triggers.append("prompt_sandwich_pose_TABU")
        level = "critical"
    elif any(t.startswith("dual_physics_FAIL") or t.startswith("sim_backend") or t.startswith("law_spikes") for t in triggers):
        level = "critical"
    elif triggers:
        level = "warn"

    if level == "none" and triggers:
        level = "warn"

    state: dict[str, Any] = {
        "state_id": "CLIFFORD_STRESS_STATE_v1",
        "stress_level": level,
        "mode_recommendation": "CLIFFORD_STRESS" if level != "none" else "WORK",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "triggers": triggers,
        "law_failed": law_failed,
        "receipts": {k: str(v.name) for k, v in _RECEIPTS.items()},
        "inject": INJECT_CRITICAL if level == "critical" else (INJECT_WARN if level == "warn" else ""),
    }

    _CHIP.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def prompt_context(prompt: str) -> str:
    state = evaluate(prompt=prompt)
    if state["stress_level"] == "none":
        return ""
    if state["stress_level"] == "critical":
        return state["inject"]
    if _CLIFFORD_PROMPT.search(prompt):
        return state["inject"]
    return ""


def session_context() -> str:
    state = evaluate(prompt="")
    if state["stress_level"] == "critical":
        return state["inject"]
    return ""


if __name__ == "__main__":
    import sys

    s = evaluate(prompt=" ".join(sys.argv[1:]))
    print(json.dumps({"stress_level": s["stress_level"], "triggers": s["triggers"]}, indent=2))
