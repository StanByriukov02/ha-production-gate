//! Battery Peukert discharge + linear OCV–SOC (teaching).
//!
//! I^k · t = C_p  =>  t = C_p / I^k
//! OCV = Voc_full - (Voc_full - Voc_empty) * (1 - soc)
//!
//! Not BMS MEASURED. Not Nernst cell model.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const BATTERY_SCHEMA: &str = "ha_battery_peukert_eval_v1";
pub const BATTERY_ORACLE: &str = "ha_physics_gate_battery_peukert";

pub fn peukert_time_h(c_p: f64, k: f64, i_a: f64) -> Result<f64, String> {
    if !(c_p.is_finite() && c_p > 0.0) {
        return Err("c_p must be finite > 0".into());
    }
    if !(k.is_finite() && k >= 1.0) {
        return Err("k must be finite >= 1".into());
    }
    if !(i_a.is_finite() && i_a > 0.0) {
        return Err("i_a must be finite > 0".into());
    }
    Ok(c_p / i_a.powf(k))
}

pub fn ocv_v(soc: f64, voc_full: f64, voc_empty: f64) -> Result<f64, String> {
    if !(soc.is_finite() && (0.0..=1.0).contains(&soc)) {
        return Err("soc must be in [0,1]".into());
    }
    if !(voc_full.is_finite() && voc_empty.is_finite() && voc_full > voc_empty) {
        return Err("voc_full > voc_empty required".into());
    }
    Ok(voc_full - (voc_full - voc_empty) * (1.0 - soc))
}

pub fn evaluate_battery_peukert(
    pack_id: &str,
    c_p: f64,
    k: f64,
    voc_full: f64,
    voc_empty: f64,
    i_a: f64,
    soc: f64,
) -> Result<Value, String> {
    let t_h = peukert_time_h(c_p, k, i_a)?;
    let ocv = ocv_v(soc, voc_full, voc_empty)?;
    let eff_ah = i_a * t_h;
    Ok(json!({
        "schema": BATTERY_SCHEMA,
        "oracle": BATTERY_ORACLE,
        "pack_id": pack_id,
        "i_a": i_a,
        "soc": soc,
        "k": k,
        "c_p": c_p,
        "t_discharge_h": (t_h * 1e12).round() / 1e12,
        "effective_ah": (eff_ah * 1e12).round() / 1e12,
        "ocv_v": (ocv * 1e9).round() / 1e9,
        "equation": "t=C_p/I^k; OCV=linear(soc)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_nernst_bms": true,
            "teaching_peukert_ocv": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_battery_peukert_from_catalog(
    catalog_json: &str,
    pack_id: &str,
    i_a: Option<f64>,
    soc: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let packs = root
        .get("packs")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.packs required".to_string())?;
    let pack = packs
        .get(pack_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown pack={pack_id}"))?;
    let defaults = root
        .get("defaults")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.defaults required".to_string())?;
    let i = i_a.unwrap_or(f64_req(defaults, "i_a")?);
    let s = soc.unwrap_or(f64_req(defaults, "soc")?);
    let mut doc = evaluate_battery_peukert(
        pack_id,
        f64_req(pack, "c_p_ah_k")?,
        f64_req(pack, "k")?,
        f64_req(pack, "voc_full_v")?,
        f64_req(pack, "voc_empty_v")?,
        i,
        s,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_battery_peukert_file(
    catalog_path: &Path,
    pack_id: &str,
    i_a: Option<f64>,
    soc: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_battery_peukert_from_catalog(&text, pack_id, i_a, soc)
}

#[cfg(test)]
mod battery_tests {
    use super::*;

    #[test]
    fn higher_k_shorter_time() {
        let mild = peukert_time_h(12.0, 1.05, 8.0).unwrap();
        let harsh = peukert_time_h(10.0, 1.35, 8.0).unwrap();
        assert!(mild > harsh);
    }
}
