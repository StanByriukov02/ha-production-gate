//! Dust ingress rate + accumulation (Stubbs/Colwell/Benaroya ADAPT).
//!
//! rate = base(zone) * seal * gap * ES * (1 - mit_red)
//! gap  = 1 + min(0.5, joint_gap_mm/2)
//! acc  = min(sat, prev + rate * n_sols)
//! wear = min(cap, 1 + coeff * acc)
//!
//! Not Shackleton flux meter. Not MEASURED.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const DUST_SCHEMA: &str = "ha_dust_ingress_eval_v1";
pub const DUST_ORACLE: &str = "ha_physics_gate_dust_ingress";

fn hazard_class(rate: f64, med: f64, high: f64, sev: f64) -> &'static str {
    if rate >= sev {
        "SEVERE"
    } else if rate >= high {
        "HIGH"
    } else if rate >= med {
        "MEDIUM"
    } else {
        "LOW"
    }
}

pub fn evaluate_dust_ingress(
    zone: &str,
    seal: &str,
    base_rate: f64,
    es: f64,
    seal_scale: f64,
    max_mit_red: f64,
    mitigation_duty: f64,
    joint_gap_mm: f64,
    n_sols: f64,
    prev_g_m2: f64,
    sat_g_m2: f64,
    abrasion_coeff: f64,
    max_stress: f64,
    thr_med: f64,
    thr_high: f64,
    thr_sev: f64,
    loft_km: f64,
) -> Result<Value, String> {
    if !(base_rate.is_finite() && base_rate >= 0.0) {
        return Err("base_rate must be finite >= 0".into());
    }
    if !(es.is_finite() && es >= 0.0) {
        return Err("electrostatic_index must be finite >= 0".into());
    }
    if !(seal_scale.is_finite() && seal_scale >= 0.0) {
        return Err("seal_scale must be finite >= 0".into());
    }
    if !(max_mit_red.is_finite() && (0.0..=1.0).contains(&max_mit_red)) {
        return Err("max_mit_red must be in [0,1]".into());
    }
    if !(mitigation_duty.is_finite() && (0.0..=1.0).contains(&mitigation_duty)) {
        return Err("mitigation_duty must be in [0,1]".into());
    }
    if !(joint_gap_mm.is_finite() && joint_gap_mm >= 0.0) {
        return Err("joint_gap_mm must be finite >= 0".into());
    }
    if !(n_sols.is_finite() && n_sols >= 0.0) {
        return Err("n_sols must be finite >= 0".into());
    }
    if !(prev_g_m2.is_finite() && prev_g_m2 >= 0.0) {
        return Err("prev accumulation must be finite >= 0".into());
    }
    if !(sat_g_m2.is_finite() && sat_g_m2 > 0.0) {
        return Err("saturation must be finite > 0".into());
    }

    let mit_red = (mitigation_duty * max_mit_red).clamp(0.0, max_mit_red);
    let gap_scale = 1.0 + (joint_gap_mm / 2.0).min(0.5);
    let rate = base_rate * seal_scale * gap_scale * es * (1.0 - mit_red);
    let acc = (prev_g_m2 + rate * n_sols).min(sat_g_m2);
    let wear = (1.0 + abrasion_coeff * acc).min(max_stress);
    let haz = hazard_class(rate, thr_med, thr_high, thr_sev);

    Ok(json!({
        "schema": DUST_SCHEMA,
        "oracle": DUST_ORACLE,
        "zone": zone,
        "seal_class": seal,
        "base_rate_g_m2_per_sol": base_rate,
        "effective_rate_g_m2_per_sol": (rate * 1e9).round() / 1e9,
        "ingress_hazard_class": haz,
        "electrostatic_index": es,
        "seal_scale": seal_scale,
        "gap_scale": (gap_scale * 1e9).round() / 1e9,
        "mitigation_duty": mitigation_duty,
        "mitigation_reduction": (mit_red * 1e9).round() / 1e9,
        "joint_gap_mm": joint_gap_mm,
        "n_sols": n_sols,
        "prev_accumulation_g_m2": prev_g_m2,
        "accumulation_g_m2": (acc * 1e9).round() / 1e9,
        "saturated": acc >= sat_g_m2 - 1e-12,
        "saturation_g_m2": sat_g_m2,
        "stress_index_multiplier": (wear * 1e9).round() / 1e9,
        "loft_altitude_km": loft_km,
        "equation": "rate=base*seal*gap*ES*(1-mit); acc=min(sat,prev+rate*n)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "adapt_not_flux_meter": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("missing required {key}"))
}

pub fn evaluate_dust_ingress_from_catalog(
    catalog_json: &str,
    zone: &str,
    seal: &str,
    mitigation_duty: f64,
    joint_gap_mm: f64,
    n_sols: f64,
    prev_g_m2: f64,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let zones = root
        .get("zones")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.zones required".to_string())?;
    let zrow = zones
        .get(zone)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown zone={zone}"))?;
    let seals = root
        .get("seal_classes")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.seal_classes required".to_string())?;
    let srow = seals
        .get(seal)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown seal={seal}"))?;
    let mit = root
        .get("mitigation")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.mitigation required".to_string())?;
    let wear = root
        .get("wear_coupling")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.wear_coupling required".to_string())?;
    let thr = root
        .get("hazard_thresholds_g_m2_per_sol")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.hazard_thresholds required".to_string())?;

    let base = f64_req(zrow, "base_rate_g_m2_per_sol")?;
    let es = f64_req(zrow, "electrostatic_index")?;
    let seal_scale = f64_req(srow, "ingress_scale")?;
    let max_red = f64_req(mit, "wiper_magnet_max_reduction")?;
    let sat = f64_req(wear, "accumulation_saturation_g_m2")?;
    let coeff = f64_req(wear, "abrasion_coeff_per_g_m2")?;
    let cap = f64_req(wear, "max_stress_mult")?;
    let thr_med = f64_req(thr, "MEDIUM")?;
    let thr_high = f64_req(thr, "HIGH")?;
    let thr_sev = f64_req(thr, "SEVERE")?;
    let loft = root
        .get("loft_altitude_km")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "loft_altitude_km required".to_string())?;

    let mut doc = evaluate_dust_ingress(
        zone,
        seal,
        base,
        es,
        seal_scale,
        max_red,
        mitigation_duty,
        joint_gap_mm,
        n_sols,
        prev_g_m2,
        sat,
        coeff,
        cap,
        thr_med,
        thr_high,
        thr_sev,
        loft,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_dust_ingress_file(
    catalog_path: &Path,
    zone: &str,
    seal: &str,
    mitigation_duty: f64,
    joint_gap_mm: f64,
    n_sols: f64,
    prev_g_m2: f64,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_dust_ingress_from_catalog(
        &text,
        zone,
        seal,
        mitigation_duty,
        joint_gap_mm,
        n_sols,
        prev_g_m2,
    )
}

#[cfg(test)]
mod dust_tests {
    use super::*;

    #[test]
    fn massif_louder_than_psr() {
        let m = evaluate_dust_ingress(
            "massif_traverse",
            "B5",
            0.12,
            0.95,
            1.0,
            0.65,
            0.0,
            0.5,
            1.0,
            0.0,
            2.0,
            0.05,
            1.35,
            0.06,
            0.09,
            0.12,
            100.0,
        )
        .unwrap();
        let p = evaluate_dust_ingress(
            "psr_floor",
            "B5",
            0.02,
            0.45,
            1.0,
            0.65,
            0.0,
            0.5,
            1.0,
            0.0,
            2.0,
            0.05,
            1.35,
            0.06,
            0.09,
            0.12,
            100.0,
        )
        .unwrap();
        assert!(
            m["effective_rate_g_m2_per_sol"].as_f64().unwrap()
                > p["effective_rate_g_m2_per_sol"].as_f64().unwrap() * 2.0
        );
    }

    #[test]
    fn saturation_caps() {
        let d = evaluate_dust_ingress(
            "massif_traverse",
            "B5",
            0.12,
            0.95,
            1.0,
            0.65,
            0.0,
            0.5,
            1000.0,
            0.0,
            2.0,
            0.05,
            1.35,
            0.06,
            0.09,
            0.12,
            100.0,
        )
        .unwrap();
        assert!((d["accumulation_g_m2"].as_f64().unwrap() - 2.0).abs() < 1e-9);
        assert!(d["saturated"].as_bool().unwrap());
    }
}
