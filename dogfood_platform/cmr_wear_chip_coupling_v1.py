"""CMR wear → chip stress coupling v1 — PY_GLUE bus mirror (oracle only, not engine crown).

Engine truth: CHIP_COUPLING_CELL_WEAR_PARITY_RECEIPT_v1.json (CXX_PARITY_REFERENCE).
Binds: lunar_physics ingress · radiation_fet wear at traverse fraction · duty headroom proxy.
TABU: claim flight chip stress MEASURED · Python-only engine truth.
"""
from __future__ import annotations

from typing import Any

from dogfood_platform.chip_mission_situation_inherit_v1 import PROFILES
from dogfood_platform.coupling_cell_wear_oracle_v1 import ORACLE, evaluate_wear_cell
from dogfood_platform.robot_os_radiation_bind_v1 import (
    DEFAULT_MISSION_YEARS,
    DEFAULT_SHIELD_G_CM2,
    DEFAULT_SITE_CLASS,
    wear_at_traverse_fraction,
)

PROOF_TIER = "WEAR_CHIP_COUPLE_SLICE"
_RADIATION_STRESS_SCALE_MV = 50.0
_INGRESS_STRESS_SCALE = 0.3
_MAX_DUTY_LOSS = 0.25
_MIN_DUTY_CAP = 0.5


def _traverse_fraction(state: dict[str, Any], carrier: dict[str, Any]) -> float:
    profile_id = str(state.get("profile_id") or "lunar_crater_5km")
    traverse_m = float(PROFILES.get(profile_id, PROFILES["lunar_crater_5km"])["traverse_m"])
    cursor = float(carrier.get("cursor_m") or 0.0)
    if traverse_m <= 0:
        return 0.0
    return min(1.0, max(0.0, cursor / traverse_m))


def _stress_index(*, ingress_mult: float, radiation_delta_vth_mv: float) -> float:
    return float(
        evaluate_wear_cell(
            ingress_mult=ingress_mult,
            radiation_delta_vth_mv=radiation_delta_vth_mv,
        )["stress_index"]
    )


def build_wear_chip_stress_row(
    state: dict[str, Any],
    *,
    carrier_id: str | None = None,
) -> dict[str, Any]:
    """Derive chip stress row from envelope B physics at traverse fraction."""
    coord = state.get("coordinator") or {}
    carrier_id = carrier_id or str(coord.get("terminal_carrier_id") or "scout_B")
    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    fraction = _traverse_fraction(state, carrier)
    from dogfood_platform.material_tick_ingress_v1 import resolve_tick_ingress

    resolved = resolve_tick_ingress(state, carrier_id)
    ingress_mult = float(resolved["ingress_mult"])
    ingress_source = str(resolved.get("ingress_source") or "material_physics_bus")
    delta_mv = float(resolved["radiation_delta_vth_mv"])
    lunar = dict(resolved.get("lunar") or carrier.get("lunar_physics") or {})
    if not lunar:
        from dogfood_platform.robot_os_hal_lunar_profile_v1 import evaluate_lunar_traverse_tick

        profile_id = str(state.get("profile_id") or "lunar_crater_5km")
        seg_len = abs(
            float(carrier.get("segment_end_m", 0.0)) - float(carrier.get("segment_start_m", 0.0))
        )
        step_m = seg_len / 6.0 if seg_len else 1.0
        lunar = evaluate_lunar_traverse_tick(step_m, profile_id=profile_id, state=state)

    rad = wear_at_traverse_fraction(
        fraction,
        mission_years=DEFAULT_MISSION_YEARS,
        shield_g_cm2=DEFAULT_SHIELD_G_CM2,
        site_class=DEFAULT_SITE_CLASS,
    )
    delta_mv = float(rad.get("radiation_delta_vth_mv") or 0.0)
    wear = evaluate_wear_cell(ingress_mult=ingress_mult, radiation_delta_vth_mv=delta_mv)
    stress = float(wear["stress_index"])
    duty_cap = float(wear["effective_duty_cap"])

    return {
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
        "engine_truth": "CXX_PARITY_REFERENCE",
        "carrier_id": carrier_id,
        "traverse_fraction": round(fraction, 4),
        "regolith": {
            "ingress_disturbance_mult": ingress_mult,
            "ingress_source": ingress_source,
            "sinkage_mm": lunar.get("sinkage_mm"),
            "sinkage_risk": lunar.get("sinkage_risk"),
            "traverse_feasible": lunar.get("traverse_feasible"),
        },
        "radiation": {
            "delta_vth_mv": round(delta_mv, 4),
            "within_budget": rad.get("within_budget"),
            "mission_years_at_fraction": round(DEFAULT_MISSION_YEARS * fraction, 4),
        },
        "chip_stress": {
            "stress_index": round(stress, 4),
            "effective_duty_cap": round(duty_cap, 4),
            "headroom_loss_pct": round((1.0 - duty_cap) * 100.0, 2),
        },
        "tabu": "claim MEASURED chip derate",
    }


