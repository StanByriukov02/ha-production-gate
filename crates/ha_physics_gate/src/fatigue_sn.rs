//! Basquin high-cycle S–N fatigue (teaching).
//! σ_a = σ_f' (2 N_f)^b  =>  N_f = 0.5 · (σ_a/σ_f')^(1/b)

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const FATIGUE_SCHEMA: &str = "ha_fatigue_sn_eval_v1";
pub const FATIGUE_ORACLE: &str = "ha_physics_gate_fatigue_sn";

pub fn basquin_n_f(sigma_a: f64, sigma_f_prime: f64, b: f64) -> Result<f64, String> {
    if !(sigma_a.is_finite() && sigma_a > 0.0) {
        return Err("sigma_a must be finite > 0".into());
    }
    if !(sigma_f_prime.is_finite() && sigma_f_prime > 0.0) {
        return Err("sigma_f_prime must be finite > 0".into());
    }
    if !(b.is_finite() && b < 0.0) {
        return Err("b must be finite < 0".into());
    }
    if sigma_a >= sigma_f_prime {
        return Err("sigma_a must be < sigma_f_prime for Basquin teaching".into());
    }
    let ratio = sigma_a / sigma_f_prime;
    Ok(0.5 * ratio.powf(1.0 / b))
}

pub fn evaluate_fatigue_sn(
    mat_id: &str,
    sigma_f_prime: f64,
    b: f64,
    sigma_a: f64,
) -> Result<Value, String> {
    let n_f = basquin_n_f(sigma_a, sigma_f_prime, b)?;
    Ok(json!({
        "schema": FATIGUE_SCHEMA,
        "oracle": FATIGUE_ORACLE,
        "mat_id": mat_id,
        "sigma_a_mpa": sigma_a,
        "sigma_f_prime_mpa": sigma_f_prime,
        "b": b,
        "n_f_cycles": (n_f * 1e6).round() / 1e6,
        "equation": "N_f=0.5*(sigma_a/sigma_f_prime)^(1/b)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_paris_fem": true,
            "teaching_basquin": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_fatigue_sn_from_catalog(
    catalog_json: &str,
    mat_id: &str,
    sigma_a: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let mats = root
        .get("mats")
        .and_then(|x| x.as_object())
        .ok_or_else(|| "catalog.mats required".to_string())?;
    let mat = mats
        .get(mat_id)
        .and_then(|x| x.as_object())
        .ok_or_else(|| format!("unknown mat={mat_id}"))?;
    let defaults = root
        .get("defaults")
        .and_then(|x| x.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let s = sigma_a.unwrap_or(f64_req(defaults, "sigma_a_mpa")?);
    let mut doc = evaluate_fatigue_sn(
        mat_id,
        f64_req(mat, "sigma_f_prime_mpa")?,
        f64_req(mat, "b")?,
        s,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_fatigue_sn_file(
    catalog_path: &Path,
    mat_id: &str,
    sigma_a: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_fatigue_sn_from_catalog(&text, mat_id, sigma_a)
}
