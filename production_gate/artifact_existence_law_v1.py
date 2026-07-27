"""Artifact Existence Law v1 — Dual Probe + Energy + Physics + Fuse.

Law: pack/action does not exist without Safe∧Hostile + actuation_truth
     + balanced energy_claim + coherent physics_gate (no apoptosis)
     + intact silicon fuse + body identity when body present.

**Oracle:** Rust `ha-artifact-law` (Python = glue only).

TABU: product_ready · Isaac GT · skip Safe · Python as existence oracle.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROOF_TIER = "ARTIFACT_EXISTENCE_LAW_SLICE"
LAW_ID = "LIE_MUST_COST_PHYSICALLY_H8_H7_H6_IRON"
REQUIRED_CONDITIONS = ("safe", "hostile")


def build_actuation_truth(dual_block: dict[str, Any], dual: dict[str, Any]) -> dict[str, Any]:
    """Command vs world_delta proxy (cursor) for stub and planner legs."""
    stub = dual_block.get("stub") or {}
    reg = dual_block.get("regolith") or {}
    stub_tick = stub.get("tick") or {}
    reg_tick = reg.get("tick") or {}
    stub_cmd = str((stub.get("proposal") or {}).get("command") or dual.get("stub_command") or "")
    reg_cmd = str((reg.get("proposal") or {}).get("command") or dual.get("regolith_command") or "")
    physics = dual_block.get("physics") or {}

    def _leg(cmd: str, tick: dict[str, Any], cursor_delta: float, advanced: bool) -> dict[str, Any]:
        before = tick.get("cursor_before")
        after = tick.get("cursor_after")
        delta = float(cursor_delta) if cursor_delta is not None else 0.0
        return {
            "command": cmd,
            "world_before": {"cursor_m": before, "sinkage_mm": physics.get("sinkage_mm")},
            "world_after": {"cursor_m": after, "sinkage_mm": physics.get("sinkage_mm")},
            "cursor_delta_m": round(delta, 4),
            "delta_nonzero": abs(delta) > 1e-6,
            "advanced": bool(advanced),
            "held": bool(tick.get("governance_hold")) or (not advanced and cmd in ("recover", "hold", "idle")),
        }

    stub_leg = _leg(
        stub_cmd,
        stub_tick,
        float(stub.get("cursor_delta_m") or 0.0),
        bool(stub.get("advanced")),
    )
    reg_leg = _leg(
        reg_cmd,
        reg_tick,
        float(reg.get("cursor_delta_m") or 0.0),
        bool(reg.get("advanced")),
    )
    return {
        "schema": "actuation_truth_v1",
        "condition_id": dual_block.get("condition_id") or dual.get("condition_id"),
        "stub": stub_leg,
        "planner": reg_leg,
        "command_equals_world_change": False,  # always false as philosophy — we record legs
        "any_world_delta": bool(stub_leg["delta_nonzero"] or reg_leg["delta_nonzero"]),
        "epsilon": {
            "ε_inject_not_measured": True,
            "ε_delta_is_proxy": True,
            "ε_soft_not_iron": True,
        },
        "honesty": {
            "not_measured": True,
            "sim_slice": True,
            "note": "world_delta is desk cursor/sinkage proxy — not field dynamics",
        },
    }


def _runs_dir_for_project(project_id: str) -> Path:
    from production_gate.robot_project_desk_v1 import project_dir

    return project_dir(project_id) / "runs"


def load_run_docs(project_id: str) -> list[dict[str, Any]]:
    runs_dir = _runs_dir_for_project(project_id)
    if not runs_dir.is_dir():
        return []
    docs: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("run-*.json")):
        try:
            docs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return docs


def _latest_by_condition(docs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for doc in docs:
        cond = str(doc.get("condition") or "")
        if cond not in REQUIRED_CONDITIONS:
            continue
        prev = latest.get(cond)
        if prev is None or str(doc.get("timestamp_utc") or "") >= str(prev.get("timestamp_utc") or ""):
            latest[cond] = doc
    return latest


def _leg_nonhollow(leg: Any, *, role: str, condition: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(leg, dict):
        return [f"hollow_actuation_truth:{condition}:{role}:not_object"]
    cmd = str(leg.get("command") or "").strip()
    if not cmd:
        errors.append(f"hollow_actuation_truth:{condition}:{role}:empty_command")
    before = leg.get("world_before")
    after = leg.get("world_after")
    if not isinstance(before, dict) or "cursor_m" not in before:
        errors.append(f"hollow_actuation_truth:{condition}:{role}:missing_world_before")
    if not isinstance(after, dict) or "cursor_m" not in after:
        errors.append(f"hollow_actuation_truth:{condition}:{role}:missing_world_after")
    if "cursor_delta_m" not in leg or "delta_nonzero" not in leg:
        errors.append(f"hollow_actuation_truth:{condition}:{role}:missing_delta_fields")
    return errors


def _actuation_truth_nonhollow(at: Any, *, condition: str) -> list[str]:
    if not isinstance(at, dict) or at.get("schema") != "actuation_truth_v1":
        return [f"missing_actuation_truth:{condition}"]
    errors: list[str] = []
    errors.extend(_leg_nonhollow(at.get("stub"), role="stub", condition=condition))
    errors.extend(_leg_nonhollow(at.get("planner"), role="planner", condition=condition))
    # Hostile must show a real world-delta on at least one leg (stub advance or planner move)
    # OR an explicit hold with zero delta on planner while stub advanced — captured by any_world_delta
    if condition == "hostile" and not bool(at.get("any_world_delta")):
        # allow planner-held with stub delta via any_world_delta; if forge omitted it, fail
        stub = at.get("stub") if isinstance(at.get("stub"), dict) else {}
        planner = at.get("planner") if isinstance(at.get("planner"), dict) else {}
        if not (stub.get("delta_nonzero") or planner.get("delta_nonzero") or planner.get("held")):
            errors.append(f"hollow_actuation_truth:{condition}:no_delta_or_hold")
    return errors


def evaluate_artifact_existence(
    project_id: str,
    *,
    require_iron: bool = False,
    reject_soft_stub: bool = False,
) -> dict[str, Any]:
    """Return law verdict for a project. Oracle = Rust ha-artifact-law. Does not raise."""
    from production_gate.artifact_law_v1 import verify_project
    from production_gate.robot_project_desk_v1 import project_dir
    from production_gate.silicon_fuse_v1 import ensure_silicon_fuse

    # Ensure fuse file exists so root verify is well-formed (C ensure is idempotent)
    try:
        ensure_silicon_fuse(project_id)
    except (FileNotFoundError, RuntimeError):
        pass

    try:
        receipt = verify_project(
            project_id,
            allow_fail=True,
            require_iron=require_iron,
            reject_soft_stub=reject_soft_stub,
        )
    except FileNotFoundError as exc:
        return {
            "law_id": LAW_ID,
            "proof_tier": PROOF_TIER,
            "ok": False,
            "verdict": "FAIL",
            "errors": [f"artifact_law_oracle_missing:{exc}"],
            "conditions_present": [],
            "run_ids": {},
            "honesty": {
                "not_measured": True,
                "sim_slice": True,
                "not_product_ready": True,
                "python_not_oracle": True,
                "law_oracle": "ha-artifact-law",
            },
        }

    out: dict[str, Any] = {
        "law_id": str(receipt.get("law_id") or LAW_ID),
        "proof_tier": PROOF_TIER,
        "ok": bool(receipt.get("ok")),
        "verdict": str(receipt.get("verdict") or ("PASS" if receipt.get("ok") else "FAIL")),
        "errors": list(receipt.get("errors") or []),
        "conditions_present": list(receipt.get("conditions_present") or []),
        "run_ids": dict(receipt.get("run_ids") or {}),
        "honesty": dict(receipt.get("honesty") or {}),
        "oracles": dict(receipt.get("oracles") or {}),
        "iron": dict(receipt.get("iron") or {}),
        "require_iron": require_iron,
        "law_receipt_path": str(project_dir(project_id) / "LAW_RECEIPT_v1.json"),
    }
    # Pack emit gate (SCARCE + closed_loop + soft-stub anti-lie) — separate from Dual law.
    # UI must not conflate "Dual PASS" with "export/bundle allowed".
    pack_emit: dict[str, Any]
    soft_present = _project_has_soft_stub_iron(project_id)
    try:
        from production_gate.desk_closed_loop_v1 import require_closed_loop_consequence

        cl = require_closed_loop_consequence(project_id)
        pack_ok = bool(out["ok"]) and bool(cl.get("ok")) and not soft_present
        pack_errors: list[str] = []
        if soft_present:
            pack_errors.append(
                "soft_stub IRON present — scarce emit refused (soft ≠ OTP). "
                "Remove IRON_ATTESTATION_v1.json for Dual-only local emit, "
                "or provide OTP/HSM."
            )
        pack_emit = {
            "ok": pack_ok,
            "closed_loop_ok": bool(cl.get("ok")),
            "dual_law_ok": bool(out["ok"]),
            "soft_stub_blocks_emit": soft_present,
            "errors": pack_errors,
        }
    except ValueError as exc:
        pack_emit = {
            "ok": False,
            "closed_loop_ok": False,
            "dual_law_ok": bool(out["ok"]),
            "soft_stub_blocks_emit": soft_present,
            "errors": [str(exc)]
            + (
                [
                    "soft_stub IRON present — scarce emit refused (soft ≠ OTP)."
                ]
                if soft_present
                else []
            ),
        }
    out["pack_emit"] = pack_emit
    if soft_present:
        out.setdefault("iron", {})
        if isinstance(out["iron"], dict):
            out["iron"] = dict(out["iron"])
            out["iron"].setdefault("backend", "soft_stub")
            out["iron"]["soft_neq_otp"] = True
            out["iron"]["blocks_scarce_emit"] = True
    honesty = out["honesty"]
    honesty.setdefault("law_oracle", "ha-artifact-law")
    honesty.setdefault("python_not_oracle", True)
    honesty.setdefault("body_oracle", "ha-body-identity")
    honesty.setdefault("energy_oracle", "ha-energy-ledger")
    honesty.setdefault("physics_oracle", "ha-physics-gate")
    honesty.setdefault("fuse_oracle", "ha-silicon-fuse")
    honesty.setdefault("iron_oracle", "ha-iron-attestation")
    honesty["pack_emit_is_not_dual_law"] = True
    honesty["soft_stub_neq_otp"] = True
    return out


def require_artifact_existence(
    project_id: str,
    *,
    require_iron: bool | None = None,
    reject_soft_stub: bool | None = None,
    require_closed_loop: bool | None = None,
) -> dict[str, Any]:
    """Hard scarce gate — Dual∧Law (+ closed_loop) + iron anti-lie.

    Reliability default (years-forward):
      If IRON_ATTESTATION_v1.json is soft_stub → scarce FAIL (soft ≠ OTP).
      No IRON file → emit still allowed after Dual∧closed_loop (local gate).
    Env:
      HA_SCARCE_REQUIRE_IRON=1
      HA_SCARCE_REJECT_SOFT_STUB=1|0  (override auto soft-stub refuse)
      HA_SCARCE_REQUIRE_CLOSED_LOOP=0  (debug only)
    """
    import os

    from production_gate.artifact_law_v1 import ArtifactLawError, require_rust_artifact_law
    from production_gate.silicon_fuse_v1 import ensure_silicon_fuse

    if require_iron is None:
        require_iron = os.environ.get("HA_SCARCE_REQUIRE_IRON", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
    if reject_soft_stub is None:
        raw = os.environ.get("HA_SCARCE_REJECT_SOFT_STUB", "").strip().lower()
        if raw in ("0", "false", "no", "off"):
            reject_soft_stub = False
        elif raw in ("1", "true", "yes", "on"):
            reject_soft_stub = True
        else:
            # AUTO reliability: soft stub present → refuse scarce (cannot lie as iron)
            reject_soft_stub = _project_has_soft_stub_iron(project_id)
    if require_closed_loop is None:
        raw = os.environ.get("HA_SCARCE_REQUIRE_CLOSED_LOOP", "1").strip().lower()
        require_closed_loop = raw not in ("0", "false", "no", "off")

    ensure_silicon_fuse(project_id)
    try:
        receipt = require_rust_artifact_law(
            project_id,
            require_iron=bool(require_iron),
            reject_soft_stub=bool(reject_soft_stub),
        )
    except ArtifactLawError as exc:
        msg = str(exc)
        if reject_soft_stub and (
            "soft_stub" in msg.lower()
            or "iron_soft_stub_rejected" in msg.lower()
            or "reject_soft" in msg.lower()
        ):
            raise ValueError(
                "SCARCE_IRON_ANTI_LIE FAIL — soft_stub IRON_ATTESTATION cannot authorize "
                "export/push/bundle. Remove IRON_ATTESTATION_v1.json for local Dual-only emit, "
                "or provide OTP/HSM via HA_IRON_PROVIDER_BIN. "
                f"Debug override: HA_SCARCE_REJECT_SOFT_STUB=0. Detail: {exc}"
            ) from exc
        raise ValueError(
            "ARTIFACT_EXISTENCE_LAW FAIL — pack does not exist without Safe∧Hostile "
            f"+ actuation_truth + energy_claim + physics_gate + intact fuse: {exc}"
        ) from exc

    closed_loop_gate: dict[str, Any] | None = None
    if require_closed_loop:
        from production_gate.desk_closed_loop_v1 import require_closed_loop_consequence

        closed_loop_gate = require_closed_loop_consequence(project_id)

    return {
        "law_id": str(receipt.get("law_id") or LAW_ID),
        "proof_tier": PROOF_TIER,
        "ok": True,
        "verdict": "PASS",
        "errors": [],
        "conditions_present": list(receipt.get("conditions_present") or []),
        "run_ids": dict(receipt.get("run_ids") or {}),
        "honesty": dict(receipt.get("honesty") or {}),
        "oracles": dict(receipt.get("oracles") or {}),
        "law_receipt": receipt,
        "require_iron": bool(require_iron),
        "reject_soft_stub": bool(reject_soft_stub),
        "require_closed_loop": bool(require_closed_loop),
        "closed_loop_gate": closed_loop_gate,
        "iron_anti_lie": bool(reject_soft_stub),
    }


def _project_has_soft_stub_iron(project_id: str) -> bool:
    """True when project carries soft_stub IRON_ATTESTATION (bridge, not OTP)."""
    from production_gate.robot_project_desk_v1 import project_dir

    path = project_dir(project_id) / "IRON_ATTESTATION_v1.json"
    if not path.is_file():
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    backend = str(doc.get("backend") or "").strip().lower()
    return backend in ("soft_stub", "soft", "stub")



def run_dual_conditions_for_law(project_id: str) -> dict[str, Any]:
    """Convenience: Safe then Hostile so artifact may exist. Used by tests/CLI."""
    from production_gate.robot_project_run_v1 import run_project

    safe = run_project(project_id, "safe")
    hostile = run_project(project_id, "hostile")
    return {"safe": safe, "hostile": hostile, "law": evaluate_artifact_existence(project_id)}
