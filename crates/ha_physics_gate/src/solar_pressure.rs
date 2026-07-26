//! Solar radiation pressure cannonball (teaching).
//! P = S/c · F = P · A · Cr · max(cos i, 0)²

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const SRP_SCHEMA: &str = "ha_solar_pressure_eval_v1";
pub const SRP_ORACLE: &str = "ha_physics_gate_solar_pressure";

pub fn solar_pressure_force(s: f64, c: f64, area: f64, cr: f64, i_rad: f64) -> Result<(f64, f64), String> {
    if !(s.is_finite() && s > 0.0) {
        return Err("S must be finite > 0".into());
    }
    if !(c.is_finite() && c > 0.0) {
        return Err("c must be finite > 0".into());
    }
    if !(area.is_finite() && area > 0.0) {
        return Err("area must be finite > 0".into());
    }
    if !(cr.is_finite() && cr >= 0.0) {
        return Err("Cr must be finite >= 0".into());
    }
    if !i_rad.is_finite() {
        return Err("i_rad must be finite".into());
    }
    let p = s / c;
    let cos_i = i_rad.cos().max(0.0);
    let f = p * area * cr * cos_i * cos_i;
    Ok((p, f))
}

pub fn evaluate_solar_pressure(
    pack_id: &str,
    s: f64,
    c: f64,
    area: f64,
    cr: f64,
    i_rad: f64,
) -> Result<Value, String> {
    let (p, f) = solar_pressure_force(s, c, area, cr, i_rad)?;
    Ok(json!({
        "schema": SRP_SCHEMA,
        "oracle": SRP_ORACLE,
        "pack_id": pack_id,
        "s_w_m2": s,
        "c_m_s": c,
        "area_m2": area,
        "cr": cr,
        "i_rad": i_rad,
        "p_pa": (p * 1e15).round() / 1e15,
        "f_srp_n": (f * 1e15).round() / 1e15,
        "equation": "P=S/c; F=P*A*Cr*max(cos(i),0)^2",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_brdf": true,
            "teaching_srp": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_solar_pressure_from_catalog(
    catalog_json: &str,
    pack_id: &str,
    i_rad: Option<f64>,
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
    let constants = root
        .get("constants")
        .and_then(|x| x.as_object())
        .ok_or_else(|| "catalog.constants required".to_string())?;
    let i = match i_rad {
        Some(x) => x,
        None => f64_req(pack, "i_rad")?,
    };
    let mut doc = evaluate_solar_pressure(
        pack_id,
        f64_req(pack, "s_w_m2")?,
        f64_req(constants, "c_m_s")?,
        f64_req(pack, "area_m2")?,
        f64_req(pack, "cr")?,
        i,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_solar_pressure_file(
    catalog_path: &Path,
    pack_id: &str,
    i_rad: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_solar_pressure_from_catalog(&text, pack_id, i_rad)
}
