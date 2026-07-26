//! ISRU sinter Arrhenius kinetics + heater energy (teaching).
//!
//! rate = A · exp(-Ea / (R T))
//! progress = 1 - exp(-rate · t)
//! E = P · t
//!
//! Not MEASURED kiln. Not densification FEM.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const SINTER_SCHEMA: &str = "ha_isru_sinter_eval_v1";
pub const SINTER_ORACLE: &str = "ha_physics_gate_isru_sinter";

pub fn arrhenius_rate(a: f64, ea: f64, r: f64, t_k: f64) -> Result<f64, String> {
    if !(a.is_finite() && a > 0.0 && ea.is_finite() && ea > 0.0 && r.is_finite() && r > 0.0) {
        return Err("A,Ea,R invalid".into());
    }
    if !(t_k.is_finite() && t_k > 0.0) {
        return Err("t_k must be finite > 0".into());
    }
    Ok(a * (-ea / (r * t_k)).exp())
}

pub fn evaluate_isru_sinter(
    recipe_id: &str,
    a: f64,
    ea: f64,
    r: f64,
    t_k: f64,
    t_s: f64,
    p_w: f64,
) -> Result<Value, String> {
    if !(t_s.is_finite() && t_s >= 0.0) {
        return Err("t_s must be finite >= 0".into());
    }
    if !(p_w.is_finite() && p_w >= 0.0) {
        return Err("p_w must be finite >= 0".into());
    }
    let rate = arrhenius_rate(a, ea, r, t_k)?;
    let progress = 1.0 - (-rate * t_s).exp();
    let e_j = p_w * t_s;
    Ok(json!({
        "schema": SINTER_SCHEMA,
        "oracle": SINTER_ORACLE,
        "recipe_id": recipe_id,
        "t_k": t_k,
        "t_s": t_s,
        "p_w": p_w,
        "rate_per_s": (rate * 1e15).round() / 1e15,
        "progress": (progress * 1e12).round() / 1e12,
        "energy_j": (e_j * 1e9).round() / 1e9,
        "equation": "rate=A·exp(-Ea/(RT)); progress=1-e^{-rate t}; E=P t",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_densification_fem": true,
            "teaching_arrhenius_sinter": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_isru_sinter_from_catalog(
    catalog_json: &str,
    recipe_id: &str,
    t_k: Option<f64>,
    t_s: Option<f64>,
    p_w: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let recipes = root
        .get("recipes")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.recipes required".to_string())?;
    let recipe = recipes
        .get(recipe_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown recipe={recipe_id}"))?;
    let constants = root
        .get("constants")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.constants required".to_string())?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let tk = t_k.unwrap_or(f64_req(defaults, "t_k")?);
    let ts = t_s.unwrap_or(f64_req(defaults, "t_s")?);
    let pw = p_w.unwrap_or(f64_req(defaults, "p_w")?);
    let mut doc = evaluate_isru_sinter(
        recipe_id,
        f64_req(recipe, "A_per_s")?,
        f64_req(recipe, "Ea_j_mol")?,
        f64_req(constants, "R_j_mol_k")?,
        tk,
        ts,
        pw,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_isru_sinter_file(
    catalog_path: &Path,
    recipe_id: &str,
    t_k: Option<f64>,
    t_s: Option<f64>,
    p_w: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_isru_sinter_from_catalog(&text, recipe_id, t_k, t_s, p_w)
}

#[cfg(test)]
mod sinter_tests {
    use super::*;

    #[test]
    fn lower_barrier_faster() {
        let r = 8.314462618;
        let mild = arrhenius_rate(50.0, 80000.0, r, 1100.0).unwrap();
        let cold = arrhenius_rate(50.0, 120000.0, r, 1100.0).unwrap();
        assert!(mild > cold);
    }
}
