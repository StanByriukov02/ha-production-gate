//! DC motor linear τ–ω + gear ratio with efficiency (teaching).
//!
//! τ_m(ω) = τ_stall · (1 − ω/ω_nl)   for 0 ≤ ω ≤ ω_nl
//! τ_out = τ_m · n · η
//! ω_out = ω / n
//!
//! Not FOC. Not saturation. Not dyno MEASURED.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const MOTOR_SCHEMA: &str = "ha_dc_motor_gear_eval_v1";
pub const MOTOR_ORACLE: &str = "ha_physics_gate_dc_motor_gear";

pub fn motor_tau_nm(tau_stall: f64, omega_nl: f64, omega: f64) -> Result<f64, String> {
    if !(tau_stall.is_finite() && tau_stall > 0.0) {
        return Err("tau_stall must be finite > 0".into());
    }
    if !(omega_nl.is_finite() && omega_nl > 0.0) {
        return Err("omega_nl must be finite > 0".into());
    }
    if !(omega.is_finite() && omega >= 0.0) {
        return Err("omega must be finite >= 0".into());
    }
    if omega > omega_nl + 1e-12 {
        return Err("omega exceeds no-load omega_nl".into());
    }
    Ok(tau_stall * (1.0 - omega / omega_nl))
}

pub fn gear_out(tau_m: f64, omega: f64, n: f64, eta: f64) -> Result<(f64, f64, f64), String> {
    if !(n.is_finite() && n > 0.0) {
        return Err("gear_ratio must be finite > 0".into());
    }
    if !(eta.is_finite() && (0.0..=1.0).contains(&eta)) {
        return Err("eta must be in [0,1]".into());
    }
    if !(tau_m.is_finite() && tau_m >= 0.0) {
        return Err("tau_m must be finite >= 0".into());
    }
    let tau_out = tau_m * n * eta;
    let omega_out = omega / n;
    let p_out = tau_out * omega_out;
    Ok((tau_out, omega_out, p_out))
}

pub fn evaluate_dc_motor_gear(
    pack_id: &str,
    tau_stall: f64,
    omega_nl: f64,
    gear_ratio: f64,
    eta: f64,
    omega: f64,
) -> Result<Value, String> {
    let tau_m = motor_tau_nm(tau_stall, omega_nl, omega)?;
    let (tau_out, omega_out, p_out) = gear_out(tau_m, omega, gear_ratio, eta)?;
    let p_motor = tau_m * omega;
    Ok(json!({
        "schema": MOTOR_SCHEMA,
        "oracle": MOTOR_ORACLE,
        "pack_id": pack_id,
        "omega_rad_s": omega,
        "tau_stall_nm": tau_stall,
        "omega_nl_rad_s": omega_nl,
        "gear_ratio": gear_ratio,
        "eta": eta,
        "tau_motor_nm": (tau_m * 1e12).round() / 1e12,
        "tau_out_nm": (tau_out * 1e12).round() / 1e12,
        "omega_out_rad_s": (omega_out * 1e12).round() / 1e12,
        "p_motor_w": (p_motor * 1e12).round() / 1e12,
        "p_out_w": (p_out * 1e12).round() / 1e12,
        "equation": "tau_m=tau_stall*(1-omega/omega_nl); tau_out=tau_m*n*eta",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_foc_dyno": true,
            "teaching_dc_gear": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_dc_motor_gear_from_catalog(
    catalog_json: &str,
    pack_id: &str,
    omega: Option<f64>,
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
    let w = omega.unwrap_or(f64_req(defaults, "omega_rad_s")?);
    let mut doc = evaluate_dc_motor_gear(
        pack_id,
        f64_req(pack, "tau_stall_nm")?,
        f64_req(pack, "omega_nl_rad_s")?,
        f64_req(pack, "gear_ratio")?,
        f64_req(pack, "eta")?,
        w,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_dc_motor_gear_file(
    catalog_path: &Path,
    pack_id: &str,
    omega: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_dc_motor_gear_from_catalog(&text, pack_id, omega)
}

#[cfg(test)]
mod dc_motor_tests {
    use super::*;

    #[test]
    fn higher_eta_higher_tau_out() {
        let (hi, _, _) = gear_out(1.0, 100.0, 20.0, 0.9).unwrap();
        let (lo, _, _) = gear_out(1.0, 100.0, 20.0, 0.5).unwrap();
        assert!(hi > lo);
    }

    #[test]
    fn faster_lower_tau() {
        let stall = motor_tau_nm(2.0, 300.0, 0.0).unwrap();
        let mid = motor_tau_nm(2.0, 300.0, 150.0).unwrap();
        assert!(stall > mid);
    }
}
