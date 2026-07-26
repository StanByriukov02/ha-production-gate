//! Coulomb joint friction (teaching).
//! F_f = μ N · τ_f = F_f · r_eff

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const JOINT_SCHEMA: &str = "ha_joint_friction_eval_v1";
pub const JOINT_ORACLE: &str = "ha_physics_gate_joint_friction";

pub fn joint_friction(mu: f64, n_n: f64, r_eff: f64) -> Result<(f64, f64), String> {
    if !(mu.is_finite() && mu >= 0.0) {
        return Err("mu must be finite >= 0".into());
    }
    if !(n_n.is_finite() && n_n >= 0.0) {
        return Err("N must be finite >= 0".into());
    }
    if !(r_eff.is_finite() && r_eff > 0.0) {
        return Err("r_eff must be finite > 0".into());
    }
    let f = mu * n_n;
    Ok((f, f * r_eff))
}

pub fn evaluate_joint_friction(
    pack_id: &str,
    mu: f64,
    n_n: f64,
    r_eff: f64,
) -> Result<Value, String> {
    let (f, tau) = joint_friction(mu, n_n, r_eff)?;
    Ok(json!({
        "schema": JOINT_SCHEMA,
        "oracle": JOINT_ORACLE,
        "pack_id": pack_id,
        "mu": mu,
        "n_n": n_n,
        "r_eff_m": r_eff,
        "f_friction_n": (f * 1e12).round() / 1e12,
        "tau_friction_nm": (tau * 1e12).round() / 1e12,
        "equation": "F_f=mu*N; tau_f=F_f*r_eff",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_stribeck": true,
            "teaching_coulomb_joint": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_joint_friction_from_catalog(
    catalog_json: &str,
    pack_id: &str,
    n_n: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let packs = root
        .get("packs")
        .and_then(|x| x.as_object())
        .ok_or_else(|| "catalog.packs required".to_string())?;
    let pack = packs
        .get(pack_id)
        .and_then(|x| x.as_object())
        .ok_or_else(|| format!("unknown pack={pack_id}"))?;
    let defaults = root
        .get("defaults")
        .and_then(|x| x.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let n = n_n.unwrap_or(f64_req(defaults, "n_n")?);
    let mut doc = evaluate_joint_friction(
        pack_id,
        f64_req(pack, "mu")?,
        n,
        f64_req(pack, "r_eff_m")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_joint_friction_file(
    catalog_path: &Path,
    pack_id: &str,
    n_n: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_joint_friction_from_catalog(&text, pack_id, n_n)
}
