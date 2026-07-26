//! Radiation dose-rate window law (U4 M3).
//!
//! annual_dose_gy / hours_per_year → rate_gy_per_h
//! window_dose = rate * dt_h * clamp(flare_scale, lo, hi)
//!
//! Teaching / PROXY class constants live in ON catalog JSON — not CREME FEM.
//! Not MEASURED.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const RADIATION_SCHEMA: &str = "ha_radiation_rate_eval_v1";
pub const RADIATION_ORACLE: &str = "ha_physics_gate_radiation_rate";
pub const HOURS_PER_YEAR: f64 = 365.25 * 24.0;

/// Instantaneous dose rate [Gy/h] from annual class dose.
pub fn dose_rate_gy_per_h(annual_dose_gy: f64) -> Result<f64, String> {
    if !annual_dose_gy.is_finite() || annual_dose_gy < 0.0 {
        return Err("annual_dose_gy must be finite >= 0".into());
    }
    Ok(annual_dose_gy / HOURS_PER_YEAR)
}

/// Clamp flare/dose scale into [lo, hi].
pub fn clamp_flare_scale(scale: f64, lo: f64, hi: f64) -> Result<f64, String> {
    if !(scale.is_finite() && lo.is_finite() && hi.is_finite()) {
        return Err("flare scale bounds must be finite".into());
    }
    if lo > hi {
        return Err("flare_lo must be <= flare_hi".into());
    }
    Ok(scale.max(lo).min(hi))
}

/// Window dose accumulation [Gy] for one timestep.
pub fn window_dose_gy(
    annual_dose_gy: f64,
    dt_h: f64,
    flare_scale: f64,
    flare_lo: f64,
    flare_hi: f64,
) -> Result<f64, String> {
    if !dt_h.is_finite() || dt_h < 0.0 {
        return Err("dt_h must be finite >= 0".into());
    }
    let rate = dose_rate_gy_per_h(annual_dose_gy)?;
    let scale = clamp_flare_scale(flare_scale, flare_lo, flare_hi)?;
    Ok(rate * dt_h * scale)
}

/// Same for SEE event rate [events] over window from annual SEE rate.
pub fn window_see_events(
    annual_see_per_year: f64,
    dt_h: f64,
    flare_scale: f64,
    flare_lo: f64,
    flare_hi: f64,
) -> Result<f64, String> {
    if !annual_see_per_year.is_finite() || annual_see_per_year < 0.0 {
        return Err("annual_see_per_year must be finite >= 0".into());
    }
    if !dt_h.is_finite() || dt_h < 0.0 {
        return Err("dt_h must be finite >= 0".into());
    }
    let rate = annual_see_per_year / HOURS_PER_YEAR;
    let scale = clamp_flare_scale(flare_scale, flare_lo, flare_hi)?;
    Ok(rate * dt_h * scale)
}

pub fn evaluate_radiation_rate(
    annual_dose_gy: f64,
    annual_see_per_year: f64,
    dt_h: f64,
    flare_scale: f64,
    flare_lo: f64,
    flare_hi: f64,
    site_id: Option<&str>,
) -> Result<Value, String> {
    let rate = dose_rate_gy_per_h(annual_dose_gy)?;
    let scale = clamp_flare_scale(flare_scale, flare_lo, flare_hi)?;
    let d_dose = window_dose_gy(annual_dose_gy, dt_h, flare_scale, flare_lo, flare_hi)?;
    let d_see = window_see_events(annual_see_per_year, dt_h, flare_scale, flare_lo, flare_hi)?;
    Ok(json!({
        "schema": RADIATION_SCHEMA,
        "oracle": RADIATION_ORACLE,
        "site_id": site_id,
        "annual_dose_gy": annual_dose_gy,
        "annual_see_per_year": annual_see_per_year,
        "dt_h": dt_h,
        "flare_scale_raw": flare_scale,
        "flare_scale": scale,
        "flare_lo": flare_lo,
        "flare_hi": flare_hi,
        "dose_rate_gy_per_h": (rate * 1e18).round() / 1e18,
        "window_dose_gy": (d_dose * 1e18).round() / 1e18,
        "window_see_events": (d_see * 1e18).round() / 1e18,
        "hours_per_year": HOURS_PER_YEAR,
        "equation": "dD = (D_annual / H_year) * dt_h * clamp(flare, lo, hi)",
        "honesty": {
            "not_measured": true,
            "not_creme_fem": true,
            "python_not_oracle": true,
            "teaching_proxy_class": true,
            "sim_slice": true
        }
    }))
}

pub fn evaluate_radiation_rate_from_catalog(
    catalog_json: &str,
    site_id: &str,
    dt_h: f64,
    flare_scale: f64,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let sites = root
        .get("sites")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.missing sites object".to_string())?;
    let site = sites
        .get(site_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown site_id={site_id}"))?;
    let annual = site
        .get("annual_dose_gy")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "site.annual_dose_gy required".to_string())?;
    let see = site
        .get("annual_see_per_year")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "site.annual_see_per_year required (no airborne SEE)".to_string())?;
    let gates = root.get("gates").and_then(|v| v.as_object());
    let lo = gates
        .and_then(|g| g.get("flare_lo"))
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "catalog.gates.flare_lo required".to_string())?;
    let hi = gates
        .and_then(|g| g.get("flare_hi"))
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "catalog.gates.flare_hi required".to_string())?;
    let mut doc = evaluate_radiation_rate(annual, see, dt_h, flare_scale, lo, hi, Some(site_id))?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("label".into(), site.get("label").cloned().unwrap_or(json!(site_id)));
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
        obj.insert(
            "catalog_equation".into(),
            root.get("equation").cloned().unwrap_or(json!("")),
        );
    }
    Ok(doc)
}

pub fn evaluate_radiation_rate_file(
    catalog_path: &Path,
    site_id: &str,
    dt_h: f64,
    flare_scale: f64,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_radiation_rate_from_catalog(&text, site_id, dt_h, flare_scale)
}

#[cfg(test)]
mod radiation_tests {
    use super::*;

    #[test]
    fn year_window_recovers_annual_at_unity_flare() {
        let d = window_dose_gy(0.55, HOURS_PER_YEAR, 1.0, 1.0, 12.0).unwrap();
        assert!((d - 0.55).abs() < 1e-12);
    }

    #[test]
    fn flare_scales_dose() {
        let quiet = window_dose_gy(0.55, 24.0, 1.0, 1.0, 12.0).unwrap();
        let storm = window_dose_gy(0.55, 24.0, 4.0, 1.0, 12.0).unwrap();
        assert!((storm / quiet - 4.0).abs() < 1e-12);
    }

    #[test]
    fn flare_clamped() {
        let s = clamp_flare_scale(100.0, 1.0, 12.0).unwrap();
        assert!((s - 12.0).abs() < 1e-12);
    }
}
