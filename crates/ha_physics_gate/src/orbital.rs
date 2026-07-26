//! Orbital vis-viva + Kepler period (teaching two-body).
//!
//! v = √(μ (2/r − 1/a))
//! T = 2π √(a³ / μ)
//!
//! Not n-body. Not MEASURED ephemeris.

use serde_json::{json, Value};
use std::f64::consts::PI;
use std::fs;
use std::path::Path;

pub const ORBIT_SCHEMA: &str = "ha_orbital_visviva_eval_v1";
pub const ORBIT_ORACLE: &str = "ha_physics_gate_orbital_visviva";

pub fn vis_viva_v(mu: f64, r_m: f64, a_m: f64) -> Result<f64, String> {
    if !(mu.is_finite() && mu > 0.0) {
        return Err("mu must be finite > 0".into());
    }
    if !(r_m.is_finite() && r_m > 0.0 && a_m.is_finite() && a_m > 0.0) {
        return Err("r,a must be finite > 0".into());
    }
    let inside = 2.0 / r_m - 1.0 / a_m;
    if inside <= 0.0 {
        return Err("vis-viva argument must be > 0 (bound orbit)".into());
    }
    Ok((mu * inside).sqrt())
}

pub fn kepler_period_s(mu: f64, a_m: f64) -> Result<f64, String> {
    if !(mu.is_finite() && mu > 0.0 && a_m.is_finite() && a_m > 0.0) {
        return Err("mu,a invalid".into());
    }
    Ok(2.0 * PI * (a_m.powi(3) / mu).sqrt())
}

pub fn evaluate_orbital_visviva(
    body: &str,
    mu: f64,
    r_m: f64,
    a_m: f64,
) -> Result<Value, String> {
    let v = vis_viva_v(mu, r_m, a_m)?;
    let t = kepler_period_s(mu, a_m)?;
    Ok(json!({
        "schema": ORBIT_SCHEMA,
        "oracle": ORBIT_ORACLE,
        "body": body,
        "mu_m3_s2": mu,
        "r_m": r_m,
        "a_m": a_m,
        "r_km": r_m / 1000.0,
        "a_km": a_m / 1000.0,
        "v_m_s": (v * 1e6).round() / 1e6,
        "period_s": (t * 1e6).round() / 1e6,
        "period_h": ((t / 3600.0) * 1e9).round() / 1e9,
        "equation": "v=√(μ(2/r−1/a)); T=2π√(a³/μ)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_nbody": true,
            "teaching_two_body_kepler": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_orbital_visviva_from_catalog(
    catalog_json: &str,
    body: &str,
    r_km: Option<f64>,
    a_km: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let bodies = root
        .get("bodies")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.bodies required".to_string())?;
    let brow = bodies
        .get(body)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown body={body}"))?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let r = r_km.unwrap_or(f64_req(defaults, "r_km")?) * 1000.0;
    let a = a_km.unwrap_or(f64_req(defaults, "a_km")?) * 1000.0;
    let mut doc = evaluate_orbital_visviva(body, f64_req(brow, "mu_m3_s2")?, r, a)?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_orbital_visviva_file(
    catalog_path: &Path,
    body: &str,
    r_km: Option<f64>,
    a_km: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_orbital_visviva_from_catalog(&text, body, r_km, a_km)
}

#[cfg(test)]
mod orbit_tests {
    use super::*;

    #[test]
    fn leo_faster_than_geo() {
        let mu = 3.986004418e14;
        let v_leo = vis_viva_v(mu, 6778e3, 6778e3).unwrap();
        let v_geo = vis_viva_v(mu, 42164e3, 42164e3).unwrap();
        assert!(v_leo > v_geo);
    }
}
