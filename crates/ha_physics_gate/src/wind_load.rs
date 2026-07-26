//! Earth wind dynamic pressure + load (teaching).
//! q = ½ ρ v² · F = q Cd A

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const WIND_SCHEMA: &str = "ha_wind_load_eval_v1";
pub const WIND_ORACLE: &str = "ha_physics_gate_wind_load";

pub fn wind_load(rho: f64, v: f64, cd: f64, area: f64) -> Result<(f64, f64), String> {
    if !(rho.is_finite() && rho >= 0.0) {
        return Err("rho must be finite >= 0".into());
    }
    if !(v.is_finite() && v >= 0.0) {
        return Err("v must be finite >= 0".into());
    }
    if !(cd.is_finite() && cd >= 0.0) {
        return Err("Cd must be finite >= 0".into());
    }
    if !(area.is_finite() && area > 0.0) {
        return Err("area must be finite > 0".into());
    }
    let q = 0.5 * rho * v * v;
    let f = q * cd * area;
    Ok((q, f))
}

pub fn evaluate_wind_load(
    pack_id: &str,
    rho: f64,
    v: f64,
    cd: f64,
    area: f64,
) -> Result<Value, String> {
    let (q, f) = wind_load(rho, v, cd, area)?;
    Ok(json!({
        "schema": WIND_SCHEMA,
        "oracle": WIND_ORACLE,
        "pack_id": pack_id,
        "rho_kg_m3": rho,
        "v_m_s": v,
        "cd": cd,
        "area_m2": area,
        "q_pa": (q * 1e12).round() / 1e12,
        "f_wind_n": (f * 1e12).round() / 1e12,
        "equation": "q=0.5*rho*v^2; F=q*Cd*A",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_cfd": true,
            "teaching_wind_load": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_wind_load_from_catalog(
    catalog_json: &str,
    pack_id: &str,
    v: Option<f64>,
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
    let vv = match v {
        Some(x) => x,
        None => f64_req(pack, "v_m_s")?,
    };
    let mut doc = evaluate_wind_load(
        pack_id,
        f64_req(pack, "rho_kg_m3")?,
        vv,
        f64_req(pack, "cd")?,
        f64_req(pack, "area_m2")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_wind_load_file(
    catalog_path: &Path,
    pack_id: &str,
    v: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_wind_load_from_catalog(&text, pack_id, v)
}
