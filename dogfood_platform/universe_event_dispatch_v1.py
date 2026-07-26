"""Universe event dispatch — route catalog events to physics backends (R1+R2)."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Callable

from dogfood_platform.lunar_dust_ingress_v1 import electrostatic_index, ingress_rate_g_m2_per_sol
from dogfood_platform.lunar_micrometeoroid_threat_v1 import threat_mass_in_band
from dogfood_platform.lunar_thermal_l5_v1 import radiative_net_flux_w_m2
from dogfood_platform.arena.eds_2r_sense_v1 import sense_delta_c
from dogfood_platform.arena.eds_2r_transport_v1 import compare_idle_vs_tw, simulate_transport_tw
from dogfood_platform.arena.maxwell_g1_v1 import compare_g0_vs_g1
from dogfood_platform.chamber.chamber_envelope_v1 import pump_down_profile
from dogfood_platform.lunar_regolith_thermal_v1 import effective_k_w_mk
from dogfood_platform.lunar_site_burial_v1 import burial_thickness_m
from dogfood_platform.lunar_lc2_duty_bind_v1 import evaluate_lc2_duty_bind
from dogfood_platform.lunar_radiation_shield_v1 import classify_regolith_shield
from dogfood_platform.universe_env_radiation_v1 import radiation_fet_from_env, radiation_state_delta
from dogfood_platform.arena.arena_moon_coupling_v1 import compare_coupled_vs_baseline, moon_tile_environment

_REPO = Path(__file__).resolve().parents[1]
_KINEMATIC_RECEIPT = _REPO / "results" / "platform_bpass" / "universe" / "SPIKE_CGA_vs_SYMPLECTIC_v1.json"
_OPERATOR_RG_RECEIPT = _REPO / "results" / "platform_bpass" / "universe" / "SPIKE_OPERATOR_RG_v1.json"


def _band_ok(val: float, spec: dict[str, Any] | None) -> bool:
    if not spec or "band" not in spec:
        return True
    lo, hi = spec["band"]
    return float(lo) <= val <= float(hi)


def _dispatch_see(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    dose = float(params.get("dose_gy") or 0.001)
    see_count = float(params.get("see_count") or 1.0)
    shield = float(params.get("areal_density_g_cm2") or params.get("shield_g_cm2") or 0.0)
    delta = radiation_state_delta(
        mission_years=1.0,
        shield_g_cm2=shield,
        annual_dose_gy=dose,
        see_rate_per_year=see_count,
    )
    inc = radiation_fet_from_env(
        delta["radiation"],
        mission_years=1.0,
        shield_g_cm2=shield,
    )
    ok = float(inc.get("radiation_delta_vth_mv") or 0) >= 0
    return {
        "effect": inc,
        "in_typical_band": ok,
        "epsilon": {"name": "see_wear_mv", "value": inc.get("radiation_delta_vth_mv"), "unit": "mV"},
        "state_delta": delta,
    }


def _dispatch_tid(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    dose = float(params.get("dose_gy") or 0.1)
    shield = float(params.get("areal_density_g_cm2") or params.get("shield_g_cm2") or 0.0)
    delta = radiation_state_delta(
        mission_years=1.0,
        shield_g_cm2=shield,
        annual_dose_gy=dose,
        see_rate_per_year=0.0,
    )
    inc = radiation_fet_from_env(delta["radiation"], mission_years=1.0, shield_g_cm2=shield)
    return {
        "effect": inc,
        "in_typical_band": dose <= 1.0,
        "epsilon": {"name": "tid_wear_mv", "value": inc.get("radiation_delta_vth_mv"), "unit": "mV"},
        "state_delta": delta,
    }


def _dispatch_tribo(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    zone = str(params.get("zone") or "rim_sun")
    scale = float(params.get("e_index_scale") or 1.0)
    es = electrostatic_index(zone)  # type: ignore[arg-type]
    e_idx = float(es["electrostatic_index"]) * scale
    ok = 0.3 <= e_idx <= 2.5
    return {
        "effect": {"electrostatic_index": e_idx, "zone": zone},
        "in_typical_band": ok,
        "epsilon": {"name": "e_index", "value": e_idx, "unit": "rel"},
    }


def _dispatch_phonon(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    dt = float(params.get("delta_t_k") or 5.0)
    k_row = effective_k_w_mk("highland_regolith_loose", t_k=220.0 + dt)
    return {
        "effect": k_row,
        "in_typical_band": 1.0 <= dt <= 30.0,
        "epsilon": {"name": "k_w_mk", "value": k_row.get("k_w_mk"), "unit": "W/mK"},
    }


def _dispatch_sense_grain(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    dust_um = float(params.get("dust_layer_um") or 10.0)
    s = sense_delta_c(dust_layer_um=dust_um)
    ok = (dust_um <= 1e-9 and abs(float(s["delta_c_frac"])) < 1e-9) or float(s["delta_c_frac"]) < 0
    return {
        "effect": s,
        "in_typical_band": ok,
        "epsilon": {"name": "delta_c_frac", "value": s["delta_c_frac"], "unit": "frac"},
    }


def _dispatch_transport(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    q = float(params.get("q_transport_scale") or 1.0)
    tw = simulate_transport_tw(q_proxy=q)
    idle = compare_idle_vs_tw()
    ok = bool(tw["outward_bias"]) and bool(idle["falsifier_pass"])
    return {
        "effect": {"transport": tw, "idle_cmp": idle},
        "in_typical_band": ok,
        "epsilon": {"name": "drift_mm", "value": tw["mean_radial_drift_mm"], "unit": "mm"},
    }


def _dispatch_thermal_shadow(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    illum = float(params.get("illum_frac") or 0.96)
    rim = radiative_net_flux_w_m2(220.0, zone="rim_sun")
    psr = radiative_net_flux_w_m2(70.0, zone="psr_floor")
    rim_q = float(rim["q_solar_w_m2"]) * illum
    ok = rim_q >= float(psr["q_solar_w_m2"])
    return {
        "effect": {"rim_q_solar": rim_q, "psr_q_solar": psr["q_solar_w_m2"]},
        "in_typical_band": ok,
        "epsilon": {"name": "q_solar_delta", "value": rim_q - float(psr["q_solar_w_m2"]), "unit": "W/m2"},
    }


def _dispatch_maxwell_gap(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    c = compare_g0_vs_g1()
    ok = bool(c.get("uniform_scaling")) and bool(c.get("falsifier_pass"))
    return {
        "effect": c,
        "in_typical_band": ok,
        "epsilon": {"name": "g0_g1_ratio", "value": (c.get("per_phase_ratio") or [0])[0], "unit": "rel"},
    }


def _dispatch_chamber_pump(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    p = pump_down_profile()
    ok = p["verdict"] == "PASS" and float(p["h_c_final"]) == 0.0
    return {
        "effect": p,
        "in_typical_band": ok,
        "epsilon": {"name": "p_final_torr", "value": p["p_final_torr"], "unit": "Torr"},
    }


def _dispatch_micrometeoroid(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    mass = float(params.get("mass_g") or 1e-4)
    t = threat_mass_in_band(mass)
    return {
        "effect": t,
        "in_typical_band": bool(t["in_mem_threat_band"]),
        "epsilon": {"name": "mass_g", "value": mass, "unit": "g"},
    }


def _dispatch_solar_flare(params: dict[str, Any], event: dict[str, Any], *, env: Any = None) -> dict[str, Any]:
    mult = float(params.get("flare_multiplier") or 3.0)
    t_surf = 220.0
    if env is not None:
        t_surf = float(env.thermal_column.t_surface_k)
    rim = radiative_net_flux_w_m2(t_surf, zone="rim_sun")
    q = float(rim["q_solar_w_m2"]) * mult
    ok = 1.0 <= mult <= 12.0
    delta = {"solar": {"flare_multiplier": mult, "q_solar_w_m2": q}}
    if env is not None:
        delta = {}
    return {
        "effect": {"flare_multiplier": mult, "q_solar_scaled_w_m2": q},
        "in_typical_band": ok,
        "epsilon": {"name": "q_solar_scaled", "value": q, "unit": "W/m2"},
        "state_delta": delta if env is None else {},
    }


def _dispatch_ingress_joint(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    zone = str(params.get("zone") or "rim_sun")
    n = float(params.get("n_sols") or 30.0)
    rate = ingress_rate_g_m2_per_sol(zone)  # type: ignore[arg-type]
    loading = rate * n
    ok = loading >= 0
    return {
        "effect": {"ingress_rate_g_m2_per_sol": rate, "cumulative_g_m2": loading},
        "in_typical_band": ok,
        "epsilon": {"name": "cumulative_loading_g_m2", "value": loading, "unit": "g/m2"},
    }


def _dispatch_universe_corridor(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    key = str(params.get("corridor_key") or "w_chip")
    mod = importlib.import_module("dogfood_platform.universe_kernel_v1")
    rec = mod.run_corridor_receipt(live=False, corridor_key=key)
    ok = rec.verdict == "PASS"
    return {
        "effect": {"verdict": rec.verdict, "world_id": rec.state_bus.get("world_id")},
        "in_typical_band": ok,
        "epsilon": {"name": "corridor_verdict", "value": 1.0 if ok else 0.0, "unit": "bool"},
    }


def _dispatch_regolith_robot(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    mod = importlib.import_module("dogfood_platform.world_regolith_robot_v0")
    n = float(params.get("n_sols") or 30.0)
    rec = mod.run_mission(n_sols=n, zone=str(params.get("zone") or "massif_traverse"))  # type: ignore[arg-type]
    ok = rec.verdict == "PASS"
    wear_mv = float(rec.metric.get("final_wear_mv") or 0)
    return {
        "effect": {"verdict": rec.verdict, "final_wear_mv": wear_mv},
        "in_typical_band": ok,
        "epsilon": {"name": "final_wear_mv", "value": wear_mv, "unit": "mV"},
    }


def _dispatch_traverse_macro(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    return _dispatch_regolith_robot(params, event)


def _dispatch_moon_shackleton(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    zone = str(params.get("zone") or "rim_sun")
    env = moon_tile_environment(zone=zone, n_sols=float(params.get("n_sols") or 30.0))  # type: ignore[arg-type]
    thermal_index = float(env.get("q_transport_mult") or params.get("thermal_index") or 1.0)
    ok = 0.8 <= thermal_index <= 2.5
    return {
        "effect": env,
        "in_typical_band": ok,
        "epsilon": {"name": "thermal_index", "value": thermal_index, "unit": "rel"},
        "state_delta": {
            "solar": {"illum_frac": 0.96},
            "dust_charge": {"mass_loading_g_m2": float(env.get("accumulation_g_m2") or 0.0)},
            "vacuum_thermal": {"t_surf_k": float(env.get("t_surf_k") or 220.0)},
        },
    }


def _dispatch_lc2_duty(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    row = evaluate_lc2_duty_bind()
    duty = float(params.get("duty_frac") or row.get("duty_on") or 0.5)
    mult = float(row.get("thermal_stress_mult") or 1.0) * (0.5 + duty)
    ok = 0.1 <= duty <= 0.95
    return {
        "effect": {**row, "duty_frac": duty, "thermal_stress_mult": mult},
        "in_typical_band": ok,
        "epsilon": {"name": "thermal_stress_mult", "value": mult, "unit": "rel"},
        "state_delta": {"vacuum_thermal": {"t_surf_k": 220.0 + 15.0 * duty}},
    }


def _dispatch_arena_moon_stack(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    zone = str(params.get("zone") or "rim_sun")
    cmp = compare_coupled_vs_baseline(zone=zone)  # type: ignore[arg-type]
    ok = bool(cmp.get("falsifier_pass"))
    drift = float(cmp.get("coupled_transport_mm") or 0.0)
    return {
        "effect": cmp,
        "in_typical_band": ok,
        "epsilon": {"name": "drift_mm", "value": drift, "unit": "mm"},
        "state_delta": {"dust_charge": {"mass_loading_g_m2": float(params.get("mass_loading_g_m2") or 0.5)}},
    }


def _dispatch_site_burial(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    burial_m = float(params.get("burial_m") or 1.5)
    row = burial_thickness_m()
    t_mult = 1.0 + 0.05 * burial_m
    ok = 0.5 <= burial_m <= 3.0
    return {
        "effect": {**row, "burial_m": burial_m},
        "in_typical_band": ok,
        "epsilon": {"name": "burial_m", "value": burial_m, "unit": "m"},
        "state_delta": {"vacuum_thermal": {"t_surf_k": 220.0 / t_mult}},
    }


def _dispatch_solar_particle_proxy(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    dose = float(params.get("dose_gy") or 0.5)
    depth_m = float(params.get("shield_depth_m") or 0.5)
    areal = float(params.get("areal_density_g_cm2") or max(depth_m * 20.0, 10.0))
    shield = classify_regolith_shield(areal)
    delta = radiation_state_delta(
        mission_years=1.0,
        shield_g_cm2=areal,
        annual_dose_gy=dose,
        see_rate_per_year=1.0,
    )
    inc = radiation_fet_from_env(delta["radiation"], mission_years=1.0, shield_g_cm2=areal)
    ok = shield["spe_class"] != "SPE_INSUFFICIENT" and dose <= 2.0
    wear = float(inc.get("radiation_delta_vth_mv") or 0)
    return {
        "effect": {"shield": shield, "wear": inc, "areal_density_g_cm2": areal},
        "in_typical_band": ok,
        "epsilon": {"name": "radiation_delta_vth_mv", "value": wear, "unit": "mV"},
        "state_delta": delta,
    }


def _dispatch_cosmic_ray_step(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    yrs = float(params.get("exposure_yr") or 1.0)
    shield = float(params.get("areal_density_g_cm2") or params.get("shield_g_cm2") or 0.0)
    delta = radiation_state_delta(mission_years=yrs, shield_g_cm2=shield)
    row = delta["radiation"]
    ok = float(row.get("dose_gy") or 0) <= 1.0 and float(row.get("see_rate_1_per_yr") or 0) <= 0.25
    return {
        "effect": {
            "mission_dose_gy": row.get("dose_gy"),
            "incident_dose_gy": row.get("incident_dose_gy"),
            "albedo_dose_gy": row.get("albedo_dose_gy"),
            "albedo_fraction": row.get("albedo_fraction"),
            "see_rate_per_year": row.get("see_rate_1_per_yr"),
            "oracle": "PROXY_CITED",
        },
        "in_typical_band": ok,
        "epsilon": {"name": "mission_dose_gy", "value": row.get("dose_gy"), "unit": "Gy"},
        "state_delta": delta,
    }


def _dispatch_eclipse_thermal(params: dict[str, Any], event: dict[str, Any], *, env: Any = None) -> dict[str, Any]:
    drop = float(params.get("illum_drop_frac") or 1.0)
    duration_h = float(params.get("duration_h") or 2.0)
    t_surf = 220.0
    if env is not None:
        t_surf = float(env.thermal_column.t_surface_k)
    rim = radiative_net_flux_w_m2(t_surf, zone="rim_sun")
    q_lit = float(rim["q_solar_w_m2"])
    q_eclipse = q_lit * (1.0 - min(drop, 1.0))
    swing = max(0.0, (q_lit - q_eclipse) / 50.0)
    ok = 0.5 <= duration_h <= 4.0
    state_delta = {
        "solar": {"q_solar_w_m2": q_eclipse, "illum_frac": 1.0 - drop},
        "vacuum_thermal": {"t_surf_k": t_surf - 30.0 * drop},
    }
    if env is not None:
        state_delta = {}
    return {
        "effect": {"q_lit": q_lit, "q_eclipse": q_eclipse, "duration_h": duration_h},
        "in_typical_band": ok,
        "epsilon": {"name": "thermal_swing_k", "value": swing, "unit": "K"},
        "state_delta": state_delta,
    }


def _load_kinematic_spike(*, full: bool = False) -> dict[str, Any]:
    if _KINEMATIC_RECEIPT.is_file():
        return json.loads(_KINEMATIC_RECEIPT.read_text(encoding="utf-8"))
    if full:
        from dogfood_platform.universe_backend_native_v1 import run_kinematic_spike_native

        return run_kinematic_spike_native(build=True)
    raise FileNotFoundError(_KINEMATIC_RECEIPT)


def _dispatch_kinematic_shock(params: dict[str, Any], event: dict[str, Any], *, full: bool = False) -> dict[str, Any]:
    if full:
        return _dispatch_kinematic_shock_full(params, event)
    report = _load_kinematic_spike(full=False)
    sym = report.get("symplectic") or {}
    scale = float(params.get("impulse_scale") or 1.0)
    jerk = float(sym.get("mlcc_jerk_peak") or 0.0) * scale
    drift = float(sym.get("energy_drift_rms_rel") or 0.0)
    ok = drift <= 1.5
    return {
        "effect": {"symplectic": sym, "impulse_scale": scale, "mode": "receipt"},
        "in_typical_band": ok,
        "epsilon": {"name": "mlcc_jerk_peak", "value": jerk, "unit": "rel"},
        "state_delta": {"mechanical": {"jerk_peak": jerk, "impulse_scale": scale}},
    }


def _dispatch_kinematic_shock_full(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    from dogfood_platform.universe_backend_native_v1 import run_kinematic_event_full

    report = run_kinematic_event_full(params, build=True, write_receipt=True)
    sym = report.get("symplectic") or {}
    cga = report.get("cga") or {}
    scale = float(params.get("impulse_scale") or 1.0)
    drift_budget = float((event.get("typical_numbers") or {}).get("energy_drift_rms_rel") or 0.5)
    sym_drift = float(sym.get("energy_drift_rms_rel") or 0.0)
    cga_drift = float(cga.get("energy_drift_rms_rel") or 0.0)
    jerk = float(cga.get("mlcc_jerk_peak") or sym.get("mlcc_jerk_peak") or 0.0)
    ok = sym_drift <= drift_budget * 3.0 and cga_drift <= drift_budget * 3.0
    ok = ok and str(sym.get("language") or "") == "rust" and str(cga.get("language") or "") == "rust"
    return {
        "effect": {
            "mode": "native_full_run",
            "symplectic": sym,
            "cga": cga,
            "winner": report.get("winner"),
            "promote_cga": report.get("promote_cga"),
            "receipt": report.get("receipt"),
            "impulse_scale": scale,
        },
        "in_typical_band": ok,
        "epsilon": {"name": "mlcc_jerk_peak", "value": jerk, "unit": "rel"},
        "state_delta": {"mechanical": {"jerk_peak": jerk, "impulse_scale": scale}},
    }


def _load_operator_rg_spike(*, full: bool = False) -> dict[str, Any]:
    if _OPERATOR_RG_RECEIPT.is_file():
        return json.loads(_OPERATOR_RG_RECEIPT.read_text(encoding="utf-8"))
    if full:
        from dogfood_platform.universe_backend_native_v1 import run_operator_rg_spike_native

        return run_operator_rg_spike_native(build=True)
    raise FileNotFoundError(_OPERATOR_RG_RECEIPT)


def _dispatch_operator_rg_bridge(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    report = _load_operator_rg_spike(full=False)
    op = report.get("operator_rg_galerkin") or {}
    naive = report.get("naive_generator_mor") or {}
    residual = float(op.get("generator_residual_mean") or 0.01)
    ok = residual < float(naive.get("generator_residual_mean") or 1.0)
    return {
        "effect": {"operator_rg": op, "naive": naive, "winner": report.get("winner")},
        "in_typical_band": ok,
        "epsilon": {"name": "generator_residual_mean", "value": residual, "unit": "rel"},
        "state_delta": {},
    }


def _dispatch_ascent_acoustic(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    from dogfood_platform.rocket_ascent_load_v1 import evaluate_ascent_envelope

    scale = float(params.get("impulse_scale") or 1.0)
    ev = evaluate_ascent_envelope(impulse_scale=scale)
    mv = float(ev["epsilon"]["total_mv"])
    return {
        "effect": ev,
        "in_typical_band": ev.get("falsifier_pass", False),
        "epsilon": {"name": "ascent_envelope_mv", "value": mv, "unit": "mV_proxy"},
    }


def _dispatch_generic_pass(params: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    return {
        "effect": {"note": "catalog_registered", "backend": event.get("backend")},
        "in_typical_band": True,
        "epsilon": {"name": "registered", "value": 1.0, "unit": "bool"},
    }


_DISPATCH: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "EVT-u-01": _dispatch_see,
    "EVT-u-02": _dispatch_tid,
    "EVT-u-04": _dispatch_tribo,
    "EVT-u-05": _dispatch_phonon,
    "EVT-u-08": _dispatch_sense_grain,
    "EVT-m-02": _dispatch_ingress_joint,
    "EVT-m-04": _dispatch_transport,
    "EVT-m-05": _dispatch_thermal_shadow,
    "EVT-m-08": _dispatch_maxwell_gap,
    "EVT-M-01": _dispatch_traverse_macro,
    "EVT-M-02": _dispatch_moon_shackleton,
    "EVT-M-03": _dispatch_solar_flare,
    "EVT-M-04": _dispatch_chamber_pump,
    "EVT-M-05": _dispatch_lc2_duty,
    "EVT-M-06": _dispatch_arena_moon_stack,
    "EVT-M-07": _dispatch_site_burial,
    "EVT-M-08": _dispatch_universe_corridor,
    "EVT-C-01": _dispatch_micrometeoroid,
    "EVT-C-02": _dispatch_solar_particle_proxy,
    "EVT-C-03": _dispatch_cosmic_ray_step,
    "EVT-C-04": _dispatch_eclipse_thermal,
    "EVT-C-05": _dispatch_solar_flare,
    "EVT-C-06": _dispatch_kinematic_shock,
    "EVT-C-07": _dispatch_operator_rg_bridge,
    "EVT-C-08": _dispatch_regolith_robot,
    "EVT-A2-01": _dispatch_ascent_acoustic,
}


def apply_event(
    event: dict[str, Any],
    params: dict[str, Any],
    *,
    full: bool = False,
    env: Any = None,
) -> dict[str, Any]:
    eid = str(event.get("event_id") or "")
    env_kw = {"env": env} if env is not None else {}
    if full and eid == "EVT-C-06":
        out = _dispatch_kinematic_shock(params, event, full=True)
    elif full and eid in ("EVT-M-02", "EVT-M-06"):
        out = _dispatch_universe_corridor(params, event)
    else:
        handler = _DISPATCH.get(eid, _dispatch_generic_pass)
        if eid == "EVT-C-06":
            out = _dispatch_kinematic_shock(params, event, full=False)
        elif eid in ("EVT-C-05", "EVT-C-04") and env is not None:
            out = handler(params, event, env=env)
        else:
            try:
                out = handler(params, event, **env_kw)
            except TypeError:
                out = handler(params, event)
    delta = out.get("state_delta")
    if not delta:
        delta = event_state_delta(event, out) if env is None else {}
    return {
        "event_id": eid,
        "name": event.get("name"),
        "scale_class": event.get("scale_class"),
        "law_id": event.get("law_id"),
        "coupling_targets": event.get("coupling_targets"),
        "params": params,
        "verdict": "PASS" if out.get("in_typical_band") else "FAIL",
        "state_delta": delta or {},
        "env_read": env is not None,
        **out,
    }


def event_state_delta(event: dict[str, Any], dispatch_out: dict[str, Any]) -> dict[str, Any]:
    if dispatch_out.get("state_delta"):
        return dict(dispatch_out["state_delta"])
    eps = dispatch_out.get("epsilon") or {}
    name = str(eps.get("name") or "")
    val = eps.get("value")
    if val is None:
        return {}
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return {}
    scale = str(event.get("scale_class") or "")
    if name in ("see_wear_mv", "tid_wear_mv", "radiation_delta_vth_mv", "mission_dose_gy"):
        return {"radiation": {"dose_gy_accum": fval, "dose_gy": fval}}
    if name == "see_albedo_mv":
        return {"radiation": {"see_albedo_mv": fval}}
    if name in ("q_solar_scaled", "q_solar_delta"):
        return {"solar": {"q_solar_w_m2": fval}}
    if name == "cumulative_loading_g_m2":
        return {"dust_charge": {"mass_loading_g_m2": fval}}
    if name == "mlcc_jerk_peak":
        return {"mechanical": {"jerk_peak": fval}}
    if scale in ("macro", "cosmic"):
        return {"solar": {"flare_multiplier": fval}} if fval > 0 else {}
    return {}


def macro_cosmic_dispatch_audit(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    from dogfood_platform.universe_event_sampler_v1 import load_event_catalog, draw_event_params
    import random

    data = catalog or load_event_catalog()
    rng = random.Random(20260616)
    missing: list[str] = []
    generic: list[str] = []
    for ev in data.get("events") or []:
        scale = str(ev.get("scale_class") or "")
        if scale not in ("macro", "cosmic"):
            continue
        eid = str(ev.get("event_id") or "")
        if eid not in _DISPATCH:
            missing.append(eid)
            continue
        params = draw_event_params(ev, rng)
        out = apply_event(ev, params)
        if (out.get("epsilon") or {}).get("name") == "registered":
            generic.append(eid)
    return {
        "audit_id": "MACRO_COSMIC_DISPATCH_AUDIT_v1",
        "macro_cosmic_count": sum(1 for e in data.get("events") or [] if e.get("scale_class") in ("macro", "cosmic")),
        "missing_handlers": missing,
        "generic_pass_hits": generic,
        "verdict": "PASS" if not missing and not generic else "FAIL",
    }
