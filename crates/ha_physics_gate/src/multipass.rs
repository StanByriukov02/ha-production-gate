//! Multi-pass rut accumulation (teaching).
//!
//! z1 = Bekker virgin sinkage
//! z_N = z1 * N^α     (α ∈ (0,1) — diminishing per-pass growth)
//! Rc_N from Wong §2.5.1 at z_N
//!
//! Not densification FEM. Not MEASURED multi-pass campaign.

use crate::bekker::{bekker_sinkage_m, compaction_resistance_n, BekkerParams};
use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const MULTIPASS_SCHEMA: &str = "ha_multipass_rut_eval_v1";
pub const MULTIPASS_ORACLE: &str = "ha_physics_gate_multipass_rut";

pub fn multipass_rut(
    n: f64,
    kc: f64,
    k_phi: f64,
    b_m: f64,
    p_kpa: f64,
    n_passes: f64,
    alpha: f64,
) -> Result<(f64, f64, f64, f64), String> {
    if !(n_passes.is_finite() && n_passes >= 1.0) {
        return Err("n_passes must be finite >= 1".into());
    }
    if !(alpha.is_finite() && alpha > 0.0 && alpha < 1.0) {
        return Err("alpha must be in (0,1)".into());
    }
    let params = BekkerParams {
        n,
        kc,
        k_phi,
        b_m,
        p_kpa,
    };
    let z1 = bekker_sinkage_m(params)?;
    let z_n = z1 * n_passes.powf(alpha);
    let rc_n = compaction_resistance_n(params, z_n)?;
    let rc_1 = compaction_resistance_n(params, z1)?;
    Ok((z1, z_n, rc_1, rc_n))
}

pub fn evaluate_multipass_rut(
    soil_id: &str,
    n: f64,
    kc: f64,
    k_phi: f64,
    b_m: f64,
    p_kpa: f64,
    n_passes: f64,
    alpha: f64,
) -> Result<Value, String> {
    let (z1, z_n, rc_1, rc_n) = multipass_rut(n, kc, k_phi, b_m, p_kpa, n_passes, alpha)?;
    Ok(json!({
        "schema": MULTIPASS_SCHEMA,
        "oracle": MULTIPASS_ORACLE,
        "soil_id": soil_id,
        "n_passes": n_passes,
        "alpha": alpha,
        "p_kpa": p_kpa,
        "b_m": b_m,
        "bekker": { "n": n, "kc": kc, "k_phi": k_phi },
        "z1_m": (z1 * 1e12).round() / 1e12,
        "z_n_m": (z_n * 1e12).round() / 1e12,
        "z1_mm": ((z1 * 1000.0) * 1e9).round() / 1e9,
        "z_n_mm": ((z_n * 1000.0) * 1e9).round() / 1e9,
        "rc_1_n": (rc_1 * 1e9).round() / 1e9,
        "rc_n_n": (rc_n * 1e9).round() / 1e9,
        "rut_growth_ratio": if z1 > 0.0 { ((z_n / z1) * 1e12).round() / 1e12 } else { 1.0 },
        "equation": "z1=Bekker; z_N=z1·N^α; Rc(z_N)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_densification_fem": true,
            "teaching_multipass_power_law": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_multipass_rut_from_catalog(
    catalog_json: &str,
    soil_id: &str,
    n_passes: Option<f64>,
    p_kpa: Option<f64>,
    b_m: Option<f64>,
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
    let gates = root.get("gates").and_then(|v| v.as_object());
    let np = n_passes.unwrap_or(f64_req(defaults, "n_passes")?);
    let p = p_kpa.unwrap_or(f64_req(defaults, "p_kpa")?);
    let b = b_m.unwrap_or(f64_req(defaults, "b_m")?);
    let npmin = gates
        .and_then(|g| g.get("n_passes_min"))
        .and_then(|v| v.as_f64())
        .unwrap_or(1.0);
    let npmax = gates
        .and_then(|g| g.get("n_passes_max"))
        .and_then(|v| v.as_f64())
        .unwrap_or(1000.0);
    if np < npmin || np > npmax {
        return Err(format!("n_passes={np} outside gates [{npmin},{npmax}]"));
    }
    let mut doc = evaluate_multipass_rut(
        soil_id,
        f64_req(soil, "n")?,
        f64_req(soil, "kc")?,
        f64_req(soil, "k_phi")?,
        b,
        p,
        np,
        f64_req(soil, "alpha")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_multipass_rut_file(
    catalog_path: &Path,
    soil_id: &str,
    n_passes: Option<f64>,
    p_kpa: Option<f64>,
    b_m: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_multipass_rut_from_catalog(&text, soil_id, n_passes, p_kpa, b_m)
}

#[cfg(test)]
mod multipass_tests {
    use super::*;

    #[test]
    fn more_passes_deeper_rut() {
        let (z1, z10, _, _) = multipass_rut(1.0, 40.0, 2000.0, 0.15, 35.0, 10.0, 0.15).unwrap();
        assert!(z10 > z1);
        assert!(z10 < z1 * 10.0); // sublinear
    }

    #[test]
    fn soft_grows_faster_than_firm() {
        let (_, z_firm, _, _) = multipass_rut(1.0, 40.0, 2000.0, 0.15, 35.0, 10.0, 0.15).unwrap();
        let (_, z_soft, _, _) = multipass_rut(0.8, 5.0, 200.0, 0.15, 35.0, 10.0, 0.40).unwrap();
        // soft absolute z much larger; growth ratio also higher via alpha
        assert!(z_soft > z_firm);
    }
}
