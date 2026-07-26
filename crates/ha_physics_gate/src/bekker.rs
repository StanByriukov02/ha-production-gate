//! Bekker pressure–sinkage (Wong §2.4.1 / ON corpus).
//!
//! p = (kc/b + k_phi) * z^n
//! z = (p / (kc/b + k_phi))^(1/n)
//!
//! Compaction resistance (uniform track pressure, Wong §2.5.1):
//! Rc = b/(n+1) * (kc/b + k_phi) * z^(n+1)
//!
//! Source: VPS ON dogfood_corpus …/onnx-op-wong-theory-ground-vehicles-2001

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const BEKKER_SCHEMA: &str = "ha_bekker_soil_eval_v1";
pub const BEKKER_ORACLE: &str = "ha_physics_gate_bekker";

#[derive(Debug, Clone, Copy)]
pub struct BekkerParams {
    pub n: f64,
    pub kc: f64,
    pub k_phi: f64,
    pub b_m: f64,
    pub p_kpa: f64,
}

fn bekker_modulus(p: BekkerParams) -> Result<f64, String> {
    if !(p.p_kpa.is_finite() && p.b_m.is_finite() && p.n.is_finite() && p.kc.is_finite() && p.k_phi.is_finite())
    {
        return Err("bekker params must be finite".into());
    }
    if p.b_m <= 0.0 {
        return Err("b_m must be > 0".into());
    }
    if p.n <= 0.0 {
        return Err("n must be > 0".into());
    }
    let modulus = p.kc / p.b_m + p.k_phi;
    if modulus <= 0.0 {
        return Err("kc/b + k_phi must be > 0".into());
    }
    Ok(modulus)
}

pub fn bekker_sinkage_m(p: BekkerParams) -> Result<f64, String> {
    let modulus = bekker_modulus(p)?;
    if p.p_kpa < 0.0 {
        return Err("p_kpa must be >= 0".into());
    }
    if p.p_kpa == 0.0 {
        return Ok(0.0);
    }
    Ok((p.p_kpa / modulus).powf(1.0 / p.n))
}

/// Inverse Bekker: p = (kc/b + k_phi) * z^n  [kPa].
pub fn bekker_pressure_kpa_from_z(p: BekkerParams, z_m: f64) -> Result<f64, String> {
    let modulus = bekker_modulus(p)?;
    if z_m < 0.0 || !z_m.is_finite() {
        return Err("z_m must be finite >= 0".into());
    }
    Ok(modulus * z_m.powf(p.n))
}

/// Janosi–Hanamoto shear (Wong): τ = (c + p tan φ)(1 − e^{−j/K})
/// c, p, τ in kPa; φ in degrees; j, K in m.
pub fn janosi_hanamoto_shear_kpa(
    c_kpa: f64,
    phi_deg: f64,
    k_m: f64,
    p_kpa: f64,
    j_m: f64,
) -> Result<f64, String> {
    for (name, v) in [
        ("c_kpa", c_kpa),
        ("phi_deg", phi_deg),
        ("k_m", k_m),
        ("p_kpa", p_kpa),
        ("j_m", j_m),
    ] {
        if !v.is_finite() {
            return Err(format!("{name} must be finite"));
        }
    }
    if k_m <= 0.0 {
        return Err("k_m must be > 0".into());
    }
    if j_m < 0.0 {
        return Err("j_m must be >= 0".into());
    }
    if p_kpa < 0.0 {
        return Err("p_kpa must be >= 0".into());
    }
    let phi = phi_deg.to_radians();
    let tau_max = c_kpa + p_kpa * phi.tan();
    if tau_max < 0.0 {
        return Err("c + p tanφ must be >= 0".into());
    }
    let factor = 1.0 - (-j_m / k_m).exp();
    Ok(tau_max * factor)
}

