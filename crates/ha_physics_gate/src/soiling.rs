//! Soiling thermal BC shift (teaching).
//!
//! f = min(1, m/m_sat)
//! A_eff = (1-f) A_c + f A_d
//! eps_eff = (1-f) eps_c + f eps_d
//! L = m_kg / rho ; R_th = L / k
//!
//! Not Diviner soiled coupon. Not full RT.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const SOILING_SCHEMA: &str = "ha_soiling_thermal_bc_eval_v1";
pub const SOILING_ORACLE: &str = "ha_physics_gate_soiling_bc";

pub fn soiling_bc(
    mass_g_m2: f64,
    sat_g_m2: f64,
    a_clean: f64,
    a_dust: f64,
    eps_clean: f64,
    eps_dust: f64,
    k_w_mk: f64,
    rho_kg_m3: f64,
) -> Result<(f64, f64, f64, f64, f64), String> {
    if !(mass_g_m2.is_finite() && mass_g_m2 >= 0.0) {
        return Err("mass_g_m2 must be finite >= 0".into());
    }
    if !(sat_g_m2.is_finite() && sat_g_m2 > 0.0) {
        return Err("saturation_g_m2 must be finite > 0".into());
    }
    for (n, v) in [
        ("a_clean", a_clean),
        ("a_dust", a_dust),
        ("eps_clean", eps_clean),
        ("eps_dust", eps_dust),
    ] {
        if !(v.is_finite() && (0.0..=1.0).contains(&v)) {
            return Err(format!("{n} must be in [0,1]"));
        }
    }
    if !(k_w_mk.is_finite() && k_w_mk > 0.0 && rho_kg_m3.is_finite() && rho_kg_m3 > 0.0) {
        return Err("k/rho invalid".into());
    }
    let f = (mass_g_m2 / sat_g_m2).min(1.0);
    let a_eff = (1.0 - f) * a_clean + f * a_dust;
    let eps_eff = (1.0 - f) * eps_clean + f * eps_dust;
    let m_kg = mass_g_m2 * 1.0e-3;
    let l_m = m_kg / rho_kg_m3;
    let r_th = l_m / k_w_mk;
    Ok((f, a_eff, eps_eff, l_m, r_th))
}

pub fn evaluate_soiling_bc(
    mass_g_m2: f64,
    sat_g_m2: f64,
    a_clean: f64,
    a_dust: f64,
    eps_clean: f64,
    eps_dust: f64,
    k_w_mk: f64,
    rho_kg_m3: f64,
) -> Result<Value, String> {
    let (f, a_eff, eps_eff, l_m, r_th) = soiling_bc(
        mass_g_m2, sat_g_m2, a_clean, a_dust, eps_clean, eps_dust, k_w_mk, rho_kg_m3,
    )?;
    Ok(json!({
        "schema": SOILING_SCHEMA,
        "oracle": SOILING_ORACLE,
        "mass_g_m2": mass_g_m2,
        "cover_frac": (f * 1e12).round() / 1e12,
        "albedo_eff": (a_eff * 1e12).round() / 1e12,
        "emissivity_eff": (eps_eff * 1e12).round() / 1e12,
        "thickness_m": (l_m * 1e15).round() / 1e15,
        "r_th_m2k_w": (r_th * 1e12).round() / 1e12,
        "equation": "f=min(1,m/msat); A,eps mix; R_th=L/k",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "linear_cover_teaching": true,
            "not_full_rt": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_soiling_bc_from_catalog(
    catalog_json: &str,
    mass_g_m2: f64,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let clean = root
        .get("clean")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.clean required".to_string())?;
    let dust = root
        .get("dust")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.dust required".to_string())?;
    let sat = root
        .get("saturation_g_m2")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "saturation_g_m2 required".to_string())?;
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
    let mut doc = evaluate_soiling_bc(
        mass_g_m2,
        sat,
        f64_req(clean, "albedo")?,
        f64_req(dust, "albedo")?,
        f64_req(clean, "emissivity")?,
        f64_req(dust, "emissivity")?,
        f64_req(dust, "k_w_mk")?,
        f64_req(dust, "rho_kg_m3")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_soiling_bc_file(catalog_path: &Path, mass_g_m2: f64) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_soiling_bc_from_catalog(&text, mass_g_m2)
}

#[cfg(test)]
mod soiling_tests {
    use super::*;

    #[test]
    fn soiled_darker_more_rth() {
        let (_, a0, _, _, r0) = soiling_bc(0.0, 4.0, 0.12, 0.08, 0.95, 0.88, 0.0025, 1500.0).unwrap();
        let (_, a3, _, _, r3) = soiling_bc(3.0, 4.0, 0.12, 0.08, 0.95, 0.88, 0.0025, 1500.0).unwrap();
        assert!(a3 < a0);
        assert!(r3 > r0);
    }
}
