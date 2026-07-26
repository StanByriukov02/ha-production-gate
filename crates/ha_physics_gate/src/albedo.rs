//! Albedo dose split + Matthia shield paradox (SELINE surrogate).
//!
//! f_alb = min(ceiling, f0 * site_scale * (1 + (m_f-1)*gauss(g)))
//! total = anchor * (1 + (m_t-1)*gauss(g))
//! albedo = total * f_alb; incident = total - albedo
//! see = see_base * (1 + gain * max(0, f_alb/f_base - 1))
//!
//! Not CREME FEM. Not MEASURED. Python glue only.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const ALBEDO_SCHEMA: &str = "ha_albedo_dose_eval_v1";
pub const ALBEDO_ORACLE: &str = "ha_physics_gate_albedo_dose";

fn gauss_bump(g: f64, peak: f64, sigma: f64, peak_mult: f64) -> Result<f64, String> {
    if !(g.is_finite() && g >= 0.0) {
        return Err("shield_g_cm2 must be finite >= 0".into());
    }
    if !(peak.is_finite() && peak > 0.0) {
        return Err("peak_areal must be finite > 0".into());
    }
    if !(sigma.is_finite() && sigma > 0.0) {
        return Err("sigma must be finite > 0".into());
    }
    if !(peak_mult.is_finite() && peak_mult >= 1.0) {
        return Err("peak multiplier must be finite >= 1".into());
    }
    let x = (g - peak) / sigma;
    let bump = (peak_mult - 1.0) * (-0.5 * x * x).exp();
    Ok(1.0 + bump)
}

