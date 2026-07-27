"""Appendage OS dual subagent review — deterministic spikes + merge slot for subs A/B.

Replaces human AE+ canon merge gate. Sub verdicts merged via merge_sub_reviews().
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_MOON = _REPO / "results" / "platform_bpass" / "moon"
_ROBOT = _REPO / "results" / "platform_bpass" / "robot"
_SCOPE = _REPO / "fixtures" / "robot" / "appendage_dual_review_scope_v1.json"
_CANON = "docs/agent_workflow/APPENDAGE_DUAL_REVIEW_MODES_V1.md"
_PLAN = _REPO / "docs" / "agent_workflow" / "APPENDAGE_KINEMATICS_OS_PLAN_20260712_V1.md"
_FACTORY_RECEIPT = _MOON / "ROBOT_APPENDAGE_OS_FACTORY_SIGNOFF_RECEIPT_v1.json"
_PATCH = _ROBOT / "kinematic_chain_ir_patch_v1.json"
_CANON_IR = _REPO / "fixtures" / "robot" / "kinematic_chain_ir_v0.json"

SUB_KINEMATICS_PATH = _MOON / "APPENDAGE_SUB_KINEMATICS_AUDITOR_v1.json"
SUB_IRON_SERVO_PATH = _MOON / "APPENDAGE_SUB_IRON_SERVO_AUDITOR_v1.json"
_PAIR_BENCHMARK = _MOON / "APPENDAGE_DUAL_REVIEW_PAIR_BENCHMARK_v1.json"

PAIR_PRESETS: dict[str, dict[str, str]] = {
    "pair_composer25_composer25": {
        "sub_a_model": "composer-2.5",
        "sub_b_model": "composer-2.5",
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_sub_review(path: Path, doc: dict[str, Any], *, write: bool = True) -> dict[str, Any]:
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def load_sub_reviews_from_disk() -> dict[str, dict[str, Any] | None]:
    out: dict[str, dict[str, Any] | None] = {"kinematics": None, "iron_servo": None}
    if SUB_KINEMATICS_PATH.is_file():
        out["kinematics"] = _load_json(SUB_KINEMATICS_PATH)
    if SUB_IRON_SERVO_PATH.is_file():
        out["iron_servo"] = _load_json(SUB_IRON_SERVO_PATH)
    return out


def parse_sub_verdict_blob(text: str) -> dict[str, Any]:
    """Extract JSON object from subagent markdown or raw JSON."""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    brace = re.search(r"(\{.*\})", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(1))
    raise ValueError("no JSON verdict in subagent output")


def _spike_checks(phase: str, *, from_factory: bool = False) -> list[dict[str, Any]]:
    spikes: list[dict[str, Any]] = []

    spikes.append(
        {
            "id": "scope_fixture",
            "severity": "CRITICAL",
            "pass": _SCOPE.is_file(),
            "detail": str(_SCOPE),
        }
    )
    spikes.append(
        {
            "id": "plan_deferred_ladder",
            "severity": "MEDIUM",
            "pass": _PLAN.is_file() and "Deferred staging ladder" in _PLAN.read_text(encoding="utf-8"),
            "detail": "APPENDAGE_KINEMATICS_OS_PLAN deferred ladder documented",
        }
    )
    if from_factory:
        factory_pass = True
        factory_detail = "skipped recursive factory spike (AF gate inside signoff)"
    elif _FACTORY_RECEIPT.is_file():
        fac = _load_json(_FACTORY_RECEIPT)
        checks = dict(fac.get("checks") or {})
        sans_af = {k: v for k, v in checks.items() if k != "G_AF_dual_sub_review"}
        factory_pass = fac.get("verdict") == "ROBOT_APPENDAGE_OS_FACTORY_SIGNOFF_PASS" or all(sans_af.values())
        factory_detail = f"receipt sans_AF={sum(sans_af.values())}/{len(sans_af)}"
    else:
        factory_pass = False
        factory_detail = "no factory receipt on disk"
    spikes.append(
        {
            "id": "factory_signoff_receipt",
            "severity": "CRITICAL",
            "pass": factory_pass,
            "detail": factory_detail,
        }
    )
    spikes.append(
        {
            "id": "pytest_appendage_suite",
            "severity": "CRITICAL",
            "pass": len(list((_REPO / "tests").glob("test_appendage_os_*.py"))) >= 8,
            "detail": "test_appendage_os_*.py count >= 8",
        }
    )
    spikes.append(
        {
            "id": "registry_canon_triplet",
            "severity": "MEDIUM",
            "pass": _CANON_IR.is_file()
            and len(_load_json(_CANON_IR).get("chains") or {}) >= (6 if phase == "POST_AK_AQ" else 3),
            "detail": f"kinematic_chain_ir_v0 has >= {6 if phase == 'POST_AK_AQ' else 3} canonical chains",
        }
    )
    patch_ok = True
    patch_detail = "no patch yet (ok for staging)"
    if _PATCH.is_file():
        patch = _load_json(_PATCH)
        chains = patch.get("chains") or {}
        patch_ok = bool(chains) and not any(c.get("product_ready") for c in chains.values())
        patch_detail = "patch exists · no product_ready flags"
    spikes.append(
        {
            "id": "patch_no_product_ready",
            "severity": "CRITICAL",
            "pass": patch_ok,
            "detail": patch_detail,
        }
    )
    try:
        from production_gate.kinematic_chain_ir_v1 import clear_chain_overlay

        clear_chain_overlay()
        overlay_spike = True
    except Exception as exc:  # noqa: BLE001 — spike honesty
        overlay_spike = False
        patch_detail = str(exc)
    spikes.append(
        {
            "id": "overlay_clear_hygiene",
            "severity": "MEDIUM",
            "pass": overlay_spike,
            "detail": "clear_chain_overlay callable",
        }
    )
    plan_text = _PLAN.read_text(encoding="utf-8") if _PLAN.is_file() else ""
    spikes.append(
        {
            "id": "honesty_not_universal_os",
            "severity": "MEDIUM",
            "pass": "not_universal_robot_os" in plan_text
            or "claim universal robot os" in plan_text.lower()
            or "not universal" in plan_text.lower(),
            "detail": "plan names non-universal OS boundary",
        }
    )
    spikes.append(
        {
            "id": "dual_review_personas",
            "severity": "LOW",
            "pass": (_REPO / "agents/appendage-kinematics-auditor/instructions.md").is_file()
            and (_REPO / "agents/appendage-iron-servo-auditor/instructions.md").is_file(),
            "detail": "agent persona instructions present",
        }
    )
    if phase == "POST_AK_AQ":
        charter = _REPO / "fixtures" / "robot" / "appendage_body_phase_charter_v0.json"
        phases = (_load_json(charter).get("phases") or {}) if charter.is_file() else {}
        ar_aw = {k: v for k, v in phases.items() if k in ("AR", "AS", "AT", "AU", "AV", "AW")}
        spikes.extend(
            [
                {
                    "id": "post_ak_aq_charter_ar_aw",
                    "severity": "CRITICAL",
                    "pass": len(ar_aw) == 6 and all(v.get("status") == "PASS" for v in ar_aw.values()),
                    "detail": "charter AR→AW phases PASS",
                },
                {
                    "id": "post_ak_aq_body_modules",
                    "severity": "MEDIUM",
                    "pass": all(
                        (_REPO / "production_gate" / f"{v.get('engine')}.py").is_file()
                        for v in ar_aw.values()
                        if v.get("engine")
                    ),
                    "detail": "AR→AW engine modules on disk",
                },
                {
                    "id": "post_ak_aq_hexapod_parity",
                    "severity": "MEDIUM",
                    "pass": (_REPO / "production_gate/hexapod_planar_urdf_se3_parity_v1.py").is_file(),
                    "detail": "AS hexapod planar/URDF parity module",
                },
            ]
        )
    if phase == "POST_BA":
        charter = _REPO / "fixtures" / "robot" / "appendage_body_phase_charter_v0.json"
        phases = (_load_json(charter).get("phases") or {}) if charter.is_file() else {}
        bb_bf = {k: v for k, v in phases.items() if k in ("BB", "BC", "BD", "BE", "BF")}
        spikes.extend(
            [
                {
                    "id": "post_ba_charter_bb_bf",
                    "severity": "CRITICAL",
                    "pass": len(bb_bf) == 5 and all(v.get("status") == "PASS" for v in bb_bf.values()),
                    "detail": "charter BB→BF phases PASS",
                },
                {
                    "id": "post_ba_dual_region_fixture",
                    "severity": "MEDIUM",
                    "pass": (_REPO / "fixtures/robot/full_body_dual_region_lunar_earth_v1.json").is_file(),
                    "detail": "BC dual-region full body fixture",
                },
                {
                    "id": "post_ba_earth_lunar_motion",
                    "severity": "MEDIUM",
                    "pass": (_REPO / "production_gate/earth_lunar_motion_compose_v1.py").is_file(),
                    "detail": "BE earth-lunar motion compose module",
                },
            ]
        )
    return spikes


def _merge_verdict(
    spikes: list[dict[str, Any]],
    sub_kinematics: dict[str, Any] | None,
    sub_iron: dict[str, Any] | None,
) -> str:
    critical = [s for s in spikes if s["severity"] == "CRITICAL" and not s["pass"]]
    if critical:
        return "APPENDAGE_DUAL_REVIEW_FAIL"
    subs = [sub_kinematics, sub_iron]
    if any(s and str(s.get("verdict", "")).upper() == "FAIL" for s in subs):
        return "APPENDAGE_DUAL_REVIEW_FAIL"
    if any(s and str(s.get("verdict", "")).upper() == "WARN" for s in subs):
        return "APPENDAGE_DUAL_REVIEW_WARN"
    if (
        sub_kinematics
        and sub_iron
        and str(sub_kinematics.get("verdict", "")).upper() == "PASS"
        and str(sub_iron.get("verdict", "")).upper() == "PASS"
    ):
        return "APPENDAGE_DUAL_REVIEW_PASS"
    return "APPENDAGE_DUAL_REVIEW_PENDING"


def can_promote_registry_patch(merged_verdict: str) -> bool:
    return merged_verdict in ("APPENDAGE_DUAL_REVIEW_PASS", "APPENDAGE_DUAL_REVIEW_WARN")


def merge_sub_reviews(
    *,
    phase: str = "AE_PLUS",
    sub_kinematics: dict[str, Any] | None,
    sub_iron_servo: dict[str, Any] | None,
    pair_id: str = "pair_composer25_composer25",
    write: bool = True,
    from_factory: bool = False,
) -> dict[str, Any]:
    spikes = _spike_checks(phase, from_factory=from_factory)
    verdict = _merge_verdict(spikes, sub_kinematics, sub_iron_servo)

    receipt: dict[str, Any] = {
        "receipt_id": f"APPENDAGE_DUAL_REVIEW_{phase}_RECEIPT_v1",
        "bind_id": f"APPENDAGE_DUAL_REVIEW_{phase}_BIND_v1",
        "verdict": verdict,
        "phase": phase,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canon": [_CANON],
        "scope_fixture": str(_SCOPE),
        "deterministic_spikes": spikes,
        "sub_kinematics_auditor": sub_kinematics,
        "sub_iron_servo_auditor": sub_iron_servo,
        "pair_id": pair_id,
        "ae_plus_gate": {
            "blocked": verdict in ("APPENDAGE_DUAL_REVIEW_FAIL", "APPENDAGE_DUAL_REVIEW_PENDING"),
            "warn_only": verdict == "APPENDAGE_DUAL_REVIEW_WARN",
            "operator_waive": "promote patch after WARN · subs filed",
            "replaces": "human canon merge review",
        },
        "sub_slots": {
            "kinematics": str(SUB_KINEMATICS_PATH),
            "iron_servo": str(SUB_IRON_SERVO_PATH),
        },
    }

    if write:
        _MOON.mkdir(parents=True, exist_ok=True)
        out = _MOON / f"APPENDAGE_DUAL_REVIEW_{phase}_RECEIPT_v1.json"
        bind = _MOON / f"APPENDAGE_DUAL_REVIEW_{phase}_BIND_v1.json"
        out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        bind.write_text(json.dumps({**receipt, "bind_role": "APPENDAGE_DUAL_REVIEW"}, indent=2) + "\n", encoding="utf-8")
        _append_benchmark(receipt)

    return receipt


def _append_benchmark(receipt: dict[str, Any]) -> None:
    row = {
        "timestamp_utc": receipt["timestamp_utc"],
        "phase": receipt["phase"],
        "pair_id": receipt.get("pair_id"),
        "merged_verdict": receipt["verdict"],
        "sub_a_verdict": (receipt.get("sub_kinematics_auditor") or {}).get("verdict"),
        "sub_b_verdict": (receipt.get("sub_iron_servo_auditor") or {}).get("verdict"),
        "operator_notes": None,
    }
    if _PAIR_BENCHMARK.is_file():
        data = _load_json(_PAIR_BENCHMARK)
    else:
        data = {"benchmark_id": "APPENDAGE_DUAL_REVIEW_PAIR_BENCHMARK_v1", "runs": []}
    data["runs"].append(row)
    _PAIR_BENCHMARK.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_appendage_dual_review(*, phase: str = "AE_PLUS", write: bool = True, from_factory: bool = False) -> dict[str, Any]:
    """Load sub JSON from disk if present, merge with spikes."""
    subs = load_sub_reviews_from_disk()
    return merge_sub_reviews(
        phase=phase,
        sub_kinematics=subs.get("kinematics"),
        sub_iron_servo=subs.get("iron_servo"),
        write=write,
        from_factory=from_factory,
    )


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--phase", default="AE_PLUS")
    args = p.parse_args()
    r = run_appendage_dual_review(phase=args.phase)
    print(json.dumps({"verdict": r["verdict"], "spikes": r["deterministic_spikes"]}, indent=2))
