//! Rigid-body ballistic hop under constant g (teaching).
//!
//! apex = v_up^2 / (2g)
//! tof = 2 v_up / g
//! range = v_h * tof
//!
//! Not constrained multibody 6DOF. Not MEASURED hopper.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const HOP_SCHEMA: &str = "ha_rigid_hop_eval_v1";
pub const HOP_ORACLE: &str = "ha_physics_gate_rigid_hop";

pub fn ballistic_hop(v_up: f64, v_h: f64, g: f64) -> Result<(f64, f64, f64), String> {
    if !(v_up.is_finite() && v_up >= 0.0) {
        return Err("v_up must be finite >= 0".into());
    }
    if !(v_h.is_finite() && v_h >= 0.0) {
        return Err("v_h must be finite >= 0".into());
    }
    if !(g.is_finite() && g > 0.0) {
        return Err("g must be finite > 0".into());
    }
    let apex = (v_up * v_up) / (2.0 * g);
    let tof = if v_up == 0.0 { 0.0 } else { 2.0 * v_up / g };
    let range = v_h * tof;
    Ok((apex, tof, range))
}

pub fn evaluate_rigid_hop(v_up: f64, v_h: f64, g: f64, body: &str) -> Result<Value, String> {
    let (apex, tof, range) = ballistic_hop(v_up, v_h, g)?;
    Ok(json!({
        "schema": HOP_SCHEMA,
        "oracle": HOP_ORACLE,
        "body": body,
        "g_m_s2": g,
        "v_up_m_s": v_up,
        "v_h_m_s": v_h,
        "apex_m": (apex * 1e12).round() / 1e12,
        "tof_s": (tof * 1e12).round() / 1e12,
        "range_m": (range * 1e12).round() / 1e12,
        "equation": "apex=v_up^2/(2g); tof=2 v_up/g; range=v_h*tof",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_constrained_multibody": true,
            "teaching_newton_ballistic": true,
            "vacuum_no_drag": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_rigid_hop_from_catalog(
    catalog_json: &str,
    v_up: Option<f64>,
    v_h: Option<f64>,
    body: Option<&str>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let gmap = root
        .get("g_m_s2")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.g_m_s2 required".to_string())?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let body_s = body
        .map(|s| s.to_string())
        .or_else(|| {
            defaults
                .get("body")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
        })
        .unwrap_or_else(|| "moon".to_string());
    let g = gmap
        .get(body_s.as_str())
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("unknown body={body_s}"))?;
    let vu = v_up.unwrap_or(f64_req(defaults, "v_up_m_s")?);
    let vh = v_h.unwrap_or(f64_req(defaults, "v_h_m_s")?);
    let gates = root.get("gates").and_then(|v| v.as_object());
    let umin = gates
        .and_then(|g| g.get("v_up_min"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let umax = gates
        .and_then(|g| g.get("v_up_max"))
        .and_then(|v| v.as_f64())
        .unwrap_or(100.0);
    if vu < umin || vu > umax {
        return Err(format!("v_up={vu} outside gates [{umin},{umax}]"));
    }
    let mut doc = evaluate_rigid_hop(vu, vh, g, &body_s)?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_rigid_hop_file(
    catalog_path: &Path,
    v_up: Option<f64>,
    v_h: Option<f64>,
    body: Option<&str>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_rigid_hop_from_catalog(&text, v_up, v_h, body)
}

#[cfg(test)]
mod hop_tests {
    use super::*;

    #[test]
    fn moon_higher_apex_than_earth() {
        let (am, _, _) = ballistic_hop(2.0, 1.0, 1.62).unwrap();
        let (ae, _, _) = ballistic_hop(2.0, 1.0, 9.81).unwrap();
        assert!(am > ae);
    }
}
