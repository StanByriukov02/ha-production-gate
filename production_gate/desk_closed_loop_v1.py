"""Desk closed-loop v1 — named falsifiers on PolicyPort dual probe.

Loop: policy/port → one-tick actuation → world proxy (cursor/sinkage) → KPI.
Falsifiers are physics consequence (aligned vs diverged), not only demo slogans.
Classic traverse/recover still recorded when that pattern appears.

TABU: MEASURED · Isaac GT · product_ready · claim full control stack.
"""
from __future__ import annotations

from typing import Any

PROOF_TIER = "DESK_CLOSED_LOOP_SLICE"
SCHEMA = "ha_desk_closed_loop_v1"


def build_closed_loop_v1(
    *,
    condition: str,
    dual: dict[str, Any],
    actuation_truth: dict[str, Any],
    foreign: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Receipt for one condition probe — thermometer for consequence, not theater."""
    stub_cmd = str(dual.get("stub_command") or "")
    plan_cmd = str(dual.get("regolith_command") or dual.get("planner_command") or "")
    diverged = bool(dual.get("diverged"))
    stub_leg = (actuation_truth.get("stub") or {}) if isinstance(actuation_truth, dict) else {}
    plan_leg = (actuation_truth.get("planner") or {}) if isinstance(actuation_truth, dict) else {}
    sinkage = None
    before = stub_leg.get("world_before") if isinstance(stub_leg, dict) else None
    if isinstance(before, dict) and before.get("sinkage_mm") is not None:
        sinkage = before.get("sinkage_mm")

    # Generalized BYO-safe falsifiers
    f_hostile_div = condition == "hostile" and diverged and stub_cmd != plan_cmd and bool(stub_cmd)
    f_safe_align = (
        condition == "safe"
        and (not diverged)
        and stub_cmd == plan_cmd
        and bool(stub_cmd)
    )
    # Classic demo pattern (kept as named proof when it matches)
    f_hostile_classic = (
        condition == "hostile"
        and diverged
        and stub_cmd == "traverse"
        and plan_cmd == "recover"
    )
    f_safe_classic = (
        condition == "safe"
        and (not diverged)
        and stub_cmd == plan_cmd
        and stub_cmd in ("traverse", "idle")
    )

    stub_delta = float(stub_leg.get("cursor_delta_m") or 0.0) if isinstance(stub_leg, dict) else 0.0
    plan_delta = float(plan_leg.get("cursor_delta_m") or 0.0) if isinstance(plan_leg, dict) else 0.0

    if condition == "hostile":
        active_ok = f_hostile_div
        active_id = (
            "F_hostile_stub_traverse_vs_planner_recover"
            if f_hostile_classic
            else "F_hostile_stub_planner_diverged"
        )
    else:
        active_ok = f_safe_align
        active_id = (
            "F_safe_stub_planner_aligned_traverse"
            if f_safe_classic
            else "F_safe_stub_planner_aligned"
        )

    falsifiers = {
        "F_hostile_stub_planner_diverged": f_hostile_div if condition == "hostile" else None,
        "F_hostile_stub_traverse_vs_planner_recover": f_hostile_classic
        if condition == "hostile"
        else None,
        "F_safe_stub_planner_aligned": f_safe_align if condition == "safe" else None,
        "F_safe_stub_planner_aligned_traverse": f_safe_classic if condition == "safe" else None,
    }

    return {
        "schema": SCHEMA,
        "proof_tier": PROOF_TIER,
        "condition": condition,
        "loop": {
            "policy_in": "policy_port_or_desk_stub",
            "command_stub": stub_cmd,
            "command_planner": plan_cmd,
            "state_proxy": "cursor_m + sinkage_mm",
            "foreign_recorded": foreign is not None,
        },
        "kpi": {
            "diverged": diverged,
            "sinkage_mm": sinkage,
            "stub_cursor_delta_m": round(stub_delta, 4),
            "planner_cursor_delta_m": round(plan_delta, 4),
            "any_world_delta": bool(abs(stub_delta) > 1e-6 or abs(plan_delta) > 1e-6),
        },
        "falsifiers": falsifiers,
        "active_falsifier": active_id,
        "ok": bool(active_ok),
        "honesty": {
            "not_measured": True,
            "sim_slice": True,
            "not_full_control_stack": True,
            "byo_generalized": True,
            "note": "aligned(safe) / diverged(hostile) — classic traverse/recover when present",
        },
    }


def latest_closed_loops(project_id: str) -> dict[str, dict[str, Any]]:
    """Latest closed_loop_v1 per condition from persisted runs."""
    from production_gate.artifact_existence_law_v1 import load_run_docs

    latest: dict[str, dict[str, Any]] = {}
    for doc in load_run_docs(project_id):
        cond = str(doc.get("condition") or "")
        loop = doc.get("closed_loop_v1")
        if cond not in ("safe", "hostile") or not isinstance(loop, dict):
            continue
        prev = latest.get(cond)
        if prev is None or str(doc.get("timestamp_utc") or "") >= str(
            (prev.get("_run_ts") or "")
        ):
            row = dict(loop)
            row["_run_id"] = doc.get("run_id")
            row["_run_ts"] = doc.get("timestamp_utc")
            latest[cond] = row
    return latest


def require_closed_loop_consequence(project_id: str) -> dict[str, Any]:
    """Scarce gate layer: both conditions must carry a PASSING closed_loop_v1."""
    loops = latest_closed_loops(project_id)
    errors: list[str] = []
    for cond in ("safe", "hostile"):
        loop = loops.get(cond)
        if not loop:
            errors.append(
                f"missing_closed_loop_v1:{cond} — re-run {cond} probe after closed_loop_v1 ship"
            )
            continue
        if not loop.get("ok"):
            errors.append(
                f"closed_loop_v1_FAIL:{cond}:{loop.get('active_falsifier')}"
            )
    if errors:
        raise ValueError(
            "SCARCE_CONSEQUENCE_GATE FAIL — Dual closed_loop must PASS before emit: "
            + "; ".join(errors)
        )
    return {
        "ok": True,
        "schema": "ha_scarce_consequence_gate_v1",
        "loops": {
            k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
            for k, v in loops.items()
        },
        "run_ids": {k: v.get("_run_id") for k, v in loops.items()},
    }
