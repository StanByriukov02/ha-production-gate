//! Acoustic / seismic wave speeds + path attenuation (teaching).
//!
//! vp = sqrt((K + 4/3 G) / ρ)
//! vs = sqrt(G / ρ)
//! T = exp(-α L)
//!
//! Not full seismogram. Not MEASURED lunar Q.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const ACOUSTIC_SCHEMA: &str = "ha_acoustic_wave_eval_v1";
pub const ACOUSTIC_ORACLE: &str = "ha_physics_gate_acoustic_wave";

pub fn wave_speeds(k_pa: f64, g_pa: f64, rho: f64) -> Result<(f64, f64), String> {
    if !(k_pa.is_finite() && k_pa > 0.0 && g_pa.is_finite() && g_pa > 0.0) {
        return Err("K,G must be finite > 0".into());
    }
    if !(rho.is_finite() && rho > 0.0) {
        return Err("rho must be finite > 0".into());
    }
    let vp = ((k_pa + 4.0 / 3.0 * g_pa) / rho).sqrt();
    let vs = (g_pa / rho).sqrt();
    Ok((vp, vs))
}

pub fn evaluate_acoustic_wave(
    medium_id: &str,
    k_pa: f64,
    g_pa: f64,
    rho: f64,
    alpha: f64,
    path_m: f64,
) -> Result<Value, String> {
    if !(alpha.is_finite() && alpha >= 0.0) {
        return Err("alpha must be finite >= 0".into());
    }
    if !(path_m.is_finite() && path_m >= 0.0) {
        return Err("path_m must be finite >= 0".into());
    }
    let (vp, vs) = wave_speeds(k_pa, g_pa, rho)?;
    let t = (-alpha * path_m).exp();
    Ok(json!({
        "schema": ACOUSTIC_SCHEMA,
        "oracle": ACOUSTIC_ORACLE,
        "medium_id": medium_id,
        "vp_m_s": (vp * 1e9).round() / 1e9,
        "vs_m_s": (vs * 1e9).round() / 1e9,
        "alpha_per_m": alpha,
        "path_m": path_m,
        "transmittance": (t * 1e12).round() / 1e12,
        "equation": "vp=√((K+4/3G)/ρ); vs=√(G/ρ); T=e^{-αL}",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_full_seismogram": true,
            "teaching_elastic_waves": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_acoustic_wave_from_catalog(
    catalog_json: &str,
    medium_id: &str,
    path_m: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let media = root
        .get("media")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.media required".to_string())?;
    let m = media
        .get(medium_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown medium={medium_id}"))?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let path = path_m.unwrap_or(f64_req(defaults, "path_m")?);
    let mut doc = evaluate_acoustic_wave(
        medium_id,
        f64_req(m, "K_pa")?,
        f64_req(m, "G_pa")?,
        f64_req(m, "rho_kg_m3")?,
        f64_req(m, "alpha_per_m")?,
        path,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_acoustic_wave_file(
    catalog_path: &Path,
    medium_id: &str,
    path_m: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_acoustic_wave_from_catalog(&text, medium_id, path_m)
}

#[cfg(test)]
mod acoustic_tests {
    use super::*;

    #[test]
    fn basalt_faster_than_regolith() {
        let (vp_b, _) = wave_speeds(5.0e10, 3.0e10, 2800.0).unwrap();
        let (vp_r, _) = wave_speeds(2.0e7, 5.0e6, 1500.0).unwrap();
        assert!(vp_b > vp_r);
    }
}
