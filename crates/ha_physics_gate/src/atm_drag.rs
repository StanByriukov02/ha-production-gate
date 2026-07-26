//! Atmospheric quadratic drag (teaching).
//!
//! F_d = 0.5 · ρ · v² · Cd · A
//! a_d = F_d / m
//!
//! Not CFD / DSMC. Not MEASURED Mars anemometer.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const DRAG_SCHEMA: &str = "ha_atm_drag_eval_v1";
pub const DRAG_ORACLE: &str = "ha_physics_gate_atm_drag";

pub fn atm_drag(
    rho: f64,
    v: f64,
    cd: f64,
    area: f64,
    mass: f64,
) -> Result<(f64, f64), String> {
    if !(rho.is_finite() && rho >= 0.0) {
        return Err("rho must be finite >= 0".into());
    }
    if !(v.is_finite() && v >= 0.0) {
        return Err("v must be finite >= 0".into());
    }
    if !(cd.is_finite() && cd >= 0.0) {
        return Err("Cd must be finite >= 0".into());
    }
    if !(area.is_finite() && area > 0.0) {
        return Err("area must be finite > 0".into());
    }
    if !(mass.is_finite() && mass > 0.0) {
        return Err("mass must be finite > 0".into());
    }
    let f = 0.5 * rho * v * v * cd * area;
    let a = f / mass;
    Ok((f, a))
}

pub fn evaluate_atm_drag(
    body: &str,
    rho: f64,
    v: f64,
    cd: f64,
    area: f64,
    mass: f64,
) -> Result<Value, String> {
    let (f, a) = atm_drag(rho, v, cd, area, mass)?;
    Ok(json!({
        "schema": DRAG_SCHEMA,
        "oracle": DRAG_ORACLE,
        "body": body,
        "rho_kg_m3": rho,
        "v_m_s": v,
        "cd": cd,
        "area_m2": area,
        "mass_kg": mass,
        "f_drag_n": (f * 1e12).round() / 1e12,
        "a_drag_m_s2": (a * 1e12).round() / 1e12,
        "equation": "F_d=0.5·ρ·v²·Cd·A; a=F/m",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_cfd_dsmc": true,
            "teaching_quadratic_drag": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_atm_drag_from_catalog(
    catalog_json: &str,
    body: &str,
    v: Option<f64>,
    cd: Option<f64>,
    area: Option<f64>,
    mass: Option<f64>,
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
    let rho = f64_req(brow, "rho_kg_m3")?;
    let vv = v.unwrap_or(f64_req(defaults, "v_m_s")?);
    let ccd = cd.unwrap_or(f64_req(defaults, "cd")?);
    let aa = area.unwrap_or(f64_req(defaults, "area_m2")?);
    let mm = mass.unwrap_or(f64_req(defaults, "mass_kg")?);
    let mut doc = evaluate_atm_drag(body, rho, vv, ccd, aa, mm)?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_atm_drag_file(
    catalog_path: &Path,
    body: &str,
    v: Option<f64>,
    cd: Option<f64>,
    area: Option<f64>,
    mass: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_atm_drag_from_catalog(&text, body, v, cd, area, mass)
}

#[cfg(test)]
mod drag_tests {
    use super::*;

    #[test]
    fn earth_louder_than_mars_louder_than_vacuum() {
        let (fe, _) = atm_drag(1.225, 20.0, 1.0, 0.5, 50.0).unwrap();
        let (fm, _) = atm_drag(0.020, 20.0, 1.0, 0.5, 50.0).unwrap();
        let (fv, _) = atm_drag(0.0, 20.0, 1.0, 0.5, 50.0).unwrap();
        assert!(fe > fm && fm > fv && fv == 0.0);
    }
}
