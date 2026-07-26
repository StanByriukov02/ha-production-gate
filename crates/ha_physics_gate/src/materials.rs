//! Materials Hooke + CTE (teaching).
//!
//! σ = E · ε
//! ΔL = α · L · ΔT
//! σ_thermal (fully constrained) = E · α · ΔT
//!
//! Not anisotropic FEM. Not MEASURED coupon.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const MATERIALS_SCHEMA: &str = "ha_materials_hooke_cte_eval_v1";
pub const MATERIALS_ORACLE: &str = "ha_physics_gate_materials_hooke";

pub fn hooke_sigma(e_pa: f64, eps: f64) -> Result<f64, String> {
    if !(e_pa.is_finite() && e_pa > 0.0) {
        return Err("E must be finite > 0".into());
    }
    if !eps.is_finite() {
        return Err("eps must be finite".into());
    }
    Ok(e_pa * eps)
}

pub fn cte_delta_l(alpha: f64, l_m: f64, dt_k: f64) -> Result<f64, String> {
    if !(alpha.is_finite() && l_m.is_finite() && l_m > 0.0 && dt_k.is_finite()) {
        return Err("alpha,L,dt invalid".into());
    }
    Ok(alpha * l_m * dt_k)
}

pub fn evaluate_materials_hooke(
    mat_id: &str,
    e_pa: f64,
    alpha: f64,
    eps: f64,
    dt_k: f64,
    l_m: f64,
) -> Result<Value, String> {
    let sigma = hooke_sigma(e_pa, eps)?;
    let d_l = cte_delta_l(alpha, l_m, dt_k)?;
    let sigma_th = e_pa * alpha * dt_k;
    Ok(json!({
        "schema": MATERIALS_SCHEMA,
        "oracle": MATERIALS_ORACLE,
        "mat_id": mat_id,
        "E_pa": e_pa,
        "alpha_per_k": alpha,
        "eps": eps,
        "dt_k": dt_k,
        "l_m": l_m,
        "sigma_pa": (sigma * 1e6).round() / 1e6,
        "delta_mech_m": ((eps * l_m) * 1e12).round() / 1e12,
        "delta_thermal_m": (d_l * 1e12).round() / 1e12,
        "sigma_thermal_constrained_pa": (sigma_th * 1e6).round() / 1e6,
        "equation": "σ=Eε; ΔL=αLΔT; σ_th=EαΔT",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_anisotropic_fem": true,
            "teaching_hooke_cte": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_materials_hooke_from_catalog(
    catalog_json: &str,
    mat_id: &str,
    eps: Option<f64>,
    dt_k: Option<f64>,
    l_m: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let mats = root
        .get("materials")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.materials required".to_string())?;
    let mat = mats
        .get(mat_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown mat={mat_id}"))?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let e = eps.unwrap_or(f64_req(defaults, "eps")?);
    let dt = dt_k.unwrap_or(f64_req(defaults, "dt_k")?);
    let l = l_m.unwrap_or(f64_req(defaults, "l_m")?);
    let mut doc = evaluate_materials_hooke(
        mat_id,
        f64_req(mat, "E_pa")?,
        f64_req(mat, "alpha_per_k")?,
        e,
        dt,
        l,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_materials_hooke_file(
    catalog_path: &Path,
    mat_id: &str,
    eps: Option<f64>,
    dt_k: Option<f64>,
    l_m: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_materials_hooke_from_catalog(&text, mat_id, eps, dt_k, l_m)
}

#[cfg(test)]
mod materials_tests {
    use super::*;

    #[test]
    fn al_expands_more_than_cfrp() {
        let d_al = cte_delta_l(2.3e-5, 1.0, 100.0).unwrap();
        let d_cf = cte_delta_l(1.0e-6, 1.0, 100.0).unwrap();
        assert!(d_al > d_cf);
    }
}
