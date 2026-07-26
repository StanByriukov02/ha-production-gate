//! Trapped belt dose-rate class teaching.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const BELT_SCHEMA: &str = "ha_trapped_belt_eval_v1";
pub const BELT_ORACLE: &str = "ha_physics_gate_trapped_belt";

pub fn belt_dose(base: f64, scale: f64, t_h: f64) -> Result<(f64, f64), String> {
    if !(base.is_finite() && base >= 0.0) {
        return Err("base_rate must be finite >= 0".into());
    }
    if !(scale.is_finite() && scale >= 0.0) {
        return Err("belt_scale must be finite >= 0".into());
    }
    if !(t_h.is_finite() && t_h >= 0.0) {
        return Err("t_h must be finite >= 0".into());
    }
    let rate = base * scale;
    Ok((rate, rate * t_h))
}

pub fn evaluate_trapped_belt(
    pack_id: &str,
    base: f64,
    scale: f64,
    t_h: f64,
) -> Result<Value, String> {
    let (rate, window) = belt_dose(base, scale, t_h)?;
    Ok(json!({
        "schema": BELT_SCHEMA,
        "oracle": BELT_ORACLE,
        "pack_id": pack_id,
        "base_rate_gy_h": base,
        "belt_scale": scale,
        "t_h": t_h,
        "dose_rate_gy_h": (rate * 1e12).round() / 1e12,
        "window_dose_gy": (window * 1e12).round() / 1e12,
        "equation": "dose_rate=base*belt_scale; window=dose_rate*t",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_ae9": true,
            "teaching_trapped_belt": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_trapped_belt_from_catalog(
    catalog_json: &str,
    pack_id: &str,
    t_h: Option<f64>,
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
    let t = t_h.unwrap_or(f64_req(defaults, "t_h")?);
    let mut doc = evaluate_trapped_belt(
        pack_id,
        f64_req(pack, "base_rate_gy_h")?,
        f64_req(pack, "belt_scale")?,
        t,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_trapped_belt_file(
    catalog_path: &Path,
    pack_id: &str,
    t_h: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_trapped_belt_from_catalog(&text, pack_id, t_h)
}
