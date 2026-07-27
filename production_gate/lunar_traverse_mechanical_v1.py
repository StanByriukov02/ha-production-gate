"""Shackleton rim→floor traverse → W_chip CouplingSlice_v1 mechanical proxy.

Jerk severity tracks Rust Bekker Dual consequence (Rc, sinkage, drawbar deficit),
not magic-only ADAPT theater. Teaching scale bridges to chip coupling units.
"""
from __future__ import annotations

from typing import Any

from production_gate.lunar_regolith_bearing_v1 import shackleton_default_bearing_state
from production_gate.lunar_site_geometry_v1 import shackleton_path_profile
from production_gate.lunar_zone_table_v1 import ZONES
from production_gate.terramech_bekker_on_v1 import ORACLE as BEKKER_ORACLE
from production_gate.terramech_bekker_on_v1 import physics_row_for_dual
from production_gate.universe_coupling_v1 import mechanical_coupling_slice

# L0: SK-02 depth 4.1 km · SK-13 slope ≤15° · GAP-MR-11 bearing · GAP-MR-07 path profile
_CRATER_DEPTH_KM = 4.1


def _jerk_teaching_scale() -> float:
    """Teaching jerk normalize from coupling contract — not airborne literal."""
    from production_gate.universe_coupling_v1 import coupling_teaching_scales

    return float(coupling_teaching_scales()["jerk_normalize_ref"])


def _bekker_severity(physics: dict[str, Any], *, baseline: dict[str, Any] | None = None) -> dict[str, float]:
    """Map Bekker Dual row → dimensionless severity (Hostile louder than Safe firm)."""
    rc = float(physics.get("compaction_resistance_n") or 0.0)
    sink = float(physics.get("sinkage_mm") or 0.0)
    drawbar = float(physics.get("drawbar_pull_n") or 0.0)
    base = baseline or {}
    rc0 = float(base.get("compaction_resistance_n") or max(rc, 1.0))
    sink0 = float(base.get("sinkage_mm") or 1.0)
    db0 = float(base.get("drawbar_pull_n") or max(drawbar, 1.0))
    rc_term = min(rc / max(rc0, 1e-6), 5.0)
    sink_term = min(max(sink - sink0, 0.0) / 40.0, 5.0)
    # Low drawbar (soft) raises severity vs firm baseline.
    drawbar_deficit = max(0.0, db0 - drawbar)
    db_term = min(drawbar_deficit / max(db0, 1e-6), 5.0)
    risk_boost = 1.25 if physics.get("sinkage_risk") else 1.0
    severity = (0.4 * rc_term + 0.35 * sink_term + 0.25 * db_term) * risk_boost
    return {
        "severity": max(severity, 0.05),
        "rc_n": rc,
        "sinkage_mm": sink,
        "drawbar_pull_n": drawbar,
        "rc_term": rc_term,
        "sink_term": sink_term,
        "drawbar_deficit_term": db_term,
    }


def traverse_symplectic_proxy(
    *,
    soil_id: str = "lunar_firm_proxy",
    g_mps2: float = 1.62,
    baseline_soil_id: str = "lunar_firm_proxy",
) -> dict[str, Any]:
    """Map lunar traverse + Rust Bekker → symplectic spike metrics (W_chip u-hop-mechanical)."""
    massif = ZONES["massif_traverse"]
    slope_deg = float(massif["slope_max_deg"])
    limit_deg = float(massif["slope_limit_deg"])
    physics = physics_row_for_dual(soil_id, g_mps2=g_mps2)
    baseline = (
        physics
        if soil_id == baseline_soil_id
        else physics_row_for_dual(baseline_soil_id, g_mps2=g_mps2)
    )
    sev = _bekker_severity(physics, baseline=baseline)
    bearing = shackleton_default_bearing_state()
    # Slope adjunct (ADAPT zone) — secondary, not sole jerk driver.
    slope_sev = slope_deg / max(limit_deg, 1e-6)
    severity = float(sev["severity"]) * (0.75 + 0.25 * min(slope_sev, 2.0))
    if not bearing["traverse_feasible"]:
        severity *= 1.1
    profile = shackleton_path_profile()
    path_km = float(profile["total_path_km"])
    path_factor = min(1.0, path_km / 8.0)
    jerk_scale = _jerk_teaching_scale()
    jerk_peak = jerk_scale * severity * path_factor
    drift = min(2.0, 0.85 * severity * path_factor)
    return {
        "mlcc_jerk_peak": round(jerk_peak, 4),
        "energy_drift_rms_rel": round(drift, 6),
        "backend_id": "lunar_traverse_mechanical_v1",
        "path_km": round(path_km, 3),
        "path_profile_segments": len(profile.get("segments") or []),
        "weighted_illumination_frac": profile.get("weighted_illumination_frac"),
        "slope_deg": slope_deg,
        "slope_limit_deg": limit_deg,
        "regolith_bearing_class": bearing["bearing_class"],
        "sinkage_risk": bool(physics.get("sinkage_risk") or bearing["sinkage_risk"]),
        "traverse_feasible_bearing": bearing["traverse_feasible"],
        "contact_pressure_kpa": bearing["contact_pressure_kpa"],
        "contact_pressure_source": bearing.get("contact_pressure_source"),
        "soil_id": soil_id,
        "compaction_resistance_n": sev["rc_n"],
        "sinkage_mm": sev["sinkage_mm"],
        "drawbar_pull_n": sev["drawbar_pull_n"],
        "bekker_severity": round(float(sev["severity"]), 6),
        "severity_total": round(severity, 6),
        "jerk_normalize_ref": jerk_scale,
        "oracle": BEKKER_ORACLE,
        "l0_cites": list(massif.get("l0_cites") or []) + ["SK-02", "GAP-MR-07"],
        "honesty": {
            "bekker_from_rust": True,
            "jerk_from_bekker_consequence": True,
            "jerk_scale_from_coupling_contract": True,
            "jerk_teaching_scale_not_measured": True,
            "adapt_bearing_adjunct": True,
            "python_not_oracle": True,
            "not_measured": True,
        },
    }


def lunar_traverse_coupling_slice() -> dict[str, Any]:
    proxy = traverse_symplectic_proxy()
    slice_out = mechanical_coupling_slice(proxy)
    return {**slice_out, "traverse_proxy": proxy, "coupling_contract": "chip_mechanical_to_fab_v1"}
