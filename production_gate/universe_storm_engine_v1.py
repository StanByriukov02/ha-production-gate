"""Universe storm engine — compose storms · immerse targets (U2/U3)."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from production_gate.universe_event_dispatch_v1 import apply_event
from production_gate.universe_event_sampler_v1 import (
    draw_event_params,
    load_event_catalog,
    sample_events_stratified,
)
from production_gate.universe_immersion_v1 import (
    check_budget,
    event_applies_to_target,
    load_immersion_bind,
    load_target,
    susceptibility_weight,
)

_REPO = Path(__file__).resolve().parents[1]
_STORM_BIND = _REPO / "results" / "platform_bpass" / "universe" / "STORM_PROFILE_BIND_v1.json"
_OUT = _REPO / "results" / "platform_bpass" / "universe"

TargetId = Literal["chip", "robot", "panel", "rocket"]


def load_storm_bind(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _STORM_BIND).read_text(encoding="utf-8"))


def _event_by_id(catalog: dict[str, Any], event_id: str) -> dict[str, Any] | None:
    for ev in catalog.get("events") or []:
        if ev.get("event_id") == event_id:
            return ev
    return None


def _scale_params(params: dict[str, Any], intensity: float) -> dict[str, Any]:
    out = dict(params)
    for key in ("flare_multiplier", "dose_gy", "mass_loading_g_m2", "n_sols", "mass_g", "see_count"):
        if key in out and isinstance(out[key], (int, float)):
            out[key] = float(out[key]) * intensity
    return out


def compose_storm(
    storm_id: str,
    *,
    seed: int = 20260616,
    intensity_scale: float = 1.0,
    catalog: dict[str, Any] | None = None,
    storm_bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    storms = load_storm_bind(storm_bind)
    profile = next((s for s in storms.get("storms") or [] if s.get("storm_id") == storm_id), None)
    if not profile:
        raise KeyError(f"unknown storm_id: {storm_id}")
    cat = catalog or load_event_catalog()
    rng = random.Random(seed)
    event_ids: list[str] = list(profile.get("events") or [])
    if profile.get("random_compose"):
        rc = profile["random_compose"]
        n = int(rc.get("n_events") or 12)
        rows = sample_events_stratified(n_runs=n, seed=seed, catalog=cat)
        event_ids = [r["event"]["event_id"] for r in rows]
    sequence: list[dict[str, Any]] = []
    for i, eid in enumerate(event_ids):
        ev = _event_by_id(cat, eid)
        if not ev:
            continue
        params = draw_event_params(ev, rng)
        typ = profile.get("typical_numbers") or {}
        for k, v in typ.items():
            params.setdefault(k, v)
        params = _scale_params(params, intensity_scale)
        sequence.append(
            {
                "seq": i,
                "event_id": eid,
                "event": ev,
                "params": params,
            }
        )
    return {
        "storm_id": storm_id,
        "name": profile.get("name"),
        "intensity_scale": intensity_scale,
        "seed": seed,
        "n_events": len(sequence),
        "adversarial": bool(profile.get("adversarial")),
        "sequence": sequence,
    }


def compose_random_storm(*, n_events: int = 12, seed: int = 20260616) -> dict[str, Any]:
    return compose_storm("STORM-RANDOM", seed=seed, intensity_scale=1.0)


def _accumulate_metric(metrics: dict[str, float], eps: dict[str, Any], weight: float) -> None:
    name = str(eps.get("name") or "")
    val = eps.get("value")
    if val is None:
        return
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return
    if name in ("see_wear_mv", "tid_wear_mv", "radiation_delta_vth_mv"):
        metrics["radiation_delta_vth_mv"] = metrics.get("radiation_delta_vth_mv", 0.0) + fval * weight
    elif name == "final_wear_mv":
        metrics["final_wear_mv"] = max(metrics.get("final_wear_mv", 0.0), fval)
    elif name == "delta_c_frac":
        metrics["delta_c_frac_min"] = min(metrics.get("delta_c_frac_min", 0.0), fval)
    elif name == "drift_mm":
        metrics["drift_mm_min"] = max(metrics.get("drift_mm_min", 0.0), fval)
    elif name == "mass_g":
        metrics["hull_micrometeoroid_hits"] = metrics.get("hull_micrometeoroid_hits", 0.0) + 1.0
        metrics["hull_mass_g_total"] = metrics.get("hull_mass_g_total", 0.0) + fval
    elif name == "q_solar_scaled":
        metrics["thermal_swing_k"] = max(metrics.get("thermal_swing_k", 0.0), fval / 50.0)
    elif name == "mlcc_jerk_peak" or "jerk" in name:
        metrics["structural_jerk_peak"] = max(metrics.get("structural_jerk_peak", 0.0), fval)
    elif name == "cumulative_loading_g_m2":
        metrics["accumulation_g_m2"] = max(metrics.get("accumulation_g_m2", 0.0), fval)


def immerse_target(
    target_id: str,
    storm: dict[str, Any],
    *,
    full_run: bool = False,
) -> dict[str, Any]:
    if target_id == "rocket":
        from production_gate.rocket_storm_target_v1 import immerse_rocket_target

        result = immerse_rocket_target(storm, full_run=full_run)
        result["immersion_ui"] = str(
            (result.get("immersion_ui") or "ACTIVE")
        )
        return result

    target = load_target(target_id)
    metrics: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    applied = 0
    skipped = 0
    for step in storm.get("sequence") or []:
        ev = step["event"]
        if not event_applies_to_target(ev, target):
            skipped += 1
            rows.append(
                {
                    "seq": step["seq"],
                    "event_id": step["event_id"],
                    "verdict": "SKIP",
                    "reason": "no_coupling_to_target",
                }
            )
            continue
        weight = susceptibility_weight(target, str(ev.get("law_id")))
        if weight <= 0:
            skipped += 1
            rows.append({"seq": step["seq"], "event_id": step["event_id"], "verdict": "SKIP", "reason": "zero_susceptibility"})
            continue
        result = apply_event(ev, step["params"], full=full_run)
        eps = result.get("epsilon") or {}
        _accumulate_metric(metrics, eps, weight)
        if target_id == "chip" and "radiation_delta_vth_mv" in str(result.get("effect") or {}):
            eff = result.get("effect") or {}
            if "radiation_delta_vth_mv" in eff:
                metrics["radiation_delta_vth_mv"] = float(eff["radiation_delta_vth_mv"]) * weight
        applied += 1
        rows.append(
            {
                "seq": step["seq"],
                "event_id": step["event_id"],
                "law_id": ev.get("law_id"),
                "verdict": result.get("verdict"),
                "weight": weight,
                "epsilon": eps,
            }
        )
    event_pass = sum(1 for r in rows if r.get("verdict") == "PASS")
    event_fail = sum(1 for r in rows if r.get("verdict") == "FAIL")
    budget = check_budget(target_id, metrics)
    if applied == 0:
        verdict = "SKIP"
    elif event_fail > 0:
        verdict = "FAIL"
    elif not budget.get("within_budget", True):
        verdict = "FAIL"
    else:
        verdict = "PASS"
    payload = {
        "immersion_id": f"IMM-{target_id}-{storm.get('storm_id')}",
        "target_id": target_id,
        "storm_id": storm.get("storm_id"),
        "storm_name": storm.get("name"),
        "intensity_scale": storm.get("intensity_scale"),
        "seed": storm.get("seed"),
        "events_applied": applied,
        "events_skipped": skipped,
        "events_pass": event_pass,
        "events_fail": event_fail,
        "aggregate_metrics": {k: round(v, 6) for k, v in metrics.items()},
        "budget": budget,
        "steps": rows,
        "verdict": verdict,
    }
    return payload


def immerse_in_storm_concurrent(
    target_id: str,
    storm_id: str,
    *,
    seed: int = 20260616,
    intensity_scale: float = 1.0,
    horizon_h: float = 48.0,
) -> dict[str, Any]:
    from production_gate.universe_storm_state_v1 import run_concurrent_storm

    storm = compose_storm(storm_id, seed=seed, intensity_scale=intensity_scale)
    concurrent = run_concurrent_storm(storm, horizon_h=horizon_h)
    seq_result = immerse_target(target_id, storm)
    env = concurrent["env_state"]
    seq_result["composition"] = "concurrent"
    seq_result["overlap_peak"] = concurrent["overlap_peak"]
    seq_result["env_state"] = env
    seq_result["schedule"] = concurrent["schedule"]
    seq_result["state_bus_verdict"] = concurrent["verdict"]
    if seq_result["verdict"] == "PASS" and concurrent["verdict"] == "FAIL":
        seq_result["verdict"] = "FAIL"
    return seq_result


def immerse_in_storm(
    target_id: str,
    storm_id: str,
    *,
    seed: int = 20260616,
    intensity_scale: float = 1.0,
    full_run: bool = False,
) -> dict[str, Any]:
    storm = compose_storm(storm_id, seed=seed, intensity_scale=intensity_scale)
    return immerse_target(target_id, storm, full_run=full_run)


def run_storm_matrix(
    *,
    targets: list[str] | None = None,
    storms: list[str] | None = None,
    seed: int = 20260616,
    intensity_scale: float = 1.0,
    recommended_only: bool = True,
) -> dict[str, Any]:
    bind = load_storm_bind()
    all_targets = list((load_immersion_bind().get("targets") or {}).keys())
    tgts = targets or all_targets
    profiles = [s for s in bind.get("storms") or [] if s.get("storm_id") != "STORM-RANDOM"]
    if storms:
        profiles = [p for p in profiles if p.get("storm_id") in storms]
    results: list[dict[str, Any]] = []
    for profile in profiles:
        sid = str(profile.get("storm_id"))
        storm = compose_storm(sid, seed=seed, intensity_scale=intensity_scale)
        rec = profile.get("targets_recommended") or tgts
        run_tgts = [t for t in rec if t in tgts] if recommended_only else tgts
        for tid in run_tgts:
            results.append(immerse_target(tid, storm))
    k_pass = sum(1 for r in results if r["verdict"] == "PASS")
    k_skip = sum(1 for r in results if r["verdict"] == "SKIP")
    applicable = [r for r in results if r["verdict"] != "SKIP"]
    k_applicable = len(applicable)
    k_pass_app = sum(1 for r in applicable if r["verdict"] == "PASS")
    return {
        "matrix_id": "UNIVERSE_STORM_IMMERSION_MATRIX_v1",
        "seed": seed,
        "intensity_scale": intensity_scale,
        "n_cells": len(results),
        "skip_count": k_skip,
        "pass_count": k_pass,
        "applicable_count": k_applicable,
        "applicable_pass_count": k_pass_app,
        "pass_rate": round(k_pass / max(len(results), 1), 6),
        "applicable_pass_rate": round(k_pass_app / max(k_applicable, 1), 6),
        "verdict": "PASS" if k_applicable > 0 and k_pass_app == k_applicable else "FAIL",
        "cells": results,
    }


def write_immersion_receipt(
    target_id: str,
    storm_id: str,
    *,
    seed: int = 20260616,
    intensity_scale: float = 1.0,
) -> dict[str, Any]:
    result = immerse_in_storm(target_id, storm_id, seed=seed, intensity_scale=intensity_scale)
    _OUT.mkdir(parents=True, exist_ok=True)
    slug = f"IMMERSION_{target_id.upper()}_{storm_id.replace('-', '_')}_v1.json"
    path = _OUT / slug
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    result["receipt"] = str(path.relative_to(_REPO)).replace("\\", "/")
    return result


def catalog_storms() -> list[dict[str, Any]]:
    return list(load_storm_bind().get("storms") or [])


def selftest() -> None:
    from production_gate.universe_immersion_v1 import list_target_ids

    for tid in list_target_ids():
        storm_id = "STORM-CME-MAX" if tid == "rocket" else "STORM-THERMAL-ECLIPSE"
        r = immerse_in_storm(tid, storm_id, seed=42, intensity_scale=0.8)
        if r["events_applied"] < 1:
            raise AssertionError(f"no events applied for {tid}: {r}")
    matrix = run_storm_matrix(seed=20260616, intensity_scale=0.85)
    if matrix["applicable_pass_rate"] < 0.75:
        raise AssertionError(f"storm matrix too many fails: {matrix['applicable_pass_rate']}")
    cc = immerse_in_storm_concurrent("chip", "STORM-THERMAL-ECLIPSE", seed=7)
    if cc.get("overlap_peak", 0) < 1:
        raise AssertionError(cc)
    from production_gate.universe_event_dispatch_v1 import macro_cosmic_dispatch_audit

    audit = macro_cosmic_dispatch_audit()
    if audit["verdict"] != "PASS":
        raise AssertionError(audit)
