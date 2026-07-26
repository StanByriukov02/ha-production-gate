//! Vacuum radiative boundary condition (U4 / GAP-MR-08).
//!
//! q_rad   = eps * sigma * (T^4 - T_sky^4)
//! q_solar = (1 - albedo) * S * illum
//! q_net   = q_rad - q_solar
//! q_in    = -q_net   (into surface)
//!
//! Constants live in ON catalog. Not Diviner MEASURED. Python glue only.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const RADIATIVE_SCHEMA: &str = "ha_vacuum_radiative_bc_eval_v1";
pub const RADIATIVE_ORACLE: &str = "ha_physics_gate_radiative_bc";

pub fn radiative_fluxes(
    t_surf_k: f64,
    eps: f64,
    sigma: f64,
    t_sky_k: f64,
    albedo: f64,
    solar_w_m2: f64,
    illum: f64,
) -> Result<(f64, f64, f64), String> {
    if !t_surf_k.is_finite() || t_surf_k <= 0.0 {
        return Err("t_surf_k must be finite > 0".into());
    }
    if !(eps.is_finite() && (0.0..=1.0).contains(&eps)) {
        return Err("emissivity must be in [0,1]".into());
    }
    if !(sigma.is_finite() && sigma > 0.0) {
        return Err("stefan_boltzmann must be finite > 0".into());
    }
    if !t_sky_k.is_finite() || t_sky_k < 0.0 {
        return Err("t_sky_k must be finite >= 0".into());
    }
    if !(albedo.is_finite() && (0.0..=1.0).contains(&albedo)) {
        return Err("albedo must be in [0,1]".into());
    }
    if !(solar_w_m2.is_finite() && solar_w_m2 >= 0.0) {
        return Err("solar_constant must be finite >= 0".into());
    }
    if !(illum.is_finite() && (0.0..=1.0).contains(&illum)) {
        return Err("illum_frac must be in [0,1]".into());
    }
    let q_rad = eps * sigma * (t_surf_k.powi(4) - t_sky_k.powi(4));
    let q_solar = (1.0 - albedo) * solar_w_m2 * illum;
    let q_net = q_rad - q_solar;
    Ok((q_rad, q_solar, q_net))
}

pub fn evaluate_radiative_bc(
    zone: &str,
    t_surf_k: f64,
    eps: f64,
    sigma: f64,
    t_sky_rad_k: f64,
    t_sky_ambient_k: f64,
    albedo: f64,
    solar_w_m2: f64,
    illum: f64,
) -> Result<Value, String> {
    let (q_rad, q_solar, q_net) =
        radiative_fluxes(t_surf_k, eps, sigma, t_sky_rad_k, albedo, solar_w_m2, illum)?;
    let q_in = -q_net;
    Ok(json!({
        "schema": RADIATIVE_SCHEMA,
        "oracle": RADIATIVE_ORACLE,
        "zone": zone,
        "t_surf_k": t_surf_k,
        "t_sky_rad_k": t_sky_rad_k,
        "t_sky_ambient_k": t_sky_ambient_k,
        "q_rad_w_m2": (q_rad * 1e6).round() / 1e6,
        "q_solar_w_m2": (q_solar * 1e6).round() / 1e6,
        "q_net_w_m2": (q_net * 1e6).round() / 1e6,
        "q_in_surface_w_m2": (q_in * 1e6).round() / 1e6,
        "illum_frac": illum,
        "emissivity": eps,
        "albedo": albedo,
        "solar_constant_w_m2": solar_w_m2,
        "equation": "q_rad=eps*sigma*(T^4-Tsky^4); q_solar=(1-A)*S*illum; q_net=q_rad-q_solar",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "teaching_vacuum_bc": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("missing required {key}"))
}

pub fn evaluate_radiative_bc_from_catalog(
    catalog_json: &str,
    zone: &str,
    t_surf_k: f64,
    illum_override: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let constants = root
        .get("constants")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.missing constants".to_string())?;
    let sky = root
        .get("sky_temperature_k")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.missing sky_temperature_k".to_string())?;
    let zones = root
        .get("zones")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.missing zones".to_string())?;
    let zrow = zones
        .get(zone)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown zone={zone}"))?;

    let sigma = f64_req(constants, "stefan_boltzmann_w_m2_k4")?;
    let eps = f64_req(constants, "surface_emissivity_regolith")?;
    let solar = f64_req(constants, "solar_constant_w_m2")?;
    let albedo = f64_req(constants, "albedo_highland")?;
    let t_sky_rad = f64_req(sky, "deep_space")?;

    let ambient_key = zrow
        .get("sky_ambient_from")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "zone.sky_ambient_from required".to_string())?;
    let t_sky_ambient = f64_req(sky, ambient_key)?;

    let illum = if let Some(v) = illum_override {
        v
    } else if let Some(v) = zrow.get("default_illum").and_then(|x| x.as_f64()) {
        v
    } else if let Some(key) = zrow.get("default_illum_from").and_then(|x| x.as_str()) {
        f64_req(constants, key)?
    } else {
        return Err("zone missing default_illum or default_illum_from".into());
    };

    let mut doc = evaluate_radiative_bc(
        zone,
        t_surf_k,
        eps,
        sigma,
        t_sky_rad,
        t_sky_ambient,
        albedo,
        solar,
        illum,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "label".into(),
            zrow.get("label").cloned().unwrap_or(json!(zone)),
        );
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_radiative_bc_file(
    catalog_path: &Path,
    zone: &str,
    t_surf_k: f64,
    illum_override: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_radiative_bc_from_catalog(&text, zone, t_surf_k, illum_override)
}

#[cfg(test)]
mod radiative_tests {
    use super::*;

    #[test]
    fn psr_no_solar() {
        let (_r, s, _n) = radiative_fluxes(70.0, 0.95, 5.67e-8, 3.0, 0.12, 1361.0, 0.0).unwrap();
        assert!(s.abs() < 1e-12);
    }

    #[test]
    fn warm_rim_radiates_more_than_psr() {
        let (r_warm, _, _) = radiative_fluxes(220.0, 0.95, 5.67e-8, 3.0, 0.12, 1361.0, 0.96).unwrap();
        let (r_cold, _, _) = radiative_fluxes(70.0, 0.95, 5.67e-8, 3.0, 0.12, 1361.0, 0.0).unwrap();
        assert!(r_warm > r_cold);
    }
}
