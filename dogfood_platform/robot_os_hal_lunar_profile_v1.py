"""Lunar HAL profile v1 — W_regolith_robot physics on L5 HAL sim.

Binds: lunar_wheel_locomotion · chip_mission_situation_inherit PROFILES.
proof_tier: HAL_LUNAR_PROFILE_SLICE — not MEASURED field robot.
TABU: claim Earth hover thrust on Moon · hardcoded sinkage literals.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dogfood_platform.chip_mission_situation_inherit_v1 import PROFILES
from dogfood_platform.robot_os_mission_envelope_v1 import (
    cursor_in_forbidden_zone,
    load_mission_envelope,
    traverse_crosses_forbidden_zone,
)
from dogfood_platform.robot_os_hal_sim_v1 import (
    FleetStateActuationSink,
    FleetStateEnergyLedger,
    FleetStateMissionClock,
    FleetStatePoseSource,
    build_sim_hal_stack,
    wire_sim_hal_to_kernel,
)
from dogfood_platform.robot_os_hal_v1 import (
    ActuationCommand,
    HAL_PROOF_TIER,
    RobotOsHalStack,
)
from dogfood_platform.robot_os_kernel_v1 import HalHooks, RobotOsKernel, SEGMENT_TICKS

PROOF_TIER = "HAL_LUNAR_PROFILE_SLICE"
WORLD_ORACLE = "W_regolith_robot_v0"
ORACLE = WORLD_ORACLE  # world/lane id — terramech numbers from Rust Bekker
G_MOON_MPS2 = 1.62
G_EARTH_MPS2 = 9.80665
SCOUT_MASS_KG = 20.0
WORLD_ID = "W_regolith_robot_v0"

_PROFILE_ZONE: dict[str, str] = {
    "lunar_crater_5km": "massif_traverse",
    "lunar_traverse_50km": "massif_traverse",
    "lunar_base_construct_alpha": "massif_traverse",
}


def lunar_thrust_n(command: str, *, mass_kg: float = SCOUT_MASS_KG) -> float:
    hover = mass_kg * G_MOON_MPS2 * 1.05
    if command == "traverse":
        return hover * 0.35
    if command in ("hover", "armed"):
        return hover
    return 0.0


def earth_teaching_thrust_n(command: str, *, mass_kg: float = SCOUT_MASS_KG) -> float:
    """Earth teaching proxy from hal_sim — for falsifier contrast only."""
    hover = mass_kg * G_EARTH_MPS2 * 1.05
    if command == "traverse":
        return hover * 0.35
    if command in ("hover", "armed"):
        return hover
    return 0.0


def evaluate_lunar_traverse_tick(
    step_m: float,
    *,
    profile_id: str,
    mass_kg: float = SCOUT_MASS_KG,
    variant_id: str | None = None,
    state: dict[str, Any] | None = None,
    use_material_catalog: bool = True,
) -> dict[str, Any]:
    if use_material_catalog and (variant_id or (state and state.get("material_physics_bind"))):
        from dogfood_platform.material_tick_ingress_v1 import evaluate_lunar_row_with_material

        lunar, _material = evaluate_lunar_row_with_material(
            step_m,
            profile_id=profile_id,
            variant_id=variant_id,
            state=state,
            mass_kg=mass_kg,
        )
        return lunar

    from dogfood_platform.lunar_wheel_locomotion_v1 import simulate_traverse_segment
    from dogfood_platform.terramech_bekker_on_v1 import ORACLE as BEKKER_ORACLE

    zone = _PROFILE_ZONE.get(profile_id, "massif_traverse")
    row = simulate_traverse_segment(
        max(step_m, 0.01),
        rover_mass_kg=mass_kg,
        wheel_diameter_cm=20.0,
        wheel_width_cm=8.0,
        zone=zone,  # type: ignore[arg-type]
        bearing_class="MEDIUM",
    )
    return {
        "oracle": row.get("oracle") or BEKKER_ORACLE,
        "world_oracle": WORLD_ORACLE,
        "world_id": WORLD_ID,
        "g_mps2": G_MOON_MPS2,
        "zone": zone,
        "step_m": round(max(step_m, 0.01), 4),
        "traverse_feasible": row["traverse_feasible"],
        "sinkage_mm": row["sinkage_mm"],
        "ingress_disturbance_mult": row["ingress_disturbance_mult"],
        "ingress_disturbance_heuristic": row.get("ingress_disturbance_heuristic"),
        "contact_pressure_kpa": row["contact_pressure_kpa"],
        "compaction_resistance_n": row.get("compaction_resistance_n"),
        "drawbar_pull_n": row.get("drawbar_pull_n"),
        "bearing_class": row["bearing"].get("bearing_class"),
        "sinkage_risk": row["bearing"].get("sinkage_risk"),
        "ingress_source": "lunar_physics_hal_hardcoded",
        "honesty": row.get("honesty")
        or {
            "bekker_from_rust": True,
            "ingress_quarantined_from_oracle": True,
        },
    }


def profile_v_mps(profile_id: str) -> float:
    return float(PROFILES.get(profile_id, PROFILES["lunar_crater_5km"])["v_mps"])


@dataclass
class LunarFleetStateActuationSink(FleetStateActuationSink):
    mass_kg: float = SCOUT_MASS_KG

    def _thrust_for_command(self, command: str) -> float:
        return lunar_thrust_n(command, mass_kg=self.mass_kg)


@dataclass
class LunarFleetStateEnergyLedger(FleetStateEnergyLedger):
    ingress_mult: float = 1.0

    def record_tick_wh(self, delta_wh: float) -> None:
        if delta_wh <= 0:
            delta_wh = self._segment_wh_per_tick() * max(self.ingress_mult, 1.0)
        self.wh_spent = round(self.wh_spent + delta_wh, 6)


def build_lunar_hal_stack(carrier_id: str, state: dict[str, Any], *, mass_kg: float = SCOUT_MASS_KG) -> RobotOsHalStack:
    ingress = float((state.get("lunar_hal") or {}).get("ingress_disturbance_mult") or 1.0)
    return RobotOsHalStack(
        pose=FleetStatePoseSource(carrier_id, state),
        actuation=LunarFleetStateActuationSink(carrier_id, state, mass_kg=mass_kg),
        energy=LunarFleetStateEnergyLedger(carrier_id, state, ingress_mult=ingress),
        clock=FleetStateMissionClock(carrier_id, state),
        proof_tier=PROOF_TIER,
        carrier_id=carrier_id,
    )


def wire_lunar_hal_to_kernel(
    kernel: RobotOsKernel,
    hal: RobotOsHalStack,
    state: dict[str, Any],
    *,
    radiation_enabled: bool = False,
) -> HalHooks:
    profile_id = str(state.get("profile_id", "lunar_crater_5km"))
    if radiation_enabled:
        from dogfood_platform.robot_os_radiation_bind_v1 import apply_radiation_tick, init_radiation_bind

        if not (state.get("radiation_bind") or {}).get("enabled"):
            init_radiation_bind(state, enabled=True)

    def on_tick_before(cid: str, carrier: dict[str, Any]) -> None:
        from dogfood_platform.robot_os_governed_actuation_v1 import (
            apply_governance_before_actuation,
            governance_enabled,
        )
        from dogfood_platform.robot_os_policy_only_actuation_v1 import (
            apply_policy_only_before_actuation,
            policy_only_enabled,
        )

        if policy_only_enabled(state):
            apply_policy_only_before_actuation(state, cid, hal)
            return
        if governance_enabled(state):
            apply_governance_before_actuation(state, cid, hal)
            return
        cmd = str(carrier.get("command") or "idle")
        hal.actuation.accept_command(ActuationCommand(command=cmd))

    def on_tick_after(cid: str, carrier: dict[str, Any]) -> None:
        seg_len = abs(float(carrier.get("segment_end_m", 0)) - float(carrier.get("segment_start_m", 0)))
        step_m = seg_len / SEGMENT_TICKS if seg_len else 0.0
        if (state.get("newton_x") or {}).get("enabled"):
            from dogfood_platform.robot_os_newton_x_world_step_v1 import step_newton_x_world

            step_newton_x_world(state, cid, step_m)
            terr = dict(carrier.get("lunar_physics") or {})
        else:
            mp_bind = state.get("material_physics_bind")
            if isinstance(mp_bind, dict) and mp_bind.get("variant_id"):
                from dogfood_platform.material_tick_ingress_v1 import evaluate_lunar_row_with_material

                terr, material = evaluate_lunar_row_with_material(
                    step_m,
                    profile_id=profile_id,
                    state=state,
                )
                carrier["lunar_physics"] = terr
                if material:
                    carrier["material_physics"] = material
                    carrier["material_variant"] = material.get("variant_id")
            else:
                terr = evaluate_lunar_traverse_tick(
                    step_m,
                    profile_id=profile_id,
                    use_material_catalog=False,
                )
                carrier["lunar_physics"] = terr
        ingress = float(terr["ingress_disturbance_mult"])
        if isinstance(hal.energy, LunarFleetStateEnergyLedger):
            hal.energy.ingress_mult = ingress
        hal.energy.record_tick_wh(0.0)
        pose = hal.pose.read_pose()
        if float(carrier.get("cursor_m", 0.0)) != pose.cursor_m:
            raise RuntimeError(f"lunar HAL pose drift: {pose.cursor_m} != {carrier.get('cursor_m')}")

        from dogfood_platform.robot_os_policy_only_actuation_v1 import policy_only_enabled

        if policy_only_enabled(state):
            prop = carrier.get("last_policy_proposal") or {}
            envelope = load_mission_envelope(profile_id=profile_id)
            conf_min = float(envelope.get("confidence_min") or 0.6)
            prev_m = float(carrier.get("_cursor_before_tick", carrier.get("cursor_m", 0.0)))
            curr_m = float(carrier.get("cursor_m", 0.0))
            crossed, zone_id = traverse_crosses_forbidden_zone(prev_m, curr_m, envelope)
            if (
                crossed
                and prop.get("command") == "traverse"
                and float(prop.get("confidence") or 1.0) < conf_min
            ):
                carrier["policy_zone_violation"] = str(zone_id or "forbidden")
                state.setdefault("policy_only", {})["zone_violation"] = True

        rad_row: dict[str, Any] = {}
        if radiation_enabled:
            rad_row = apply_radiation_tick(state, cid)

        lunar_hal: dict[str, Any] = {
            "proof_tier": PROOF_TIER,
            "oracle": ORACLE,
            "world_id": WORLD_ID,
            "g_mps2": G_MOON_MPS2,
            "ingress_disturbance_mult": ingress,
            "profile_v_mps": profile_v_mps(profile_id),
            "radiation_wired": radiation_enabled,
        }
        if rad_row.get("wired_to_kernel"):
            lunar_hal["radiation_delta_vth_mv"] = rad_row.get("radiation_delta_vth_mv")
            lunar_hal["radiation_within_budget"] = rad_row.get("within_budget")
        state["lunar_hal"] = lunar_hal

        if not terr["traverse_feasible"]:
            carrier["command"] = "recover"
            carrier["phase"] = "recover"
            carrier["recover_reason"] = "lunar_terramech_sinkage"
        elif rad_row.get("trigger_recover"):
            carrier["command"] = "recover"
            carrier["phase"] = "recover"
            carrier["recover_reason"] = rad_row.get("recover_reason")

    def on_phase_enter(cid: str, phase: str, carrier: dict[str, Any]) -> None:
        hal.actuation.accept_command(ActuationCommand(command=phase if phase != "handoff" else "idle"))

    return HalHooks(
        on_tick_before=on_tick_before,
        on_tick_after=on_tick_after,
        on_phase_enter=on_phase_enter,
    )


def attach_lunar_hal_to_kernel(
    kernel: RobotOsKernel,
    state: dict[str, Any],
    *,
    mass_kg: float = SCOUT_MASS_KG,
    radiation_enabled: bool = False,
) -> RobotOsHalStack:
    hal = build_lunar_hal_stack(kernel.carrier_id, state, mass_kg=mass_kg)
    kernel.hal = wire_lunar_hal_to_kernel(kernel, hal, state, radiation_enabled=radiation_enabled)
    return hal


def lunar_hal_metadata() -> dict[str, Any]:
    return {
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
        "world_id": WORLD_ID,
        "g_mps2": G_MOON_MPS2,
        "mass_kg": SCOUT_MASS_KG,
        "earth_hal_tier": HAL_PROOF_TIER,
        "tabu": ["claim MEASURED lunar robot", "claim radiation wired"],
    }