/// Physics thermometer without field iron: z(p) then p'(z) must close on p.
pub fn bekker_roundtrip(p: BekkerParams) -> Result<Value, String> {
    let z_m = bekker_sinkage_m(p)?;
    let p_recovered = bekker_pressure_kpa_from_z(p, z_m)?;
    let residual_kpa = (p_recovered - p.p_kpa).abs();
    let eps_kpa = 1e-6_f64.max(1e-9 * p.p_kpa.abs());
    let closed = residual_kpa <= eps_kpa;
    Ok(json!({
        "schema": "ha_bekker_roundtrip_v1",
        "oracle": BEKKER_ORACLE,
        "params": {
            "n": p.n,
            "kc": p.kc,
            "k_phi": p.k_phi,
            "b_m": p.b_m,
            "p_kpa": p.p_kpa
        },
        "sinkage_m": (z_m * 1e9).round() / 1e9,
        "sinkage_mm": ((z_m * 1000.0) * 1e6).round() / 1e6,
        "p_recovered_kpa": (p_recovered * 1e9).round() / 1e9,
        "residual_kpa": residual_kpa,
        "eps_kpa": eps_kpa,
        "physics_closure_ok": closed,
        "honesty": {
            "not_measured": true,
            "cross_oracle_not_field": true,
            "equation_identity": "p = (kc/b + k_phi) * z^n  ↔  z = (p / modulus)^(1/n)",
            "note": "PASS = Bekker identity closes in Rust; not a bevameter reading"
        }
    }))
}

/// Compaction resistance force [N] for contact width b and sinkage z (Wong §2.5.1).
/// Rc = b/(n+1) * (kc/b + k_phi) * z^(n+1)  with p in kPa → factor 1000 for N.
pub fn compaction_resistance_n(p: BekkerParams, z_m: f64) -> Result<f64, String> {
    if z_m < 0.0 || !z_m.is_finite() {
        return Err("z_m must be finite >= 0".into());
    }
    let modulus = p.kc / p.b_m + p.k_phi;
    if modulus <= 0.0 {
        return Err("kc/b + k_phi must be > 0".into());
    }
    // kPa * m^2 → N: 1000 N/kPa/m^2
    let rc_kpa_m2 = (p.b_m / (p.n + 1.0)) * modulus * z_m.powf(p.n + 1.0);
    Ok(rc_kpa_m2 * 1000.0)
}

/// Gross drawbar / thrust H = τ · A (Wong / Janosi traction).
/// τ in kPa, A in m² → H in N (×1000).
pub fn drawbar_pull_n(tau_kpa: f64, contact_area_m2: f64) -> Result<f64, String> {
    if !tau_kpa.is_finite() || !contact_area_m2.is_finite() {
        return Err("tau_kpa and contact_area_m2 must be finite".into());
    }
    if contact_area_m2 <= 0.0 {
        return Err("contact_area_m2 must be > 0".into());
    }
    if tau_kpa < 0.0 {
        return Err("tau_kpa must be >= 0".into());
    }
    Ok(tau_kpa * contact_area_m2 * 1000.0)
}

