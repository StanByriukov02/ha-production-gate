"""U4 — law-class env merge + concurrent timestep integrator."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dogfood_platform.lunar_dust_ingress_v1 import accumulation_after_sols, ingress_rate_g_m2_per_sol
from dogfood_platform.universe_env_state_v1 import ActiveWindow, EnvironmentStateV1
from dogfood_platform.universe_env_thermal_column_v1 import (
    apply_bc_from_env,
    earth_hours_to_lunar_sols,
    flux_bc_from_env,
    lunar_timeline_meta,
    q_net_from_bc,
    step_column_implicit_1d,
    zone_from_regime,
)

_REPO = Path(__file__).resolve().parents[1]
_ENV_DRIVER = _REPO / "results" / "platform_bpass" / "universe" / "ENV_DRIVER_BIND_v1.json"
_METHOD_BIND = _REPO / "results" / "platform_bpass" / "universe" / "ENV_STATE_PHYSICS_METHOD_BIND_v1.json"

_FLARE_BAND = (1.0, 12.0)
_SOLAR_EVENT_IDS = frozenset({"EVT-C-05", "EVT-M-03"})
_ECLIPSE_EVENT_IDS = frozenset({"EVT-C-04", "EVT-M-04", "EVT-M-05", "EVT-m-05"})
_INGRESS_EVENT_IDS = frozenset({"EVT-m-02", "EVT-M-01", "EVT-C-08"})
# Cache Rust 1h window dose so storm timesteps don't spawn CLI every hop.
_RAD_RATE_CACHE: dict[tuple[float, float, float, float, float], dict[str, Any]] = {}


def _flare_band() -> tuple[float, float]:
    if _ENV_DRIVER.is_file():
        data = json.loads(_ENV_DRIVER.read_text(encoding="utf-8"))
        band = ((data.get("driver_axes") or {}).get("solar") or {}).get("flare_multiplier") or {}
        b = band.get("band") or [1.0, 12.0]
        return float(b[0]), float(b[1])
    return _FLARE_BAND


def combine_active_solar_bc(
    env: EnvironmentStateV1,
    active: list[dict[str, Any]],
) -> dict[str, float]:
    """M5 — product illum × flare across overlapping solar-class events."""
    raw_illum = env.bc_solar.get("illum_frac")
    illum = float(raw_illum if raw_illum is not None else 0.96)
    flare = 1.0
    lo, hi = _flare_band()
    for step in active:
        eid = str(step.get("event_id") or "")
        params = step.get("params") or {}
        if eid in _SOLAR_EVENT_IDS:
            flare *= float(params.get("flare_multiplier") or 1.0)
        if eid in _ECLIPSE_EVENT_IDS:
            drop = min(float(params.get("illum_drop_frac") or 0.0), 1.0)
            illum *= 1.0 - drop
    flare = min(max(flare, lo), hi)
    illum = max(0.0, min(illum, 1.0))
    env.bc_solar["flare_multiplier"] = flare
    env.bc_solar["illum_frac"] = illum
    return dict(env.bc_solar)


def integrate_dust_window(
    env: EnvironmentStateV1,
    active: list[dict[str, Any]],
    *,
    dt_h: float,
) -> float:
    """M4 — rate x dt with saturation while ingress events active."""
    if not any(str(s.get("event_id")) in _INGRESS_EVENT_IDS for s in active):
        return 0.0
    zone = zone_from_regime(env.regime_id)
    if zone == "rim_sun":
        z = "rim_sun"
    elif env.regime_id == "psr_floor":
        z = "psr_floor"
    else:
        z = "massif_traverse"
    seal = str(env.dust.get("seal_class") or "B3")
    mit = float(env.dust.get("mitigation_duty") or 0.0)
    gap = float(env.dust.get("joint_gap_mm") or 0.5)
    dt_sols = earth_hours_to_lunar_sols(dt_h)
    prev = float(env.dust.get("loading_g_m2") or 0.0)
    acc = accumulation_after_sols(
        n_sols=dt_sols,
        zone=z,  # type: ignore[arg-type]
        seal_class=seal,  # type: ignore[arg-type]
        mitigation_duty=mit,
        joint_gap_mm=gap,
        prev_g_m2=prev,
    )
    new_load = float(acc.get("accumulation_g_m2") or prev)
    delta = new_load - prev
    env.dust["loading_g_m2"] = new_load
    env.dust["ingress_rate_g_m2_sol"] = float(acc.get("effective_rate_g_m2_per_sol") or ingress_rate_g_m2_per_sol(z))  # type: ignore[arg-type]
    env.dust["ingress_hazard_class"] = str(acc.get("ingress_hazard_class") or "")
    env.dust["saturated"] = 1.0 if acc.get("saturated") else 0.0
    return delta


def integrate_radiation_window(
    env: EnvironmentStateV1,
    active: list[dict[str, Any]],
    *,
    dt_h: float,
) -> float:
    """M3 — coupled albedo annual class × Rust rate×dt×flare (not year dump / not Python dD)."""
    from dogfood_platform.lunar_radiation_proxy_v1 import (
        evaluate_coupled_radiation_proxy,
        rust_window_dose,
    )

    shield = float(env.radiation.get("shield_areal_g_cm2") or 0.0)
    coupled = evaluate_coupled_radiation_proxy(mission_years=1.0, shield_g_cm2=shield)
    annual = float(coupled["mission_dose_gy"])
    annual_see = float(coupled["see_rate_per_year"])
    # Flare already merged into bc_solar by combine_active_solar_bc (M5) — do not re-product params.
    flare = float(env.bc_solar.get("flare_multiplier") or 1.0)
    lo, hi = _flare_band()
    flare = min(max(flare, lo), hi)
    dose_rate_extra = 1.0
    for step in active:
        params = step.get("params") or {}
        if "dose_rate_scale" in params:
            dose_rate_extra *= float(params["dose_rate_scale"])
    dose_rate_extra = min(max(dose_rate_extra, 1.0), hi)
    scale = min(flare * dose_rate_extra, hi)
    # Rust oracle once per (annual,see,scale,lo,hi) at dt=1h; scale linearly in dt (law is linear).
    cache_key = (round(annual, 12), round(annual_see, 12), round(scale, 12), lo, hi)
    rate_1h = _RAD_RATE_CACHE.get(cache_key)
    if rate_1h is None:
        rate_1h = rust_window_dose(
            annual_dose_gy=annual,
            annual_see_per_year=annual_see,
            dt_h=1.0,
            flare_scale=scale,
            flare_lo=lo,
            flare_hi=hi,
        )
        _RAD_RATE_CACHE[cache_key] = rate_1h
    d_dose = float(rate_1h["window_dose_gy"]) * float(dt_h)
    d_see = float(rate_1h["window_see_events"]) * float(dt_h)
    prev = float(env.radiation.get("dose_gy") or 0.0)
    new_dose = prev + d_dose
    env.radiation["dose_gy"] = new_dose
    env.radiation["dose_gy_accum"] = new_dose
    env.radiation["incident_dose_gy"] = float(coupled["incident_dose_gy"]) * (
        new_dose / max(annual, 1e-12)
    )
    env.radiation["albedo_dose_gy"] = float(coupled["albedo_dose_gy"]) * (
        new_dose / max(annual, 1e-12)
    )
    env.radiation["albedo_fraction"] = float(coupled["albedo_fraction"])
    env.radiation["see_rate_1_per_yr"] = annual_see * float(rate_1h["flare_scale"])
    env.radiation["see_events"] = float(env.radiation.get("see_events") or 0.0) + d_see
    env.radiation["shield_areal_g_cm2"] = shield
    env.radiation["tier"] = str(coupled.get("tier") or env.radiation.get("tier") or "PROXY_CHAT")
    env.radiation["flare_scale"] = float(rate_1h["flare_scale"])
    env.radiation["rate_oracle"] = rate_1h.get("oracle")
    env.radiation["rate_from_rust"] = True
    env.radiation["dose_rate_gy_per_h"] = float(rate_1h.get("dose_rate_gy_per_h") or 0.0)
    env.radiation["rate_cache_dt_scaled"] = True
    return d_dose


def integrate_timestep(
    env: EnvironmentStateV1,
    active: list[dict[str, Any]],
    *,
    dt_h: float,
) -> dict[str, Any]:
    """One timeline step — L_MAXWELL BC + L_POISSON column + L_STOCHASTIC dust + M3 rad."""
    env.t_h += dt_h
    env.active_windows = [
        ActiveWindow(
            event_id=str(s.get("event_id") or ""),
            law_id=str((s.get("event") or {}).get("law_id") or "L_GENERIC"),
            start_h=float(s.get("start_h") or 0.0),
            end_h=float(s.get("end_h") or 0.0),
        )
        for s in active
    ]
    combine_active_solar_bc(env, active)
    flux = flux_bc_from_env(env)
    q_in = float(flux["q_in_w_m2"])
    step_meta: dict[str, Any] = {}
    dT = step_column_implicit_1d(
        env.thermal_column,
        dt_h=dt_h,
        q_in_w_m2=q_in,
        regime_id=env.regime_id,
        step_meta=step_meta,
    )
    loading_d = integrate_dust_window(env, active, dt_h=dt_h)
    dose_d = integrate_radiation_window(env, active, dt_h=dt_h)
    tc = env.thermal_column
    row = {
        "t_h": env.t_h,
        "thermal_column_delta_k": dT,
        "thermal_surface_k": tc.t_surface_k,
        "thermal_subsurface_k": tc.t_subsurface_k,
        "subsurface_lag_k": tc.t_subsurface_k - tc.t_surface_k,
        "loading_delta_g_m2": loading_d,
        "loading_g_m2": float(env.dust.get("loading_g_m2") or 0.0),
        "dose_delta_gy": dose_d,
        "dose_gy": float(env.radiation.get("dose_gy") or 0.0),
        "radiation_flare_scale": float(env.radiation.get("flare_scale") or 1.0),
        "bc_solar": dict(env.bc_solar),
        "q_in_w_m2": q_in,
        "q_net_bind_w_m2": float(flux["q_net_bind_w_m2"]),
        "oblique_scale": float(flux.get("oblique_scale") or 1.0),
        "n_active": len(active),
    }
    if step_meta:
        row["integrator_meta"] = dict(step_meta)
    row.update(lunar_timeline_meta(env.t_h))
    return row


def integrate_laws(
    env: EnvironmentStateV1,
    scheduled: list[dict[str, Any]],
    *,
    horizon_h: float,
    dt_h: float = 0.25,
) -> tuple[list[dict[str, Any]], int]:
    """Timeline integrator; returns step log + overlap peak."""
    # Field accumulators start at 0 — fresh() seeds year-class rates, not mission dump.
    env.radiation["dose_gy"] = 0.0
    env.radiation["dose_gy_accum"] = 0.0
    env.radiation["see_events"] = 0.0
    steps: list[dict[str, Any]] = []
    peak = 0
    t = 0.0
    while t < horizon_h - 1e-9:
        active = [s for s in scheduled if float(s["start_h"]) <= t < float(s["end_h"])]
        peak = max(peak, len(active))
        row = integrate_timestep(env, active, dt_h=dt_h)
        row["t_start_h"] = round(t, 4)
        steps.append(row)
        t += dt_h
    return steps, peak


def sequential_merge_env(
    env: EnvironmentStateV1,
    scheduled: list[dict[str, Any]],
) -> EnvironmentStateV1:
    """Sequential hop merge (no overlap BC) — falsifier baseline."""
    from copy import deepcopy

    from dogfood_platform.universe_event_dispatch_v1 import apply_event, event_state_delta

    out = deepcopy(env)
    for step in sorted(scheduled, key=lambda s: (s["start_h"], s.get("seq", 0))):
        result = apply_event(step["event"], step["params"], env=out)
        delta = result.get("state_delta") or event_state_delta(step["event"], result)
        apply_state_delta(out, delta)
    return out


def apply_state_delta(env: EnvironmentStateV1, delta: dict[str, Any]) -> None:
    """Apply dispatch delta buckets onto EnvironmentStateV1."""
    if "solar" in delta:
        for k, v in delta["solar"].items():
            env.bc_solar[k] = float(v)
    if "vacuum_thermal" in delta:
        if "t_surf_k" in delta["vacuum_thermal"]:
            if env.thermal_column.t_k:
                env.thermal_column.t_k[0] = float(delta["vacuum_thermal"]["t_surf_k"])
        if "pressure_torr" in delta["vacuum_thermal"]:
            env.bc_vacuum["p_torr"] = float(delta["vacuum_thermal"]["pressure_torr"])
    if "dust_charge" in delta:
        m = delta["dust_charge"]
        if "mass_loading_g_m2" in m:
            env.dust["loading_g_m2"] = float(m["mass_loading_g_m2"])
        if "ingress_g_m2_per_sol" in m:
            env.dust["ingress_rate_g_m2_sol"] = float(m["ingress_g_m2_per_sol"])
        if "electrostatic_index" in m:
            env.dust["e_index"] = float(m["electrostatic_index"])
    if "radiation" in delta:
        key_map = {
            "dose_gy_accum": "dose_gy",
            "see_events": "see_rate_1_per_yr",
        }
        for k, v in delta["radiation"].items():
            key = key_map.get(k, k)
            if key == "tier":
                env.radiation["tier"] = str(v)
            else:
                env.radiation[key] = float(v)
    if "mechanical" in delta:
        env.mechanical.update({k: float(v) for k, v in delta["mechanical"].items()})
