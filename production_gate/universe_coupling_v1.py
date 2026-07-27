"""Universe chip world — mechanical → fab/wear coupling contract v1.

Scales load from world_chip_coupling_v1.json — not airborne module literals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_COUPLING = _REPO / "results" / "platform_bpass" / "universe" / "world_chip_coupling_v1.json"


def load_coupling_contract(path: Path | None = None) -> dict[str, Any]:
    p = path or _COUPLING
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def coupling_teaching_scales(contract: dict[str, Any] | None = None) -> dict[str, float]:
    """Cited teaching scales from coupling contract (single owner)."""
    data = contract or load_coupling_contract()
    fields = data.get("fields") or {}
    duty = fields.get("duty_cycle_proxy") or {}
    drift = fields.get("delta_t_c_proxy_k") or {}
    stress = fields.get("stress_index_multiplier") or {}
    jerk_ref = float(duty.get("normalize_ref"))
    drift_scale = float(drift.get("scale"))
    stress_coeff = float(stress.get("coeff") if stress.get("coeff") is not None else 0.15)
    return {
        "jerk_normalize_ref": jerk_ref,
        "drift_scale": drift_scale,
        "stress_coeff": stress_coeff,
    }


def mechanical_coupling_slice(symplectic_metrics: dict[str, Any]) -> dict[str, Any]:
    """Map native symplectic spike metrics → CouplingSlice_v1."""
    scales = coupling_teaching_scales()
    jerk_ref = scales["jerk_normalize_ref"]
    drift_scale = scales["drift_scale"]
    stress_coeff = scales["stress_coeff"]
    jerk = float(symplectic_metrics.get("mlcc_jerk_peak") or 0.0)
    drift = float(symplectic_metrics.get("energy_drift_rms_rel") or 0.0)
    duty = max(0.0, min(1.0, jerk / jerk_ref))
    delta_t = drift * drift_scale
    stress_mult = 1.0 + stress_coeff * duty
    return {
        "slice_id": "CouplingSlice_v1",
        "duty_cycle_proxy": round(duty, 6),
        "delta_t_c_proxy_k": round(delta_t, 6),
        "stress_index_multiplier": round(stress_mult, 6),
        "source_backend": symplectic_metrics.get("backend_id", "symplectic_euler_v0"),
        "mlcc_jerk_peak": jerk,
        "energy_drift_rms_rel": drift,
        "honesty": {
            "scales_from_coupling_contract": True,
            "teaching_unit_bridge": True,
            "not_measured_jerk_sensor": True,
        },
        "jerk_normalize_ref": jerk_ref,
    }


def apply_wear_coupling(
    wear_eps: dict[str, Any],
    coupling: dict[str, Any] | None,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scale wear epsilon budget by mechanical stress proxy."""
    del contract
    mult = float((coupling or {}).get("stress_index_multiplier") or 1.0)
    measured = dict(wear_eps.get("measured") or {})
    abs_err = float(measured.get("abs_err_mv") or 0.0)
    base_tol = float(measured.get("base_tol_mv") or 0.05)
    scaled_tol = base_tol * mult
    measured["stress_index_multiplier"] = mult
    measured["abs_err_mv_scaled"] = round(abs_err * mult, 6)
    measured["base_tol_mv"] = base_tol
    measured["scaled_tol_mv"] = round(scaled_tol, 6)
    out = dict(wear_eps)
    out["measured"] = measured
    if "abs_err_mv" in (wear_eps.get("measured") or {}):
        out["within_budget"] = abs_err * mult <= scaled_tol and bool(wear_eps.get("within_budget"))
    else:
        out["within_budget"] = bool(wear_eps.get("within_budget"))
    out["coupling_applied"] = coupling is not None
    return out


def validate_coupling_falsifier(
    slice_a: dict[str, Any],
    slice_b: dict[str, Any],
) -> bool:
    """True if slices differ when mechanical inputs differ (coupling alive)."""
    keys = ("duty_cycle_proxy", "stress_index_multiplier", "delta_t_c_proxy_k")
    return any(slice_a.get(k) != slice_b.get(k) for k in keys)
