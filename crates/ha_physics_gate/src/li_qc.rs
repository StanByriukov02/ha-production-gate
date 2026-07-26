//! Li lunar-g cone resistance q_c(h) (GAP-MR-11 teaching fit).
//!
//! q_c = A * exp(-h/B) + C   (h in metres, q_c in kPa)
//!
//! Adjunct to Bekker — not Wong soil oracle. Not MEASURED.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const LI_QC_SCHEMA: &str = "ha_li_bearing_qc_eval_v1";
pub const LI_QC_ORACLE: &str = "ha_physics_gate_li_qc";

pub fn q_c_kpa(depth_m: f64, a: f64, b_m: f64, c: f64) -> Result<f64, String> {
    if !(depth_m.is_finite() && depth_m >= 0.0) {
        return Err("depth_m must be finite >= 0".into());
    }
    if !(a.is_finite() && b_m.is_finite() && b_m > 0.0 && c.is_finite()) {
        return Err("Li coeffs A,B>0,C must be finite".into());
    }
    Ok(a * (-depth_m / b_m).exp() + c)
}

pub fn evaluate_li_qc(depth_mm: f64, a: f64, b_m: f64, c: f64) -> Result<Value, String> {
    if !(depth_mm.is_finite() && depth_mm >= 0.0) {
        return Err("depth_mm must be finite >= 0".into());
    }
    let h_m = depth_mm / 1000.0;
    let q = q_c_kpa(h_m, a, b_m, c)?;
    Ok(json!({
        "schema": LI_QC_SCHEMA,
        "oracle": LI_QC_ORACLE,
        "depth_mm": depth_mm,
        "depth_m": h_m,
        "q_c_kpa": (q * 1e9).round() / 1e9,
        "coeffs": {"A": a, "B_m": b_m, "C": c},
        "equation": "q_c = A*exp(-h/B) + C",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "teaching_li_fit": true,
            "adjunct_not_bekker_oracle": true
        }
    }))
}

pub fn evaluate_li_qc_from_catalog(catalog_json: &str, depth_mm: f64) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let coeffs = root
        .get("coeffs")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.coeffs required".to_string())?;
    let a = coeffs
        .get("A")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "coeffs.A required".to_string())?;
    let b = coeffs
        .get("B_m")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "coeffs.B_m required".to_string())?;
    let c = coeffs
        .get("C")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "coeffs.C required".to_string())?;
    let gates = root.get("gates").and_then(|v| v.as_object());
    let dmin = gates
        .and_then(|g| g.get("depth_mm_min"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let dmax = gates
        .and_then(|g| g.get("depth_mm_max"))
        .and_then(|v| v.as_f64())
        .unwrap_or(1.0e6);
    if depth_mm < dmin || depth_mm > dmax {
        return Err(format!("depth_mm={depth_mm} outside gates [{dmin},{dmax}]"));
    }
    let mut doc = evaluate_li_qc(depth_mm, a, b, c)?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_li_qc_file(catalog_path: &Path, depth_mm: f64) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_li_qc_from_catalog(&text, depth_mm)
}

#[cfg(test)]
mod li_tests {
    use super::*;

    #[test]
    fn deeper_higher_qc() {
        let shallow = q_c_kpa(0.01, -1137.5, 0.16, 1110.9).unwrap();
        let deep = q_c_kpa(0.05, -1137.5, 0.16, 1110.9).unwrap();
        assert!(deep > shallow);
    }
}
