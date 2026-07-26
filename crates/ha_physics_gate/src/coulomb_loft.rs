//! Coulomb loft criterion (Stubbs fountain teaching).
//!
//! q = 4 π ε0 r φ
//! E = |φ| / λ_D
//! loft_ratio = |q| E / (m g) ; loft iff ratio > 1
//!
//! Not PIC. Not MEASURED grain charge.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const LOFT_SCHEMA: &str = "ha_coulomb_loft_eval_v1";
pub const LOFT_ORACLE: &str = "ha_physics_gate_coulomb_loft";

pub fn loft_ratio(
    phi_v: f64,
    r_m: f64,
    rho_kg_m3: f64,
    lambda_d_m: f64,
    g_m_s2: f64,
    epsilon0: f64,
    pi: f64,
) -> Result<(f64, f64, f64, f64, f64), String> {
    if !(phi_v.is_finite()) {
        return Err("phi_v must be finite".into());
    }
    if !(r_m.is_finite() && r_m > 0.0) {
        return Err("r_m must be finite > 0".into());
    }
    if !(rho_kg_m3.is_finite() && rho_kg_m3 > 0.0) {
        return Err("rho must be finite > 0".into());
    }
    if !(lambda_d_m.is_finite() && lambda_d_m > 0.0) {
        return Err("lambda_d must be finite > 0".into());
    }
    if !(g_m_s2.is_finite() && g_m_s2 > 0.0) {
        return Err("g must be finite > 0".into());
    }
    if !(epsilon0.is_finite() && epsilon0 > 0.0 && pi.is_finite() && pi > 0.0) {
        return Err("epsilon0/pi invalid".into());
    }
    let q = 4.0 * pi * epsilon0 * r_m * phi_v;
    let e_field = phi_v.abs() / lambda_d_m;
    let f_e = q.abs() * e_field;
    let mass = (4.0 / 3.0) * pi * r_m.powi(3) * rho_kg_m3;
    let f_g = mass * g_m_s2;
    if !(f_g.is_finite() && f_g > 0.0) {
        return Err("F_g invalid".into());
    }
    let ratio = f_e / f_g;
    Ok((ratio, q, e_field, f_e, f_g))
}

pub fn evaluate_coulomb_loft(
    phi_v: f64,
    r_um: f64,
    rho_kg_m3: f64,
    lambda_d_m: f64,
    g_m_s2: f64,
    epsilon0: f64,
    pi: f64,
) -> Result<Value, String> {
    if !(r_um.is_finite() && r_um > 0.0) {
        return Err("r_um must be finite > 0".into());
    }
    let r_m = r_um * 1.0e-6;
    let (ratio, q, e_field, f_e, f_g) =
        loft_ratio(phi_v, r_m, rho_kg_m3, lambda_d_m, g_m_s2, epsilon0, pi)?;
    Ok(json!({
        "schema": LOFT_SCHEMA,
        "oracle": LOFT_ORACLE,
        "phi_v": phi_v,
        "r_um": r_um,
        "r_m": r_m,
        "rho_kg_m3": rho_kg_m3,
        "lambda_d_m": lambda_d_m,
        "g_m_s2": g_m_s2,
        "q_c": q,
        "e_v_per_m": e_field,
        "f_e_n": f_e,
        "f_g_n": f_g,
        "loft_ratio": (ratio * 1e12).round() / 1e12,
        "lofts": ratio > 1.0,
        "equation": "q=4πε0 r φ; E=|φ|/λ_D; loft_ratio=|q|E/(m g)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_pic": true,
            "teaching_stubbs_fountain": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_coulomb_loft_from_catalog(
    catalog_json: &str,
    phi_v: f64,
    r_um: Option<f64>,
    rho_kg_m3: Option<f64>,
    lambda_d_m: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let constants = root
        .get("constants")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.constants required".to_string())?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let gates = root.get("gates").and_then(|v| v.as_object());
    let r = r_um.unwrap_or(f64_req(defaults, "r_um")?);
    let rho = rho_kg_m3.unwrap_or(f64_req(defaults, "rho_kg_m3")?);
    let lam = lambda_d_m.unwrap_or(f64_req(defaults, "lambda_d_m")?);
    let rmin = gates
        .and_then(|g| g.get("r_um_min"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let rmax = gates
        .and_then(|g| g.get("r_um_max"))
        .and_then(|v| v.as_f64())
        .unwrap_or(1.0e9);
    if r < rmin || r > rmax {
        return Err(format!("r_um={r} outside gates [{rmin},{rmax}]"));
    }
    let mut doc = evaluate_coulomb_loft(
        phi_v,
        r,
        rho,
        lam,
        f64_req(constants, "g_moon_m_s2")?,
        f64_req(constants, "epsilon0")?,
        f64_req(constants, "pi")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_coulomb_loft_file(
    catalog_path: &Path,
    phi_v: f64,
    r_um: Option<f64>,
    rho_kg_m3: Option<f64>,
    lambda_d_m: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_coulomb_loft_from_catalog(&text, phi_v, r_um, rho_kg_m3, lambda_d_m)
}

#[cfg(test)]
mod loft_tests {
    use super::*;

    #[test]
    fn smaller_grain_lofts_easier() {
        let eps = 8.854187817e-12;
        let pi = std::f64::consts::PI;
        let (small, _, _, _, _) = loft_ratio(-1000.0, 0.5e-6, 3100.0, 1.0, 1.62, eps, pi).unwrap();
        let (large, _, _, _, _) = loft_ratio(-1000.0, 50e-6, 3100.0, 1.0, 1.62, eps, pi).unwrap();
        assert!(small > large);
    }
}
