"""Clifford ALU op semantics law — machine-checkable FAIL gate.

Canon: docs/agent_workflow/CLIFFORD_OP_SEMANTICS_LAW_V1.md
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

_REPO = Path(__file__).resolve().parents[2]
_LAW_MD = _REPO / "docs" / "agent_workflow" / "CLIFFORD_OP_SEMANTICS_LAW_V1.md"
_VECTORS = _REPO / "fixtures" / "chip" / "clifford_alu_vectors_v1.json"
_LC2_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_LC2_BENCH_POSE_PROBE_RECEIPT_v1.json"

LAW_ID = "CLIFFORD_OP_SEMANTICS_LAW_V1"

POSE_TABU_OPCODES = frozenset({"V_SANDWICH", "SANDWICH", "001"})

LC2_FALSIFIER = {
    "geo_prod_chain_rmse_m": 0.002,
    "sandwich_rmse_m_min": 0.1,
    "theta_rad": 0.7853981633974483,
}


class PoseTabuViolation(RuntimeError):
    """Raised when pose path uses SANDWICH opcode."""


def law_doc_present() -> bool:
    return _LAW_MD.is_file()


def vectors_law_anchor() -> dict[str, Any] | None:
    if not _VECTORS.is_file():
        return None
    data = json.loads(_VECTORS.read_text(encoding="utf-8"))
    return data.get("op_semantics_law")


def assert_pose_transform(
    transform: str,
    *,
    context: str = "",
    allow_non_pose_sandwich: bool = False,
) -> None:
    """FAIL if pose transform names SANDWICH without explicit non-pose waiver."""
    t = transform.upper()
    if allow_non_pose_sandwich:
        return
    if "POSE" in t or "LANDMARK" in t or "JOINT" in t or "RIGID" in t:
        for bad in POSE_TABU_OPCODES:
            if bad in t:
                raise PoseTabuViolation(
                    f"{context}: pose path must use GEO_PROD chain, not SANDWICH ({transform})"
                )
    if t.strip() in POSE_TABU_OPCODES or "SANDWICH" in t and "NON_POSE" not in t and "POSE" in context.upper():
        raise PoseTabuViolation(f"{context}: SANDWICH forbidden for pose ({transform})")


def recommended_pose_transform() -> str:
    return "gp(gp(R,p), reverse(R))"


def _lc2_falsifier_ok() -> tuple[bool, str]:
    if not _LC2_RECEIPT.is_file():
        return False, "LC2 receipt missing"
    r = json.loads(_LC2_RECEIPT.read_text(encoding="utf-8"))
    phys = r.get("physics", {})
    checks = {c["id"]: c for c in r.get("checks", [])}
    iron_pose_ok = checks.get("iron_rtl_pose_rmse", {}).get("pass") and checks.get(
        "iron_oracle_parity", {}
    ).get("pass")
    ok = (
        phys.get("rmse_m", 1.0) < LC2_FALSIFIER["geo_prod_chain_rmse_m"]
        and phys.get("sandwich_rmse_m", 0.0) > LC2_FALSIFIER["sandwich_rmse_m_min"]
        and checks.get("sandwich_not_rigid_motion", {}).get("pass")
        and (iron_pose_ok or checks.get("geo_prod_pose_rmse", {}).get("pass"))
    )
    detail = f"geo_rmse={phys.get('rmse_m')} sw_rmse={phys.get('sandwich_rmse_m')}"
    return ok, detail


def check_law_artifacts() -> list[dict[str, Any]]:
    """Deterministic spikes for dual physics / pytest."""
    spikes: list[dict[str, Any]] = []

    tabu_ok = False
    tabu_detail = "law doc missing"
    if law_doc_present():
        anchor = vectors_law_anchor()
        try:
            if anchor:
                assert_pose_transform(
                    anchor.get("pose_transform", ""),
                    context="vectors op_semantics_law",
                )
            lc2_ok, lc2_detail = _lc2_falsifier_ok()
            tabu_ok = lc2_ok
            tabu_detail = f"pose_transform ok · {lc2_detail}"
        except PoseTabuViolation as exc:
            tabu_detail = str(exc)
    spikes.append(
        {
            "id": "sandwich_pose_tabu",
            "severity": "CRITICAL",
            "pass": tabu_ok,
            "detail": tabu_detail,
        }
    )

    anchor = vectors_law_anchor()
    spikes.append(
        {
            "id": "vectors_op_semantics_law",
            "severity": "HIGH",
            "pass": anchor is not None and anchor.get("law_id") == LAW_ID,
            "detail": "fixtures/chip/clifford_alu_vectors_v1.json op_semantics_law",
        }
    )

    lc2_ok = False
    lc2_detail = "missing"
    if _LC2_RECEIPT.is_file():
        lc2_ok, lc2_detail = _lc2_falsifier_ok()
    spikes.append(
        {
            "id": "lc2_pose_falsifier_receipt",
            "severity": "HIGH",
            "pass": lc2_ok,
            "detail": lc2_detail,
        }
    )

    return spikes


def merge_law_spikes(spikes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = {s["id"] for s in spikes}
    for s in check_law_artifacts():
        if s["id"] not in existing:
            spikes.append(s)
    return spikes