pub fn evaluate_soil_from_catalog(
    catalog_json: &str,
    soil_id: &str,
    ground_pressure_kpa: Option<f64>,
    contact_width_b_m: Option<f64>,
    contact_area_m2: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let soils = root
        .get("soils")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.missing soils object".to_string())?;
    let soil = soils
        .get(soil_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown soil_id={soil_id}"))?;
    let vehicle = root.get("vehicle").and_then(|v| v.as_object());
    let gates = root.get("gates").and_then(|v| v.as_object());

    let b = contact_width_b_m.unwrap_or_else(|| {
        vehicle
            .and_then(|v| v.get("contact_width_b_m"))
            .and_then(|v| v.as_f64())
            .unwrap_or(0.12)
    });
    let p_kpa = ground_pressure_kpa.unwrap_or_else(|| {
        vehicle
            .and_then(|v| v.get("ground_pressure_kpa"))
            .and_then(|v| v.as_f64())
            .unwrap_or(35.0)
    });
    let contact_len = vehicle
        .and_then(|v| v.get("contact_length_m"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.25);
    let area_m2 = contact_area_m2.unwrap_or_else(|| (b * contact_len).max(1e-6));
    let n = soil
        .get("n")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "soil.n required".to_string())?;
    let kc = soil
        .get("kc")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "soil.kc required".to_string())?;
    let k_phi = soil
        .get("k_phi")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "soil.k_phi required".to_string())?;
    let z_max = gates
        .and_then(|v| v.get("sinkage_mm_max_traverse"))
        .and_then(|v| v.as_f64())
        .unwrap_or(18.0);

    let params = BekkerParams {
        n,
        kc,
        k_phi,
        b_m: b,
        p_kpa,
    };
    let z_m = bekker_sinkage_m(params)?;
    let z_mm = z_m * 1000.0;
    let rc_n = compaction_resistance_n(params, z_m)?;
    let sinkage_risk = z_mm > z_max;

    let shear = soil.get("shear").and_then(|v| v.as_object());
    let shear_json = if let Some(sh) = shear {
        let c = sh.get("c_kpa").and_then(|v| v.as_f64());
        let phi = sh.get("phi_deg").and_then(|v| v.as_f64());
        let k = sh.get("K_m").and_then(|v| v.as_f64());
        let j = sh
            .get("j_m_default")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.05);
        match (c, phi, k) {
            (Some(c), Some(phi), Some(k)) => {
                let tau = janosi_hanamoto_shear_kpa(c, phi, k, p_kpa, j)?;
                let h_n = drawbar_pull_n(tau, area_m2)?;
                Some(json!({
                    "model": "janosi_hanamoto",
                    "c_kpa": c,
                    "phi_deg": phi,
                    "K_m": k,
                    "j_m": j,
                    "p_kpa": p_kpa,
                    "tau_kpa": (tau * 1e6).round() / 1e6,
                    "contact_area_m2": (area_m2 * 1e9).round() / 1e9,
                    "drawbar_pull_n": (h_n * 1e3).round() / 1e3,
                    "equation": "tau = (c + p*tan(phi))*(1 - exp(-j/K)); H = tau * A",
                    "role": sh.get("role").cloned().unwrap_or(json!("optional")),
                    "honesty": {
                        "not_measured": true,
                        "wong_section": "§2.4 shear / Janosi–Hanamoto · drawbar H=τA",
                        "optional_catalog_block": true
                    }
                }))
            }
            _ => None,
        }
    } else {
        None
    };

    let drawbar_top = shear_json
        .as_ref()
        .and_then(|s| s.get("drawbar_pull_n").cloned());

    Ok(json!({
        "schema": BEKKER_SCHEMA,
        "proof_tier": "TERRAMECH_BEKKER_ON_SLICE",
        "oracle": BEKKER_ORACLE,
        "soil_id": soil_id,
        "label": soil.get("label"),
        "params": {
            "n": n,
            "kc": kc,
            "k_phi": k_phi,
            "b_m": b,
            "p_kpa": p_kpa,
            "contact_area_m2": (area_m2 * 1e9).round() / 1e9
        },
        "sinkage_m": (z_m * 1e6).round() / 1e6,
        "sinkage_mm": (z_mm * 1e3).round() / 1e3,
        "sinkage_mm_max_traverse": z_max,
        "sinkage_risk": sinkage_risk,
        "traverse_feasible": !sinkage_risk,
        "compaction_resistance_n": (rc_n * 1e3).round() / 1e3,
        "drawbar_pull_n": drawbar_top,
        "shear": shear_json,
        "equation": root.get("equation").cloned().unwrap_or(json!(
            "p = (kc/b + k_phi) * z^n   =>   z = (p / (kc/b + k_phi))^(1/n)"
        )),
        "on_sources": root.get("on_sources").cloned().unwrap_or(json!([])),
        "honesty": {
            "not_measured": true,
            "sim_slice": true,
            "teaching_adapt_params": true,
            "on_grounded": true,
            "not_magic_constant": true,
            "python_not_oracle": true,
            "wong_section": "§2.4.1 pressure-sinkage · §2.5.1 compaction · Janosi shear · H=τA"
        }
    }))
}

pub fn evaluate_soil_file(
    catalog_path: &Path,
    soil_id: &str,
    ground_pressure_kpa: Option<f64>,
    contact_width_b_m: Option<f64>,
    contact_area_m2: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_soil_from_catalog(
        &text,
        soil_id,
        ground_pressure_kpa,
        contact_width_b_m,
        contact_area_m2,
    )
}

