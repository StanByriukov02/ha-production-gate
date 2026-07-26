//! Janosi–Hanamoto τ(j) full curve (Wong teaching).
//!
//! τ(j) = (c + p tan φ)(1 − e^{−j/K})
//! H(j) = τ(j) · A
//!
//! Point shear already in bekker-eval — this is the curve domain.
//! Not MEASURED bevameter slip curve.

use crate::bekker::{drawbar_pull_n, janosi_hanamoto_shear_kpa};
use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const JANOSI_CURVE_SCHEMA: &str = "ha_janosi_shear_curve_eval_v1";
pub const JANOSI_CURVE_ORACLE: &str = "ha_physics_gate_janosi_curve";

pub fn janosi_curve(
    c_kpa: f64,
    phi_deg: f64,
    k_m: f64,
    p_kpa: f64,
    area_m2: f64,
    j_max_m: f64,
    n_points: usize,
) -> Result<(f64, Vec<(f64, f64, f64)>), String> {
    if !(j_max_m.is_finite() && j_max_m > 0.0) {
        return Err("j_max_m must be finite > 0".into());
    }
    if n_points < 2 {
        return Err("n_points must be >= 2".into());
    }
    let tau_inf = janosi_hanamoto_shear_kpa(c_kpa, phi_deg, k_m, p_kpa, k_m * 50.0)?;
    let mut pts = Vec::with_capacity(n_points);
    for i in 0..n_points {
        let frac = i as f64 / (n_points - 1) as f64;
        let j = j_max_m * frac;
        let tau = janosi_hanamoto_shear_kpa(c_kpa, phi_deg, k_m, p_kpa, j)?;
        let h = drawbar_pull_n(tau, area_m2)?;
        pts.push((j, tau, h));
    }
    Ok((tau_inf, pts))
}

pub fn evaluate_janosi_curve(
    soil_id: &str,
    c_kpa: f64,
    phi_deg: f64,
    k_m: f64,
    p_kpa: f64,
    area_m2: f64,
    j_max_m: f64,
    n_points: usize,
) -> Result<Value, String> {
    let (tau_inf, pts) = janosi_curve(c_kpa, phi_deg, k_m, p_kpa, area_m2, j_max_m, n_points)?;
    let curve: Vec<Value> = pts
        .iter()
        .map(|(j, t, h)| {
            json!({
                "j_m": (*j * 1e12).round() / 1e12,
                "tau_kpa": (*t * 1e9).round() / 1e9,
                "drawbar_n": (*h * 1e6).round() / 1e6
            })
        })
        .collect();
    let tau0 = pts.first().map(|p| p.1).unwrap_or(0.0);
    let tau_end = pts.last().map(|p| p.1).unwrap_or(0.0);
    Ok(json!({
        "schema": JANOSI_CURVE_SCHEMA,
        "oracle": JANOSI_CURVE_ORACLE,
        "soil_id": soil_id,
        "c_kpa": c_kpa,
        "phi_deg": phi_deg,
        "K_m": k_m,
        "p_kpa": p_kpa,
        "contact_area_m2": area_m2,
        "j_max_m": j_max_m,
        "n_points": n_points,
        "tau_inf_kpa": (tau_inf * 1e9).round() / 1e9,
        "tau_at_0_kpa": (tau0 * 1e9).round() / 1e9,
        "tau_at_jmax_kpa": (tau_end * 1e9).round() / 1e9,
        "curve": curve,
        "equation": "τ(j)=(c+p tanφ)(1-e^{-j/K}); H=τA",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "teaching_janosi_curve": true,
            "point_shear_also_in_bekker_eval": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_janosi_curve_from_catalog(
    catalog_json: &str,
    soil_id: &str,
    p_kpa: Option<f64>,
    j_max_m: Option<f64>,
    n_points: Option<usize>,
    area_m2: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let soils = root
        .get("soils")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.soils required".to_string())?;
    let soil = soils
        .get(soil_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown soil_id={soil_id}"))?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let p = p_kpa.unwrap_or(f64_req(defaults, "p_kpa")?);
    let jmax = j_max_m.unwrap_or(f64_req(defaults, "j_max_m")?);
    let area = area_m2.unwrap_or(f64_req(defaults, "contact_area_m2")?);
    let np = n_points.unwrap_or(
        defaults
            .get("n_points")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| "defaults.n_points required".to_string())? as usize,
    );
    let mut doc = evaluate_janosi_curve(
        soil_id,
        f64_req(soil, "c_kpa")?,
        f64_req(soil, "phi_deg")?,
        f64_req(soil, "K_m")?,
        p,
        area,
        jmax,
        np,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_janosi_curve_file(
    catalog_path: &Path,
    soil_id: &str,
    p_kpa: Option<f64>,
    j_max_m: Option<f64>,
    n_points: Option<usize>,
    area_m2: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_janosi_curve_from_catalog(&text, soil_id, p_kpa, j_max_m, n_points, area_m2)
}

#[cfg(test)]
mod janosi_curve_tests {
    use super::*;

    #[test]
    fn monotone_and_firm_louder() {
        let (_, firm) = janosi_curve(3.0, 30.0, 0.02, 35.0, 0.05, 0.2, 11).unwrap();
        let (_, soft) = janosi_curve(0.5, 15.0, 0.04, 35.0, 0.05, 0.2, 11).unwrap();
        assert!(firm[0].1.abs() < 1e-12);
        assert!(firm.last().unwrap().1 > firm[1].1);
        assert!(firm.last().unwrap().1 > soft.last().unwrap().1);
    }
}