pub fn evaluate_albedo_dose(
    site_class: &str,
    shield_g_cm2: f64,
    dose_anchor_gy: f64,
    f0: f64,
    site_scale: f64,
    fraction_ceiling: f64,
    peak_g: f64,
    frac_peak_mult: f64,
    total_peak_mult: f64,
    sigma: f64,
    see_base: f64,
    see_gain: f64,
) -> Result<Value, String> {
    if !(dose_anchor_gy.is_finite() && dose_anchor_gy >= 0.0) {
        return Err("dose_anchor_gy must be finite >= 0".into());
    }
    if !(f0.is_finite() && (0.0..=1.0).contains(&f0)) {
        return Err("f0 must be in [0,1]".into());
    }
    if !(site_scale.is_finite() && site_scale > 0.0) {
        return Err("site_scale must be finite > 0".into());
    }
    if !(fraction_ceiling.is_finite() && fraction_ceiling > 0.0) {
        return Err("fraction_ceiling must be finite > 0".into());
    }
    if !(see_base.is_finite() && see_base >= 0.0) {
        return Err("see_base must be finite >= 0".into());
    }
    if !(see_gain.is_finite() && see_gain >= 0.0) {
        return Err("see_gain must be finite >= 0".into());
    }

    let f_base = f0 * site_scale;
    let frac_mult = gauss_bump(shield_g_cm2, peak_g, sigma, frac_peak_mult)?;
    let total_mult = gauss_bump(shield_g_cm2, peak_g, sigma, total_peak_mult)?;
    let f_eff = (f_base * frac_mult).min(fraction_ceiling);
    let total = dose_anchor_gy * total_mult;
    let albedo = total * f_eff;
    let incident = total - albedo;
    let see_rate = see_base * (1.0 + see_gain * (f_eff / f_base.max(1e-12) - 1.0).max(0.0));

    Ok(json!({
        "schema": ALBEDO_SCHEMA,
        "oracle": ALBEDO_ORACLE,
        "site_class": site_class,
        "shield_g_cm2": shield_g_cm2,
        "dose_anchor_gy": dose_anchor_gy,
        "albedo_fraction_base": (f_base * 1e12).round() / 1e12,
        "albedo_fraction": (f_eff * 1e12).round() / 1e12,
        "shield_paradox_multiplier": (total_mult * 1e12).round() / 1e12,
        "fraction_paradox_multiplier": (frac_mult * 1e12).round() / 1e12,
        "total_dose_gy": (total * 1e12).round() / 1e12,
        "albedo_dose_gy": (albedo * 1e12).round() / 1e12,
        "incident_dose_gy": (incident * 1e12).round() / 1e12,
        "see_rate_per_year": (see_rate * 1e12).round() / 1e12,
        "equation": "total=anchor*gauss_total; f_alb=min(ceil,f0*site*gauss_f); albedo=total*f_alb",
        "honesty": {
            "not_measured": true,
            "not_creme_fem": true,
            "python_not_oracle": true,
            "teaching_seline_surrogate": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("missing required {key}"))
}

pub fn evaluate_albedo_dose_from_catalog(
    catalog_json: &str,
    site_class: &str,
    shield_g_cm2: f64,
    dose_anchor_gy: f64,
    see_base_override: Option<f64>,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let f0 = root
        .get("f0")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "catalog.f0 required".to_string())?;
    let ceiling = root
        .get("fraction_ceiling")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "catalog.fraction_ceiling required".to_string())?;
    let paradox = root
        .get("shield_paradox")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.shield_paradox required".to_string())?;
    let peak_g = f64_req(paradox, "peak_areal_g_cm2")?;
    let frac_peak = f64_req(paradox, "fraction_multiplier_at_peak")?;
    let tot_peak = f64_req(paradox, "total_dose_multiplier_at_peak")?;
    let sigma = f64_req(paradox, "sigma_g_cm2")?;
    let sites = root
        .get("site_class_modifiers")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.site_class_modifiers required".to_string())?;
    let site = sites
        .get(site_class)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown site_class={site_class}"))?;
    let site_scale = f64_req(site, "f_albedo_scale")?;
    let see = root
        .get("see_albedo_coupling")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.see_albedo_coupling required".to_string())?;
    let see_base = see_base_override.unwrap_or(f64_req(see, "base_see_per_yr")?);
    let see_gain = f64_req(see, "albedo_neutron_gain")?;

    let mut doc = evaluate_albedo_dose(
        site_class,
        shield_g_cm2,
        dose_anchor_gy,
        f0,
        site_scale,
        ceiling,
        peak_g,
        frac_peak,
        tot_peak,
        sigma,
        see_base,
        see_gain,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
        obj.insert(
            "l0_band".into(),
            root.get("l0_band").cloned().unwrap_or(json!([0.25, 0.35])),
        );
    }
    Ok(doc)
}

pub fn evaluate_albedo_dose_file(
    catalog_path: &Path,
    site_class: &str,
    shield_g_cm2: f64,
    dose_anchor_gy: f64,
    see_base_override: Option<f64>,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_albedo_dose_from_catalog(
        &text,
        site_class,
        shield_g_cm2,
        dose_anchor_gy,
        see_base_override,
    )
}

#[cfg(test)]
mod albedo_tests {
    use super::*;

    #[test]
    fn paradox_peak_raises_total() {
        let bare = evaluate_albedo_dose(
            "highland_regolith",
            0.0,
            0.55,
            0.3,
            1.0,
            0.65,
            90.0,
            1.67,
            1.12,
            40.0,
            0.12,
            0.85,
        )
        .unwrap();
        let peak = evaluate_albedo_dose(
            "highland_regolith",
            90.0,
            0.55,
            0.3,
            1.0,
            0.65,
            90.0,
            1.67,
            1.12,
            40.0,
            0.12,
            0.85,
        )
        .unwrap();
        assert!(peak["total_dose_gy"].as_f64().unwrap() > bare["total_dose_gy"].as_f64().unwrap());
    }

    #[test]
    fn sites_diverge() {
        let hi = evaluate_albedo_dose(
            "highland_regolith",
            0.0,
            0.55,
            0.3,
            1.0,
            0.65,
            90.0,
            1.67,
            1.12,
            40.0,
            0.12,
            0.85,
        )
        .unwrap();
        let mare = evaluate_albedo_dose(
            "mare_regolith",
            0.0,
            0.55,
            0.3,
            0.92,
            0.65,
            90.0,
            1.67,
            1.12,
            40.0,
            0.12,
            0.85,
        )
        .unwrap();
        assert!(hi["albedo_fraction"].as_f64().unwrap() > mare["albedo_fraction"].as_f64().unwrap());
    }
}
