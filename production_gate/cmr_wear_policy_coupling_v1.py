"""CMR wear → policy confidence coupling v1 — PY_GLUE policy derate (not engine crown).

Engine truth: CXX parity + wear_chip bus mirror.
TABU: claim VLA MEASURED policy · Python-only confidence truth.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from production_gate.robot_os_governance_types_v1 import PolicyProposal
from production_gate.robot_os_policy_port_v1 import BACKEND_REGOLITH_PLANNER, RegolithPlannerBackend

PROOF_TIER = "WEAR_POLICY_COUPLE_SLICE"
ORACLE = "CITED_BIND"
_MIN_CONFIDENCE = 0.05


def wear_policy_enabled(state: dict[str, Any]) -> bool:
    row = state.get("wear_policy") or {}
    if not row:
        return True
    return bool(row.get("enabled", True))


def init_wear_policy_bind(state: dict[str, Any]) -> dict[str, Any]:
    state["wear_policy"] = {
        "enabled": True,
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
    }
    return state["wear_policy"]


def read_wear_stress_row(state: dict[str, Any], carrier_id: str) -> dict[str, Any]:
    """Wear row at proposal time — bus tail or derive at current cursor."""
    from production_gate.cmr_wear_chip_coupling_v1 import build_wear_chip_stress_row

    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    row = carrier.get("wear_chip")
    if isinstance(row, dict) and row.get("chip_stress"):
        return row
    return build_wear_chip_stress_row(state, carrier_id=carrier_id)


def derate_confidence_from_wear(
    base_confidence: float,
    wear_row: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    from production_gate.coupling_cell_wear_oracle_v1 import ORACLE, evaluate_wear_cell

    chip = wear_row.get("chip_stress") or {}
    if chip.get("effective_duty_cap") is not None:
        stress = float(chip.get("stress_index") or 0.0)
        duty_cap = float(chip.get("effective_duty_cap") or 1.0)
    else:
        ingress = float((wear_row.get("regolith") or {}).get("ingress_disturbance_mult") or 1.0)
        delta_mv = float((wear_row.get("radiation") or {}).get("delta_vth_mv") or 0.0)
        wear = evaluate_wear_cell(ingress_mult=ingress, radiation_delta_vth_mv=delta_mv)
        stress = float(wear["stress_index"])
        duty_cap = float(wear["effective_duty_cap"])
    derated = max(_MIN_CONFIDENCE, min(1.0, float(base_confidence) * duty_cap))
    meta = {
        "nominal_confidence": round(float(base_confidence), 4),
        "derated_confidence": round(derated, 4),
        "stress_index": round(stress, 4),
        "effective_duty_cap": round(duty_cap, 4),
        "confidence_delta": round(derated - float(base_confidence), 4),
        "source": "wear_chip_bus",
        "oracle": ORACLE,
    }
    return derated, meta


def apply_wear_to_policy_proposal(
    state: dict[str, Any],
    carrier_id: str,
    proposal: PolicyProposal,
) -> PolicyProposal:
    """Apply wear bus derate to policy confidence — same tick as proposal."""
    if not wear_policy_enabled(state):
        return proposal

    carrier = state.setdefault("carriers", {}).setdefault(carrier_id, {"carrier_id": carrier_id})
    wear_row = read_wear_stress_row(state, carrier_id)
    derated, meta = derate_confidence_from_wear(proposal.confidence, wear_row)
    live_dual = carrier.get("material_dual_live_bind")
    if isinstance(live_dual, dict) and live_dual.get("effective_DUTY_ON") is not None:
        meta["material_dual_live"] = {
            "effective_DUTY_ON": live_dual.get("effective_DUTY_ON"),
            "effective_NAND2_N_TR": live_dual.get("effective_NAND2_N_TR"),
            "material_variant": live_dual.get("material_variant"),
            "oracle": live_dual.get("oracle"),
        }
    carrier["wear_policy_derate"] = meta

    if abs(derated - proposal.confidence) < 1e-9:
        return proposal

    return PolicyProposal(
        action_id=proposal.action_id,
        command=proposal.command,
        confidence=derated,
        source=proposal.source,
    )


def _terminal_stressed_state(*, profile_id: str = "lunar_crater_5km") -> dict[str, Any]:
    from production_gate.chip_mission_situation_inherit_v1 import PROFILES
    from production_gate.cmr_wear_chip_coupling_v1 import apply_wear_chip_tick, init_wear_chip_bus
    from production_gate.fleet_live_state_v1 import empty_state
    from production_gate.fleet_relay_plan_v1 import segment_bounds, terminal_carrier
    from production_gate.robot_os_clifford_bind_v1 import apply_clifford_bind

    state = apply_clifford_bind(empty_state(profile_id=profile_id), profile_id=profile_id)
    init_wear_chip_bus(state)
    init_wear_policy_bind(state)
    terminal_id = terminal_carrier(profile_id)
    bounds = segment_bounds(profile_id)
    seg_idx = 1 if terminal_id == "scout_B" else 0
    start_m, end_m = bounds[seg_idx]
    traverse_m = float(PROFILES[profile_id]["traverse_m"])
    state["carriers"][terminal_id].update(
        {
            "phase": "traverse",
            "command": "traverse",
            "segment_start_m": start_m,
            "segment_end_m": end_m,
            "cursor_m": traverse_m,
            "ticks": 6,
        }
    )
    apply_wear_chip_tick(state, terminal_id)
    return state


def _idle_terminal_state(*, profile_id: str = "lunar_crater_5km") -> dict[str, Any]:
    from production_gate.cmr_wear_chip_coupling_v1 import init_wear_chip_bus
    from production_gate.fleet_live_state_v1 import empty_state
    from production_gate.fleet_relay_plan_v1 import segment_bounds, terminal_carrier
    from production_gate.robot_os_clifford_bind_v1 import apply_clifford_bind

    state = apply_clifford_bind(empty_state(profile_id=profile_id), profile_id=profile_id)
    init_wear_chip_bus(state)
    init_wear_policy_bind(state)
    terminal_id = terminal_carrier(profile_id)
    bounds = segment_bounds(profile_id)
    seg_idx = 1 if terminal_id == "scout_B" else 0
    start_m, _end_m = bounds[seg_idx]
    state["carriers"][terminal_id].update(
        {
            "phase": "armed",
            "command": "traverse",
            "segment_start_m": start_m,
            "segment_end_m": start_m,
            "cursor_m": start_m,
            "ticks": 0,
            "wear_chip": None,
        }
    )
    return state


def validate_wear_policy_falsifiers(
    *,
    idle_derate: dict[str, Any],
    terminal_derate: dict[str, Any],
) -> dict[str, Any]:
    idle_conf = float(idle_derate.get("derated_confidence") or 0.0)
    term_conf = float(terminal_derate.get("derated_confidence") or 0.0)
    idle_stress = float(idle_derate.get("stress_index") or 0.0)
    term_stress = float(terminal_derate.get("stress_index") or 0.0)

    checks: dict[str, bool] = {
        "F_wear_policy_derate_present": bool(idle_derate and terminal_derate),
        "F_terminal_stress_ge_idle": term_stress >= idle_stress,
        "F_traverse_lowers_confidence": term_conf < idle_conf,
        "F_derate_uses_duty_cap": float(terminal_derate.get("effective_duty_cap") or 0.0) < 1.0,
        "F_oracle_honest": terminal_derate.get("oracle") == ORACLE,
        "F_source_wear_chip_bus": terminal_derate.get("source") == "wear_chip_bus",
    }
    fail = [k for k, v in checks.items() if not v]
    return {"checks": checks, "fail": fail, "pass": len(fail) == 0}


def run_cmr_wear_policy_falsifier(*, write: bool = False) -> dict[str, Any]:
    """Falsifier: terminal traverse stress → lower policy confidence vs idle."""
    from datetime import datetime, timezone

    backend = RegolithPlannerBackend()
    idle_state = _idle_terminal_state()
    term_state = _terminal_stressed_state()
    terminal_id = "scout_B"

    idle_prop = backend.propose(idle_state, terminal_id)
    idle_derated = apply_wear_to_policy_proposal(idle_state, terminal_id, idle_prop)
    idle_meta = idle_state["carriers"][terminal_id]["wear_policy_derate"]

    term_prop = backend.propose(term_state, terminal_id)
    term_derated = apply_wear_to_policy_proposal(term_state, terminal_id, term_prop)
    term_meta = term_state["carriers"][terminal_id]["wear_policy_derate"]

    fals = validate_wear_policy_falsifiers(idle_derate=idle_meta, terminal_derate=term_meta)

    receipt: dict[str, Any] = {
        "receipt_id": "CMR_WEAR_POLICY_FALSIFIER_RECEIPT_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
        "backend": BACKEND_REGOLITH_PLANNER,
        "verdict": "PASS" if fals["pass"] else "FAIL",
        "idle": {
            "proposal": idle_derated.to_dict(),
            "wear_policy_derate": idle_meta,
        },
        "terminal": {
            "proposal": term_derated.to_dict(),
            "wear_policy_derate": term_meta,
        },
        "falsifiers": fals,
        "tabu": "claim VLA MEASURED · claim wear-policy without bus row",
    }
    return receipt


def read_terminal_wear_policy_derate(state: dict[str, Any]) -> dict[str, Any] | None:
    coord = state.get("coordinator") or {}
    terminal_id = str(coord.get("terminal_carrier_id") or "scout_B")
    carrier = (state.get("carriers") or {}).get(terminal_id) or {}
    row = carrier.get("wear_policy_derate")
    return row if isinstance(row, dict) else None


def apply_wear_policy_on_fleet_tail(state: dict[str, Any]) -> dict[str, Any]:
    """Replay wear→policy on fleet terminal carrier — for CMR product after relay."""
    if not wear_policy_enabled(state):
        return {"skipped": True}

    coord = state.get("coordinator") or {}
    terminal_id = str(coord.get("terminal_carrier_id") or "scout_B")
    backend = RegolithPlannerBackend()
    shadow = deepcopy(state)
    proposal = backend.propose(shadow, terminal_id)
    derated = apply_wear_to_policy_proposal(shadow, terminal_id, proposal)
    meta = (shadow.get("carriers") or {}).get(terminal_id, {}).get("wear_policy_derate") or {}

    carrier = state.setdefault("carriers", {}).setdefault(terminal_id, {})
    carrier["wear_policy_derate"] = meta
    carrier["last_policy_proposal"] = derated.to_dict()

    idle_state = _idle_terminal_state(profile_id=str(state.get("profile_id") or "lunar_crater_5km"))
    idle_prop = backend.propose(idle_state, terminal_id)
    apply_wear_to_policy_proposal(idle_state, terminal_id, idle_prop)
    idle_meta = idle_state["carriers"][terminal_id]["wear_policy_derate"]

    fals = validate_wear_policy_falsifiers(idle_derate=idle_meta, terminal_derate=meta)
    return {
        "terminal_proposal": derated.to_dict(),
        "wear_policy_derate": meta,
        "idle_baseline_derate": idle_meta,
        "falsifiers": fals,
        "verdict": "PASS" if fals["pass"] else "FAIL",
    }
