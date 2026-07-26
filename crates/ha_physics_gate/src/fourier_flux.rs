//! 1D Fourier conduction flux teaching: q = k · ΔT / Δx.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const FOURIER_SCHEMA: &str = "ha_fourier_flux_eval_v1";
pub const FOURIER_ORACLE: &str = "ha_physics_gate_fourier_flux";

pub fn fourier_q(k: f64, dt: f64, dx: f64) -> Result<f64, String> {
    if !(k.is_finite() && k >= 0.0) {
        return Err("k must be finite >= 0".into());
    }
    if !dt.is_finite() {
        return Err("dt must be finite".into());
    }
    if !(dx.is_finite() && dx > 0.0) {
        return Err("dx must be finite > 0".into());
    }
    Ok(k * dt / dx)
}

pub fn evaluate_fourier_flux(pack_id: &str, k: f64, dt: f64, dx: f64) -> Result<Value, String> {
    let q = fourier_q(k, dt, dx)?;
    Ok(json!({
        "schema": FOURIER_SCHEMA,
        "oracle": FOURIER_ORACLE,
        "pack_id": pack_id,
        "k_w_mk": k,
        "dt_k": dt,
        "dx_m": dx,
        "q_flux_w_m2": (q * 1e9).round() / 1e9,
        "equation": "q=k*dT/dx",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_fem": true,
            "teaching_fourier": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_fourier_flux_from_catalog(
    catalog_json: &str,
    pack_id: &str,
    dt: Option<f64>,
    dx: Option<f64>,
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
    let dtk = dt.unwrap_or(f64_req(defaults, "dt_k")?);
    let dxm = dx.unwrap_or(f64_req(defaults, "dx_m")?);
    let mut doc = evaluate_fourier_flux(pack_id, f64_req(pack, "k_w_mk")?, dtk, dxm)?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_fourier_flux_file(
    catalog_path: &Path,
    pack_id: &str,
    dt: Option<f64>,
    dx: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_fourier_flux_from_catalog(&text, pack_id, dt, dx)
}
