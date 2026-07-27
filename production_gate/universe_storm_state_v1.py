"""Concurrent storm environment state — shared env trajectory on universe_state_v1 (U3)."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from production_gate.universe_event_dispatch_v1 import apply_event, event_state_delta
from production_gate.universe_state_v1 import EpsilonRow, HopState, UniverseStateBus

_REPO = Path(__file__).resolve().parents[1]
_ENV_BIND = _REPO / "results" / "platform_bpass" / "universe" / "ENV_DRIVER_BIND_v1.json"
_OUT = _REPO / "results" / "platform_bpass" / "universe"

_DEFAULT_HORIZON_H = 48.0


def _sha256_inputs(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_env_driver_defaults() -> dict[str, Any]:
    if not _ENV_BIND.is_file():
        return {}
    return json.loads(_ENV_BIND.read_text(encoding="utf-8"))


def _storm_dust_ingress(dust_ax: dict[str, Any]) -> float:
    from production_gate.lunar_dust_ingress_v1 import ingress_rate_g_m2_per_sol

    try:
        return float(ingress_rate_g_m2_per_sol("rim_sun"))
    except (FileNotFoundError, KeyError):
        row = dust_ax.get("ingress_g_m2_per_sol") or {}
        if "typical" not in row:
            raise KeyError("dust ingress missing from DUST_INGRESS_BIND and ENV_DRIVER") from None
        return float(row["typical"])


def _storm_dust_e_index(dust_ax: dict[str, Any]) -> float:
    from production_gate.lunar_dust_ingress_v1 import electrostatic_index

    try:
        return float(electrostatic_index("rim_sun")["electrostatic_index"])
    except (FileNotFoundError, KeyError):
        row = dust_ax.get("electrostatic_index") or {}
        if "typical" not in row:
            raise KeyError("dust e_index missing from DUST_INGRESS_BIND and ENV_DRIVER") from None
        return float(row["typical"])


def event_duration_h(event: dict[str, Any], params: dict[str, Any]) -> float:
    if "duration_h" in params:
        return float(params["duration_h"])
    name = str(event.get("name") or "")
    scale = str(event.get("scale_class") or "meso")
    if "eclipse" in name or "pump" in name or "chamber" in name:
        return float(params.get("duration_h") or 2.0)
    if scale == "cosmic":
        return float(params.get("exposure_yr") or 0.5) * 8760.0 if "exposure" in str(params) else 6.0
    if scale == "macro":
        n_sols = float(params.get("n_sols") or 0.0)
        return max(n_sols * 24.0, 4.0) if n_sols > 0 else 8.0
    return 1.0


@dataclass
class StormEnvironmentState:
    storm_id: str
    seed: int
    horizon_h: float
    solar: dict[str, float] = field(default_factory=lambda: {"flare_multiplier": 1.0, "q_solar_w_m2": 1361.0, "illum_frac": 0.96})
    vacuum_thermal: dict[str, float] = field(default_factory=lambda: {"t_surf_k": 220.0, "pressure_torr": 1e-6})
    dust_charge: dict[str, float] = field(default_factory=lambda: {"mass_loading_g_m2": 0.0, "ingress_g_m2_per_sol": 0.08, "electrostatic_index": 0.85})
    radiation: dict[str, float] = field(default_factory=lambda: {"dose_gy_accum": 0.0, "see_events": 0.0})
    mechanical: dict[str, float] = field(default_factory=lambda: {"jerk_peak": 0.0, "impulse_scale": 1.0})
    timeline: list[dict[str, Any]] = field(default_factory=list)
    overlap_peak: int = 0

    @classmethod
    def fresh(cls, storm_id: str, *, seed: int, horizon_h: float = _DEFAULT_HORIZON_H) -> StormEnvironmentState:
        env = load_env_driver_defaults()
        axes = env.get("driver_axes") or {}
        solar_ax = axes.get("solar") or {}
        vac_ax = axes.get("vacuum_thermal") or {}
        dust_ax = axes.get("dust_charge") or {}
        return cls(
            storm_id=storm_id,
            seed=seed,
            horizon_h=horizon_h,
            solar={
                "flare_multiplier": float((solar_ax.get("flare_multiplier") or {}).get("typical") or 1.0),
                "q_solar_w_m2": float((solar_ax.get("solar_constant_w_m2") or {}).get("typical") or 1361.0),
                "illum_frac": float((solar_ax.get("illum_frac_rim") or {}).get("typical") or 0.96),
            },
            vacuum_thermal={
                "t_surf_k": float((vac_ax.get("t_rim_surf_k") or {}).get("typical") or 220.0),
                "pressure_torr": float((vac_ax.get("pressure_torr") or {}).get("typical") or 1e-6),
            },
            dust_charge={
                "mass_loading_g_m2": 0.0,
                "ingress_g_m2_per_sol": float(_storm_dust_ingress(dust_ax)),
                "electrostatic_index": float(_storm_dust_e_index(dust_ax)),
            },
        )

    def merge_delta(self, delta: dict[str, Any], *, event_id: str, start_h: float, end_h: float) -> None:
        for axis, patch in (delta or {}).items():
            bucket = getattr(self, axis, None)
            if not isinstance(bucket, dict):
                continue
            for k, v in patch.items():
                if k.endswith("_accum") or k.endswith("_events") or k == "mass_loading_g_m2" or k == "dose_gy_accum":
                    bucket[k] = float(bucket.get(k, 0.0)) + float(v)
                elif k in ("jerk_peak", "q_solar_w_m2", "flare_multiplier"):
                    bucket[k] = max(float(bucket.get(k, 0.0)), float(v))
                else:
                    bucket[k] = float(v)
        self.timeline.append({"event_id": event_id, "start_h": start_h, "end_h": end_h, "delta": delta})

    def active_count_at(self, t_h: float, windows: list[dict[str, Any]]) -> int:
        return sum(1 for w in windows if w["start_h"] <= t_h < w["end_h"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "storm_id": self.storm_id,
            "seed": self.seed,
            "horizon_h": self.horizon_h,
            "solar": self.solar,
            "vacuum_thermal": self.vacuum_thermal,
            "dust_charge": self.dust_charge,
            "radiation": self.radiation,
            "mechanical": self.mechanical,
            "overlap_peak": self.overlap_peak,
            "n_timeline": len(self.timeline),
        }


def schedule_concurrent(
    sequence: list[dict[str, Any]],
    *,
    seed: int,
    horizon_h: float = _DEFAULT_HORIZON_H,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    scheduled: list[dict[str, Any]] = []
    for step in sequence:
        ev = step["event"]
        params = step["params"]
        dur = event_duration_h(ev, params)
        max_start = max(horizon_h - dur, 0.0)
        start = rng.uniform(0.0, max_start) if max_start > 0 else 0.0
        scheduled.append(
            {
                **step,
                "start_h": round(start, 4),
                "end_h": round(start + dur, 4),
                "duration_h": round(dur, 4),
            }
        )
    scheduled.sort(key=lambda r: (r["start_h"], r.get("seq", 0)))
    return scheduled


def compute_overlap_peak(windows: list[dict[str, Any]], *, step_h: float = 0.25) -> int:
    if not windows:
        return 0
    end = max(w["end_h"] for w in windows)
    peak = 0
    t = 0.0
    while t <= end:
        n = sum(1 for w in windows if w["start_h"] <= t < w["end_h"])
        peak = max(peak, n)
        t += step_h
    return peak


def run_concurrent_storm_env_physics(
    storm: dict[str, Any],
    *,
    horizon_h: float = _DEFAULT_HORIZON_H,
    dt_h: float = 0.25,
    full_run: bool = False,
    native_c06: bool = False,
    shield_g_cm2: float | None = None,
) -> dict[str, Any]:
    """U4 integrator — timeline law merge on EnvironmentStateV1."""
    from copy import deepcopy

    from production_gate.universe_env_merge_v1 import integrate_laws, sequential_merge_env
    from production_gate.universe_env_state_v1 import fresh as env_fresh

    seed = int(storm.get("seed") or 0)
    sid = str(storm.get("storm_id") or "STORM")
    env = env_fresh(sid, seed=seed, regime_id="rim_sunlit")
    if shield_g_cm2 is not None:
        env.radiation["shield_areal_g_cm2"] = float(shield_g_cm2)
    env0 = deepcopy(env)
    scheduled = schedule_concurrent(storm.get("sequence") or [], seed=seed, horizon_h=horizon_h)
    steps, overlap_peak = integrate_laws(env, scheduled, horizon_h=horizon_h, dt_h=dt_h)
    seq_env = sequential_merge_env(env0, scheduled)

    hops: list[HopState] = []
    eps_rows: list[EpsilonRow] = []
    backends: list[str] = []
    fail = 0
    for i, step in enumerate(scheduled):
        ev = step["event"]
        eid = str(ev.get("event_id") or "")
        use_full = full_run or (native_c06 and eid == "EVT-C-06")
        result = apply_event(ev, step["params"], full=use_full, env=env)
        delta = result.get("state_delta") or event_state_delta(ev, result)
        hop_id = f"storm-hop-{i:03d}"
        backend = str(ev.get("backend") or "dispatch")
        backends.append(backend)
        verdict = str(result.get("verdict") or "FAIL")
        if verdict == "FAIL":
            fail += 1
        eps = result.get("epsilon") or {}
        hops.append(
            HopState(
                hop_id=hop_id,
                law_id=str(ev.get("law_id") or "L_GENERIC"),
                backend=backend,
                verdict=verdict,
                state_delta=delta,
                epsilon_row=eps,
            )
        )
        eps_rows.append(
            EpsilonRow(
                hop_id=hop_id,
                epsilon_name=str(eps.get("name") or "unknown"),
                measured={"value": eps.get("value"), "unit": eps.get("unit", "")},
                unit=str(eps.get("unit") or ""),
                within_budget=verdict == "PASS",
            )
        )

    t_final = env.thermal_column.t_surface_k
    t_sub_final = env.thermal_column.t_subsurface_k
    t_seq = seq_env.thermal_column.t_surface_k
    subsurface_lag_k = t_sub_final - t_final
    overlap_physics_differ = abs(t_final - t_seq) > 1e-6 if overlap_peak > 1 else True
    dose_final = float(env.radiation.get("dose_gy") or 0.0)
    dose_deltas = [float(s.get("dose_delta_gy") or 0.0) for s in steps]
    mean_flare = (
        sum(float(s.get("radiation_flare_scale") or 1.0) for s in steps) / max(len(steps), 1)
    )

    inputs = {"storm_id": sid, "seed": seed, "horizon_h": horizon_h, "n_events": len(scheduled), "u4": True}
    bus_env = env.to_bus_env()
    bus = UniverseStateBus(
        bus_id=f"STORM-ENV-{sid}",
        world_id="W_universe",
        corridor_id="storm_env_physics_v1",
        inputs_hash=_sha256_inputs(inputs),
        hops=hops,
        epsilon=eps_rows,
        metric={
            **bus_env,
            "events_fail": fail,
            "composition": "concurrent_env_physics",
            "overlap_peak": overlap_peak,
            "thermal_column_final_k": t_final,
            "thermal_subsurface_final_k": t_sub_final,
            "subsurface_lag_k": subsurface_lag_k,
            "integrator": "implicit_1d_backward_euler",
            "thermal_column_sequential_k": t_seq,
            "overlap_physics_differ": overlap_physics_differ,
            "n_integrator_steps": len(steps),
            "native_c06": native_c06,
            "dose_gy_final": dose_final,
            "radiation_mean_flare_scale": mean_flare,
        },
        verdict="PASS" if fail == 0 else "FAIL",
        backend_manifest=sorted(set(backends)),
    )
    verdict = bus.verdict
    if overlap_peak > 1 and not overlap_physics_differ:
        verdict = "FAIL"
    return {
        "mode": "concurrent_env_physics",
        "storm_id": storm.get("storm_id"),
        "seed": seed,
        "horizon_h": horizon_h,
        "overlap_peak": overlap_peak,
        "overlap_physics_differ": overlap_physics_differ,
        "thermal_column_final_k": t_final,
        "thermal_subsurface_final_k": t_sub_final,
        "subsurface_lag_k": subsurface_lag_k,
        "integrator": "implicit_1d_backward_euler",
        "thermal_column_sequential_k": t_seq,
        "integrator_steps": len(steps),
        "dose_gy_final": dose_final,
        "dose_delta_sum_gy": round(sum(dose_deltas), 12),
        "radiation_mean_flare_scale": mean_flare,
        "shield_g_cm2": float(env.radiation.get("shield_areal_g_cm2") or 0.0),
        "schedule": [{"event_id": s["event_id"], "start_h": s["start_h"], "end_h": s["end_h"]} for s in scheduled],
        "env_state": bus_env,
        "state_bus": bus.to_dict(),
        "verdict": verdict,
    }


def run_concurrent_storm(
    storm: dict[str, Any],
    *,
    horizon_h: float = _DEFAULT_HORIZON_H,
    full_run: bool = False,
    native_c06: bool = False,
) -> dict[str, Any]:
    state = StormEnvironmentState.fresh(
        str(storm.get("storm_id") or "STORM"),
        seed=int(storm.get("seed") or 0),
        horizon_h=horizon_h,
    )
    scheduled = schedule_concurrent(storm.get("sequence") or [], seed=int(storm.get("seed") or 0), horizon_h=horizon_h)
    state.overlap_peak = compute_overlap_peak(scheduled)
    hops: list[HopState] = []
    eps_rows: list[EpsilonRow] = []
    backends: list[str] = []
    fail = 0
    for i, step in enumerate(scheduled):
        ev = step["event"]
        eid = str(ev.get("event_id") or "")
        use_full = full_run or (native_c06 and eid == "EVT-C-06")
        result = apply_event(ev, step["params"], full=use_full)
        delta = event_state_delta(ev, result)
        state.merge_delta(delta, event_id=eid, start_h=step["start_h"], end_h=step["end_h"])
        hop_id = f"storm-hop-{i:03d}"
        backend = str(ev.get("backend") or "dispatch")
        backends.append(backend)
        verdict = str(result.get("verdict") or "FAIL")
        if verdict == "FAIL":
            fail += 1
        eps = result.get("epsilon") or {}
        hops.append(
            HopState(
                hop_id=hop_id,
                law_id=str(ev.get("law_id") or "L_GENERIC"),
                backend=backend,
                verdict=verdict,
                state_delta=delta,
                epsilon_row=eps,
            )
        )
        eps_rows.append(
            EpsilonRow(
                hop_id=hop_id,
                epsilon_name=str(eps.get("name") or "unknown"),
                measured={"value": eps.get("value"), "unit": eps.get("unit", "")},
                unit=str(eps.get("unit") or ""),
                within_budget=verdict == "PASS",
            )
        )
    inputs = {"storm_id": state.storm_id, "seed": state.seed, "horizon_h": horizon_h, "n_events": len(scheduled)}
    bus = UniverseStateBus(
        bus_id=f"STORM-ENV-{state.storm_id}",
        world_id="W_universe",
        corridor_id="storm_concurrent_v1",
        inputs_hash=_sha256_inputs(inputs),
        hops=hops,
        epsilon=eps_rows,
        metric={**state.to_dict(), "events_fail": fail, "composition": "concurrent", "native_c06": native_c06},
        verdict="PASS" if fail == 0 else "FAIL",
        backend_manifest=sorted(set(backends)),
    )
    return {
        "mode": "concurrent",
        "storm_id": storm.get("storm_id"),
        "seed": storm.get("seed"),
        "horizon_h": horizon_h,
        "overlap_peak": state.overlap_peak,
        "schedule": [{"event_id": s["event_id"], "start_h": s["start_h"], "end_h": s["end_h"]} for s in scheduled],
        "env_state": state.to_dict(),
        "state_bus": bus.to_dict(),
        "verdict": bus.verdict,
    }


def write_concurrent_storm_receipt(storm: dict[str, Any], *, horizon_h: float = _DEFAULT_HORIZON_H) -> dict[str, Any]:
    result = run_concurrent_storm(storm, horizon_h=horizon_h)
    _OUT.mkdir(parents=True, exist_ok=True)
    slug = f"STORM_CONCURRENT_{str(storm.get('storm_id')).replace('-', '_')}_v1.json"
    path = _OUT / slug
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    bus_path = _OUT / f"STORM_STATE_BUS_{str(storm.get('storm_id')).replace('-', '_')}_v1.json"
    bus_path.write_text(json.dumps(result["state_bus"], indent=2) + "\n", encoding="utf-8")
    result["receipt"] = str(path.relative_to(_REPO)).replace("\\", "/")
    result["state_bus_path"] = str(bus_path.relative_to(_REPO)).replace("\\", "/")
    return result


def selftest() -> None:
    from production_gate.universe_storm_engine_v1 import compose_storm

    storm = compose_storm("STORM-THERMAL-ECLIPSE", seed=11)
    r = run_concurrent_storm(storm, horizon_h=24.0)
    if r["overlap_peak"] < 1:
        raise AssertionError(r)
    if r["env_state"]["n_timeline"] < 1:
        raise AssertionError(r)
    if r["verdict"] not in ("PASS", "FAIL"):
        raise AssertionError(r)