def init_wear_chip_bus(state: dict[str, Any], *, iron_mmio: bool = True) -> dict[str, Any]:
    """Enable envelope B wear→chip row on live state bus."""
    engine_truth = "IRON_SIM_MMIO" if iron_mmio else "CXX_PARITY_REFERENCE"
    state["wear_chip_bus"] = {
        "enabled": True,
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
        "engine_truth": engine_truth,
        "iron_mmio_enabled": iron_mmio,
        "iron_mmio_tick_count": 0,
        "tick_log_len": 0,
        "rows_by_carrier": {},
        "terminal_row": None,
    }
    return state["wear_chip_bus"]


def apply_wear_chip_tick(state: dict[str, Any], carrier_id: str) -> dict[str, Any]:
    """Write wear→chip row to carrier slot + bus tail — one kernel tick."""
    bus = state.get("wear_chip_bus") or {}
    if bus and not bus.get("enabled", True):
        return {}
    if bus.get("iron_mmio_enabled"):
        from dogfood_platform.cmr_wear_iron_mmio_coupling_v1 import apply_wear_chip_tick_iron_mmio

        return apply_wear_chip_tick_iron_mmio(state, carrier_id)

    carrier = (state.get("carriers") or {}).get(carrier_id) or {}
    row = build_wear_chip_stress_row(state, carrier_id=carrier_id)
    row["tick"] = int(carrier.get("ticks") or 0)
    row["source"] = "live_state_bus"
    carrier["wear_chip"] = row

    if "wear_chip_bus" not in state:
        init_wear_chip_bus(state)
    bus = state["wear_chip_bus"]
    rows = bus.setdefault("rows_by_carrier", {})
    rows[carrier_id] = row
    bus["last_carrier_id"] = carrier_id
    bus["tick_log_len"] = int(bus.get("tick_log_len") or 0) + 1

    coord = state.get("coordinator") or {}
    if carrier_id == str(coord.get("terminal_carrier_id") or ""):
        bus["terminal_row"] = row

    return row


def read_terminal_wear_chip_row(state: dict[str, Any]) -> dict[str, Any] | None:
    """Terminal carrier wear_chip from live bus — primary CMR v3 source."""
    coord = state.get("coordinator") or {}
    terminal_id = str(coord.get("terminal_carrier_id") or "scout_B")
    carrier = (state.get("carriers") or {}).get(terminal_id) or {}
    row = carrier.get("wear_chip")
    if isinstance(row, dict) and row.get("chip_stress"):
        return row
    bus_row = (state.get("wear_chip_bus") or {}).get("terminal_row")
    if isinstance(bus_row, dict) and bus_row.get("chip_stress"):
        return bus_row
    return None


