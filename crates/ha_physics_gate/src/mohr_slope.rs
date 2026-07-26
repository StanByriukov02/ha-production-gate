//! Infinite-slope Mohr–Coulomb factor of safety (teaching).
//!
//! FS = c / (γ z sinθ cosθ) + tan(φ) / tan(θ)
//! stable iff FS >= 1
//!
//! Not 3D FEM. Not MEASURED vane.

use serde_json::{json, Value};
use std::f64::consts::PI;
use std::fs;
use std::path::Path;

pub const SLOPE_SCHEMA: &str = "ha_mohr_coulomb_slope_eval_v1";
pub const SLOPE_ORACLE: &str = "ha_physics_gate_mohr_slope";

pub fn factor_of_safety(
    theta_deg: f64,
    z_m: f64,
    c_kpa: f64,
    phi_deg: f64,
    gamma_kn_m3: f64,
) -> Result<f64, String> {
    if !(theta_deg.is_finite() && theta_deg > 0.0 && theta_deg < 90.0) {
        return Err("theta_deg must be in (0,90)".into());
    }
    if !(z_m.is_finite() && z_m > 0.0) {
        return Err("z_m must be finite > 0".into());
    }
    if !(c_kpa.is_finite() && c_kpa >= 0.0) {
        return Err("c_kpa must be finite >= 0".into());
    }
    if !(phi_deg.is_finite() && phi_deg > 0.0 && phi_deg < 90.0) {
        return Err("phi_deg must be in (0,90)".into());
    }
    if !(gamma_kn_m3.is_finite() && gamma_kn_m3 > 0.0) {
        return Err("gamma must be finite > 0".into());
    }
    let th = theta_deg * PI / 180.0;
    let ph = phi_deg * PI / 180.0;
    let s = th.sin();
    let c = th.cos();
    let t = th.tan();
    if t.abs() < 1e-15 {
        return Err("tan(theta) ~ 0".into());
    }
    let cohesion_term = c_kpa / (gamma_kn_m3 * z_m * s * c);
    let friction_term = ph.tan() / t;
    Ok(cohesion_term + friction_term)
}

pub fn evaluate_mohr_slope(
    theta_deg: f64,
    z_m: f64,
    c_kpa: f64,
    phi_deg: f64,
    gamma_kn_m3: f64,
) -> Result<Value, String> {
    let fs = factor_of_safety(theta_deg, z_m, c_kpa, phi_deg, gamma_kn_m3)?;
    Ok(json!({
        "schema": SLOPE_SCHEMA,
        "oracle": SLOPE_ORACLE,
        "theta_deg": theta_deg,
        "z_m": z_m,
        "c_kpa": c_kpa,
        "phi_deg": phi_deg,
        "gamma_kn_m3": gamma_kn_m3,
        "fs": (fs * 1e9).round() / 1e9,
        "stable": fs >= 1.0,
        "equation": "FS = c/(γ z sinθ cosθ) + tan(φ)/tan(θ)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_3d_fem": true,
            "teaching_infinite_slope": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_mohr_slope_from_catalog(
    catalog_json: &str,
    theta_deg: f64,
    z_m: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let soil = root
        .get("soil")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.soil required".to_string())?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let gates = root.get("gates").and_then(|v| v.as_object());
    let z = z_m.unwrap_or(f64_req(defaults, "z_m")?);
    let tmin = gates
        .and_then(|g| g.get("theta_deg_min"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.1);
    let tmax = gates
        .and_then(|g| g.get("theta_deg_max"))
        .and_then(|v| v.as_f64())
        .unwrap_or(80.0);
    if theta_deg < tmin || theta_deg > tmax {
        return Err(format!("theta_deg={theta_deg} outside gates [{tmin},{tmax}]"));
    }
    let mut doc = evaluate_mohr_slope(
        theta_deg,
        z,
        f64_req(soil, "c_kpa")?,
        f64_req(soil, "phi_deg")?,
        f64_req(soil, "gamma_kn_m3")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_mohr_slope_file(
    catalog_path: &Path,
    theta_deg: f64,
    z_m: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_mohr_slope_from_catalog(&text, theta_deg, z_m)
}

#[cfg(test)]
mod slope_tests {
    use super::*;

    #[test]
    fn steeper_lower_fs() {
        let mild = factor_of_safety(15.0, 0.5, 0.1, 35.0, 2.43).unwrap();
        let steep = factor_of_safety(45.0, 0.5, 0.1, 35.0, 2.43).unwrap();
        assert!(mild > steep);
        assert!(mild >= 1.0);
        assert!(steep < 1.0);
    }
}