/// Pressure from sinkage for a catalog soil (inverse of bekker-eval z(p)).
pub fn evaluate_pressure_from_z_file(
    catalog_path: &Path,
    soil_id: &str,
    z_m: f64,
    contact_width_b_m: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    let root: Value = serde_json::from_str(&text).map_err(|e| format!("catalog JSON: {e}"))?;
    let soils = root
        .get("soils")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.missing soils object".to_string())?;
    let soil = soils
        .get(soil_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown soil_id={soil_id}"))?;
    let vehicle = root.get("vehicle").and_then(|v| v.as_object());
    let b = contact_width_b_m.unwrap_or_else(|| {
        vehicle
            .and_then(|v| v.get("contact_width_b_m"))
            .and_then(|v| v.as_f64())
            .unwrap_or(0.12)
    });
    let n = soil
        .get("n")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "soil.n required".to_string())?;
    let kc = soil
        .get("kc")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "soil.kc required".to_string())?;
    let k_phi = soil
        .get("k_phi")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "soil.k_phi required".to_string())?;
    let params = BekkerParams {
        n,
        kc,
        k_phi,
        b_m: b,
        p_kpa: 0.0,
    };
    let p_kpa = bekker_pressure_kpa_from_z(params, z_m)?;
    Ok(json!({
        "schema": "ha_bekker_pressure_from_z_v1",
        "oracle": BEKKER_ORACLE,
        "soil_id": soil_id,
        "z_m": (z_m * 1e9).round() / 1e9,
        "z_mm": ((z_m * 1000.0) * 1e6).round() / 1e6,
        "b_m": b,
        "p_kpa": (p_kpa * 1e6).round() / 1e6,
        "params": { "n": n, "kc": kc, "k_phi": k_phi, "b_m": b },
        "equation": "p = (kc/b + k_phi) * z^n",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "sim_slice": true
        }
    }))
}

#[cfg(test)]
mod bekker_tests {
    use super::*;

    #[test]
    fn firm_lab_15mm() {
        let z = bekker_sinkage_m(BekkerParams {
            n: 1.0,
            kc: 40.0,
            k_phi: 2000.0,
            b_m: 0.12,
            p_kpa: 35.0,
        })
        .unwrap();
        assert!((z * 1000.0 - 15.0).abs() < 1e-6);
    }

    #[test]
    fn soft_hostile_over_gate() {
        let z = bekker_sinkage_m(BekkerParams {
            n: 0.8,
            kc: 5.0,
            k_phi: 80.0,
            b_m: 0.12,
            p_kpa: 35.0,
        })
        .unwrap();
        assert!(z * 1000.0 > 18.0);
        assert!((z * 1000.0 - 210.679).abs() < 0.05);
    }

    #[test]
    fn roundtrip_closes_firm() {
        let p = BekkerParams {
            n: 1.0,
            kc: 40.0,
            k_phi: 2000.0,
            b_m: 0.12,
            p_kpa: 35.0,
        };
        let doc = bekker_roundtrip(p).unwrap();
        assert_eq!(doc["physics_closure_ok"], true);
        assert!(doc["residual_kpa"].as_f64().unwrap() < 1e-9);
    }

    #[test]
    fn shear_zero_at_j0() {
        let tau = janosi_hanamoto_shear_kpa(1.0, 30.0, 0.02, 35.0, 0.0).unwrap();
        assert!(tau.abs() < 1e-12);
    }

    #[test]
    fn shear_approaches_max() {
        let tau = janosi_hanamoto_shear_kpa(0.0, 45.0, 0.01, 10.0, 1.0).unwrap();
        // tan(45°)=1 → tau_max=10; j>>K → ~10
        assert!((tau - 10.0).abs() < 0.01);
    }

    #[test]
    fn drawbar_scales_with_area() {
        let h1 = drawbar_pull_n(10.0, 0.03).unwrap();
        let h2 = drawbar_pull_n(10.0, 0.06).unwrap();
        assert!((h1 - 300.0).abs() < 1e-9);
        assert!((h2 - 2.0 * h1).abs() < 1e-9);
    }
}
