//! Beer–Lambert dust optical depth (teaching).
//!
//! τ = κ · m ; T = exp(-τ) ; A_opt = 1 - T
//!
//! Not Mie / BRDF. Not MEASURED optics meter.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const OPTICS_SCHEMA: &str = "ha_optics_dust_tau_eval_v1";
pub const OPTICS_ORACLE: &str = "ha_physics_gate_optics_tau";

pub fn optical_depth(kappa_m2_per_g: f64, mass_g_m2: f64) -> Result<(f64, f64, f64), String> {
    if !(kappa_m2_per_g.is_finite() && kappa_m2_per_g >= 0.0) {
        return Err("kappa must be finite >= 0".into());
    }
    if !(mass_g_m2.is_finite() && mass_g_m2 >= 0.0) {
        return Err("mass_g_m2 must be finite >= 0".into());
    }
    let tau = kappa_m2_per_g * mass_g_m2;
    let transmittance = (-tau).exp();
    let absorptance = 1.0 - transmittance;
    Ok((tau, transmittance, absorptance))
}

pub fn evaluate_optics_tau(kappa_m2_per_g: f64, mass_g_m2: f64) -> Result<Value, String> {
    let (tau, t, a) = optical_depth(kappa_m2_per_g, mass_g_m2)?;
    Ok(json!({
        "schema": OPTICS_SCHEMA,
        "oracle": OPTICS_ORACLE,
        "mass_g_m2": mass_g_m2,
        "kappa_m2_per_g": kappa_m2_per_g,
        "tau": (tau * 1e12).round() / 1e12,
        "transmittance": (t * 1e12).round() / 1e12,
        "absorptance": (a * 1e12).round() / 1e12,
        "equation": "τ=κ·m; T=exp(-τ); A=1-T",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_mie_brdf": true,
            "teaching_beer_lambert": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_optics_tau_from_catalog(
    catalog_json: &str,
    mass_g_m2: f64,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let coeffs = root
        .get("coeffs")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.coeffs required".to_string())?;
    let gates = root.get("gates").and_then(|v| v.as_object());
    let amin = gates
        .and_then(|g| g.get("mass_g_m2_min"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let amax = gates
        .and_then(|g| g.get("mass_g_m2_max"))
        .and_then(|v| v.as_f64())
        .unwrap_or(1.0e6);
    if mass_g_m2 < amin || mass_g_m2 > amax {
        return Err(format!("mass_g_m2={mass_g_m2} outside gates [{amin},{amax}]"));
    }
    let mut doc = evaluate_optics_tau(f64_req(coeffs, "kappa_m2_per_g")?, mass_g_m2)?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_optics_tau_file(catalog_path: &Path, mass_g_m2: f64) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_optics_tau_from_catalog(&text, mass_g_m2)
}

#[cfg(test)]
mod optics_tests {
    use super::*;

    #[test]
    fn dustier_lower_t() {
        let (_, t0, _) = optical_depth(0.35, 0.0).unwrap();
        let (_, t2, _) = optical_depth(0.35, 2.0).unwrap();
        assert!((t0 - 1.0).abs() < 1e-12);
        assert!(t2 < t0);
    }
}
