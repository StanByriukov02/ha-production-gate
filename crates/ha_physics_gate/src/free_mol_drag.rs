//! Free-molecular drag teaching: F = ρ v² Cd A (no continuum 1/2).

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const FMD_SCHEMA: &str = "ha_free_mol_drag_eval_v1";
pub const FMD_ORACLE: &str = "ha_physics_gate_free_mol_drag";

pub fn free_mol_drag(rho: f64, v: f64, cd: f64, area: f64) -> Result<f64, String> {
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
    Ok(rho * v * v * cd * area)
}

pub fn evaluate_free_mol_drag(
    pack_id: &str,
    rho: f64,
    v: f64,
    cd: f64,
    area: f64,
) -> Result<Value, String> {
    let f = free_mol_drag(rho, v, cd, area)?;
    Ok(json!({
        "schema": FMD_SCHEMA,
        "oracle": FMD_ORACLE,
        "pack_id": pack_id,
        "rho_kg_m3": rho,
        "v_m_s": v,
        "cd": cd,
        "area_m2": area,
        "f_fmd_n": (f * 1e18).round() / 1e18,
        "equation": "F=rho*v^2*Cd*A",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_dsmc": true,
            "teaching_free_mol": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_free_mol_drag_from_catalog(
    catalog_json: &str,
    pack_id: &str,
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
    let mut doc = evaluate_free_mol_drag(
        pack_id,
        f64_req(pack, "rho_kg_m3")?,
        f64_req(pack, "v_m_s")?,
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

pub fn evaluate_free_mol_drag_file(catalog_path: &Path, pack_id: &str) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_free_mol_drag_from_catalog(&text, pack_id)
}
