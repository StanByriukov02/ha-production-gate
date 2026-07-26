//! TID accumulate teaching: D = dose_rate · t; proxy = D / D_fail.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const TID_SCHEMA: &str = "ha_rad_damage_tid_eval_v1";
pub const TID_ORACLE: &str = "ha_physics_gate_rad_damage_tid";

pub fn tid_accumulate(dose_rate: f64, t_h: f64, d_fail: f64) -> Result<(f64, f64), String> {
    if !(dose_rate.is_finite() && dose_rate >= 0.0) {
        return Err("dose_rate must be finite >= 0".into());
    }
    if !(t_h.is_finite() && t_h >= 0.0) {
        return Err("t_h must be finite >= 0".into());
    }
    if !(d_fail.is_finite() && d_fail > 0.0) {
        return Err("d_fail must be finite > 0".into());
    }
    let d = dose_rate * t_h;
    Ok((d, d / d_fail))
}

pub fn evaluate_rad_damage_tid(
    pack_id: &str,
    dose_rate: f64,
    t_h: f64,
    d_fail: f64,
) -> Result<Value, String> {
    let (d, proxy) = tid_accumulate(dose_rate, t_h, d_fail)?;
    Ok(json!({
        "schema": TID_SCHEMA,
        "oracle": TID_ORACLE,
        "pack_id": pack_id,
        "dose_rate_gy_h": dose_rate,
        "t_h": t_h,
        "d_fail_gy": d_fail,
        "d_tid_gy": (d * 1e12).round() / 1e12,
        "damage_proxy": (proxy * 1e12).round() / 1e12,
        "equation": "D=dose_rate*t; proxy=D/D_fail",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_creme": true,
            "teaching_tid": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_rad_damage_tid_from_catalog(
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
    let mut doc = evaluate_rad_damage_tid(
        pack_id,
        f64_req(pack, "dose_rate_gy_h")?,
        t,
        f64_req(pack, "d_fail_gy")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_rad_damage_tid_file(
    catalog_path: &Path,
    pack_id: &str,
    t_h: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_rad_damage_tid_from_catalog(&text, pack_id, t_h)
}
