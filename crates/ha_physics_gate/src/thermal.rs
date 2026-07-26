//! Regolith thermal conductivity k(T) (U4 M1 / GAP-MR-01).
//!
//! k = k_solid + b_rad * T^3
//! if apply_cryo && T < t_cryo: k *= cryo_scale
//!
//! Coefficients live in ON catalog JSON (Sakatani/Heiken + Woods cryo ADAPT).
//! Not Apollo site MEASURED. Python is glue only.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const THERMAL_SCHEMA: &str = "ha_regolith_thermal_k_eval_v1";
pub const THERMAL_ORACLE: &str = "ha_physics_gate_thermal_k";

/// Base Sakatani vacuum law: k_solid + b_rad * T^3.
pub fn k_w_mk(k_solid: f64, b_rad: f64, t_k: f64) -> Result<f64, String> {
    if !(k_solid.is_finite() && k_solid >= 0.0) {
        return Err("k_solid must be finite >= 0".into());
    }
    if !(b_rad.is_finite() && b_rad >= 0.0) {
        return Err("b_rad must be finite >= 0".into());
    }
    if !t_k.is_finite() || t_k <= 0.0 {
        return Err("t_k must be finite > 0".into());
    }
    Ok(k_solid + b_rad * t_k.powi(3))
}

/// Apply Woods-style cryo leg when T < t_cryo.
pub fn apply_cryo_scale(k: f64, t_k: f64, t_cryo_k: f64, scale: f64) -> Result<(f64, f64), String> {
    if !(k.is_finite() && k >= 0.0) {
        return Err("k must be finite >= 0".into());
    }
    if !(t_cryo_k.is_finite() && t_cryo_k > 0.0) {
        return Err("t_cryo_k must be finite > 0".into());
    }
    if !(scale.is_finite() && scale > 0.0 && scale <= 1.0) {
        return Err("cryo scale must be in (0, 1]".into());
    }
    if t_k < t_cryo_k {
        Ok((k * scale, scale))
    } else {
        Ok((k, 1.0))
    }
}

pub fn evaluate_thermal_k(
    material_id: &str,
    t_k: f64,
    k_solid: f64,
    b_rad: f64,
    apply_cryo: bool,
    t_cryo_k: f64,
    cryo_scale: f64,
) -> Result<Value, String> {
    let k_base = k_w_mk(k_solid, b_rad, t_k)?;
    let (k_out, applied) = if apply_cryo {
        apply_cryo_scale(k_base, t_k, t_cryo_k, cryo_scale)?
    } else {
        (k_base, 1.0)
    };
    Ok(json!({
        "schema": THERMAL_SCHEMA,
        "oracle": THERMAL_ORACLE,
        "material_id": material_id,
        "t_k": t_k,
        "k_solid_w_mk": k_solid,
        "b_rad": b_rad,
        "k_base_w_mk": (k_base * 1e12).round() / 1e12,
        "k_w_mk": (k_out * 1e12).round() / 1e12,
        "cryo_applied": apply_cryo && applied < 1.0,
        "cryo_scale_applied": applied,
        "t_cryo_k": t_cryo_k,
        "equation": "k = k_solid + b_rad*T^3; cryo: k*=scale if T<t_cryo",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "teaching_adapt_k_t": true,
            "cryo_order_of_magnitude_adapt": true
        }
    }))
}

pub fn evaluate_thermal_k_from_catalog(
    catalog_json: &str,
    material_id: &str,
    t_k: f64,
    apply_cryo: bool,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let mats = root
        .get("materials")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.missing materials object".to_string())?;
    let mat = mats
        .get(material_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown material_id={material_id}"))?;
    let k_solid = mat
        .get("k_solid_w_mk")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "material.k_solid_w_mk required".to_string())?;
    let b_rad = mat
        .get("b_rad")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "material.b_rad required".to_string())?;
    let gates = root.get("gates").and_then(|v| v.as_object());
    let t_min = gates
        .and_then(|g| g.get("t_min_k"))
        .and_then(|v| v.as_f64())
        .unwrap_or(1.0);
    let t_max = gates
        .and_then(|g| g.get("t_max_k"))
        .and_then(|v| v.as_f64())
        .unwrap_or(1000.0);
    if t_k < t_min || t_k > t_max {
        return Err(format!("t_k={t_k} outside catalog gates [{t_min},{t_max}]"));
    }
    let cryo = root.get("cryo_leg").and_then(|v| v.as_object());
    let t_cryo = cryo
        .and_then(|c| c.get("t_cryo_k"))
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "catalog.cryo_leg.t_cryo_k required".to_string())?;
    let cryo_scale = cryo
        .and_then(|c| c.get("k_scale_below_t_cryo"))
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "catalog.cryo_leg.k_scale_below_t_cryo required".to_string())?;
    let mut doc = evaluate_thermal_k(
        material_id,
        t_k,
        k_solid,
        b_rad,
        apply_cryo,
        t_cryo,
        cryo_scale,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "label".into(),
            mat.get("label").cloned().unwrap_or(json!(material_id)),
        );
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
        obj.insert(
            "catalog_equation".into(),
            root.get("equation").cloned().unwrap_or(json!("")),
        );
        if let Some(band) = mat.get("heiken_band_w_mk") {
            obj.insert("heiken_band_w_mk".into(), band.clone());
        }
        if let Some(cite) = mat.get("cite") {
            obj.insert("cite".into(), cite.clone());
        }
    }
    Ok(doc)
}

pub fn evaluate_thermal_k_file(
    catalog_path: &Path,
    material_id: &str,
    t_k: f64,
    apply_cryo: bool,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_thermal_k_from_catalog(&text, material_id, t_k, apply_cryo)
}

#[cfg(test)]
mod thermal_tests {
    use super::*;

    #[test]
    fn k_increases_with_t() {
        let cold = k_w_mk(0.0154, 2.45e-10, 80.0).unwrap();
        let warm = k_w_mk(0.0154, 2.45e-10, 220.0).unwrap();
        assert!(warm > cold);
    }

    #[test]
    fn cryo_reduces_below_threshold() {
        let k = k_w_mk(0.0154, 2.45e-10, 80.0).unwrap();
        let (k_c, s) = apply_cryo_scale(k, 80.0, 150.0, 0.1).unwrap();
        assert!((s - 0.1).abs() < 1e-12);
        assert!((k_c - k * 0.1).abs() < 1e-15);
    }

    #[test]
    fn cryo_noop_above_threshold() {
        let k = k_w_mk(0.0154, 2.45e-10, 220.0).unwrap();
        let (k_c, s) = apply_cryo_scale(k, 220.0, 150.0, 0.1).unwrap();
        assert!((s - 1.0).abs() < 1e-12);
        assert!((k_c - k).abs() < 1e-15);
    }
}
