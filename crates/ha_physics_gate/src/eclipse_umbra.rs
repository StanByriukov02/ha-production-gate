//! Circular-orbit beta=0 umbra eclipse fraction (teaching).
//! f_e = (1/π) · acos(√(r² − R²) / r)

use serde_json::{json, Value};
use std::f64::consts::PI;
use std::fs;
use std::path::Path;

pub const ECLIPSE_SCHEMA: &str = "ha_eclipse_umbra_eval_v1";
pub const ECLIPSE_ORACLE: &str = "ha_physics_gate_eclipse_umbra";

pub fn eclipse_fraction(r_km: f64, r_earth_km: f64) -> Result<f64, String> {
    if !(r_km.is_finite() && r_km > 0.0 && r_earth_km.is_finite() && r_earth_km > 0.0) {
        return Err("r and R_earth must be finite > 0".into());
    }
    if r_km <= r_earth_km {
        return Err("r must be > R_earth".into());
    }
    let arg = ((r_km * r_km - r_earth_km * r_earth_km).sqrt()) / r_km;
    if !(arg.is_finite() && (0.0..=1.0).contains(&arg)) {
        return Err("eclipse acos arg out of range".into());
    }
    Ok(arg.acos() / PI)
}

pub fn evaluate_eclipse_umbra(
    orbit_id: &str,
    r_km: f64,
    r_earth_km: f64,
    period_s: f64,
) -> Result<Value, String> {
    let f = eclipse_fraction(r_km, r_earth_km)?;
    if !(period_s.is_finite() && period_s > 0.0) {
        return Err("period_s must be finite > 0".into());
    }
    let t_e = f * period_s;
    Ok(json!({
        "schema": ECLIPSE_SCHEMA,
        "oracle": ECLIPSE_ORACLE,
        "orbit_id": orbit_id,
        "r_km": r_km,
        "R_earth_km": r_earth_km,
        "period_s": period_s,
        "f_eclipse": (f * 1e12).round() / 1e12,
        "t_eclipse_s": (t_e * 1e9).round() / 1e9,
        "equation": "f_e=(1/pi)*acos(sqrt(r^2-R^2)/r)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "beta_zero_only": true,
            "teaching_eclipse": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_eclipse_umbra_from_catalog(
    catalog_json: &str,
    orbit_id: &str,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let orbits = root
        .get("orbits")
        .and_then(|x| x.as_object())
        .ok_or_else(|| "catalog.orbits required".to_string())?;
    let orb = orbits
        .get(orbit_id)
        .and_then(|x| x.as_object())
        .ok_or_else(|| format!("unknown orbit={orbit_id}"))?;
    let mut doc = evaluate_eclipse_umbra(
        orbit_id,
        f64_req(orb, "r_km")?,
        f64_req(orb, "R_earth_km")?,
        f64_req(orb, "period_s")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_eclipse_umbra_file(catalog_path: &Path, orbit_id: &str) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_eclipse_umbra_from_catalog(&text, orbit_id)
}