def _rows_match(bus_row: dict[str, Any], recompute_row: dict[str, Any]) -> bool:
    if abs(float(bus_row.get("traverse_fraction") or 0) - float(recompute_row.get("traverse_fraction") or 0)) > 1e-3:
        return False
    bus_stress = bus_row.get("chip_stress") or {}
    rec_stress = recompute_row.get("chip_stress") or {}
    if abs(float(bus_stress.get("stress_index") or 0) - float(rec_stress.get("stress_index") or 0)) > 1e-3:
        return False
    if abs(float(bus_stress.get("effective_duty_cap") or 0) - float(rec_stress.get("effective_duty_cap") or 0)) > 1e-3:
        return False
    return True


def validate_wear_chip_bus_falsifiers(
    bus_row: dict[str, Any] | None,
    *,
    recompute_row: dict[str, Any],
    idle_baseline: dict[str, Any],
    bus_meta: dict[str, Any] | None = None,
    terminal_ticks: int = 0,
) -> dict[str, Any]:
    """CMR v3 — bus row is source of truth; recompute is cross-check only."""
    row = bus_row or {}
    base = validate_wear_chip_falsifiers(row, idle_baseline=idle_baseline)
    checks = dict(base["checks"])
    checks["F_bus_row_present"] = bool(bus_row and bus_row.get("chip_stress"))
    checks["F_bus_matches_recompute"] = bool(bus_row and _rows_match(bus_row, recompute_row))
    checks["F_bus_tick_logged"] = int((bus_meta or {}).get("tick_log_len") or 0) >= 1
    checks["F_bus_source_live"] = (bus_row or {}).get("source") in (
        "live_state_bus",
        "iron_mmio_readback",
    )
    checks["F_bus_terminal_ticks_ge_1"] = terminal_ticks >= 1
    fail = [k for k, v in checks.items() if not v]
    return {"checks": checks, "fail": fail, "pass": len(fail) == 0}


def build_idle_wear_chip_baseline(state: dict[str, Any]) -> dict[str, Any]:
    """Baseline at cursor=0 for falsifier: traverse must raise stress."""
    shadow = {
        **state,
        "carriers": {
            cid: {**c, "cursor_m": 0.0, "lunar_physics": None}
            for cid, c in (state.get("carriers") or {}).items()
        },
    }
    coord = state.get("coordinator") or {}
    cid = str(coord.get("terminal_carrier_id") or "scout_B")
    row = build_wear_chip_stress_row(shadow, carrier_id=cid)
    row["mode"] = "idle_baseline"
    return row


def validate_wear_chip_falsifiers(
    row: dict[str, Any],
    *,
    idle_baseline: dict[str, Any],
) -> dict[str, Any]:
    stress = float((row.get("chip_stress") or {}).get("stress_index") or 0.0)
    idle_stress = float((idle_baseline.get("chip_stress") or {}).get("stress_index") or 0.0)
    ingress = float((row.get("regolith") or {}).get("ingress_disturbance_mult") or 0.0)
    delta_mv = float((row.get("radiation") or {}).get("delta_vth_mv") or 0.0)
    duty_cap = float((row.get("chip_stress") or {}).get("effective_duty_cap") or 0.0)

    checks: dict[str, bool] = {
        "F_wear_chip_row_present": bool(row.get("chip_stress")),
        "F_stress_index_unit_interval": 0.0 <= stress <= 1.0,
        "F_duty_cap_bounded": _MIN_DUTY_CAP <= duty_cap <= 1.0,
        "F_traverse_raises_stress_vs_idle": stress > idle_stress,
        "F_regolith_ingress_ge_1": ingress >= 1.0,
        "F_radiation_mv_non_negative": delta_mv >= 0.0,
        "F_radiation_coupled": "delta_vth_mv" in (row.get("radiation") or {}),
        "F_oracle_honest": row.get("oracle") == ORACLE,
    }
    fail = [k for k, v in checks.items() if not v]
    return {"checks": checks, "fail": fail, "pass": len(fail) == 0}
