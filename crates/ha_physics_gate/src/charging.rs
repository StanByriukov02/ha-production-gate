//! Lunar surface charging class + φ_s (Zheng/Stubbs cited anchors).
//!
//! Piecewise on illum_frac + SEP/magnetotail flags — not CCMC live solver.
//! Not MEASURED spacecraft potential.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const CHARGING_SCHEMA: &str = "ha_surface_charging_eval_v1";
pub const CHARGING_ORACLE: &str = "ha_physics_gate_surface_charging";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChargingClass {
    DaysideLowPos,
    TerminatorShadow,
    NightsideHighNeg,
    NightsideExtremeNeg,
}

impl ChargingClass {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::DaysideLowPos => "DAYSIDE_LOW_POS",
            Self::TerminatorShadow => "TERMINATOR_SHADOW",
            Self::NightsideHighNeg => "NIGHTSIDE_HIGH_NEG",
            Self::NightsideExtremeNeg => "NIGHTSIDE_EXTREME_NEG",
        }
    }
}

pub fn classify_charging(
    illum_frac: f64,
    sep_active: bool,
    in_magnetotail: bool,
    dayside_illum_min: f64,
    terminator_illum_min: f64,
    dayside_v: f64,
    shadow_v: f64,
    nightside_floor_v: f64,
    nightside_extreme_v: f64,
) -> Result<(ChargingClass, f64), String> {
    if !(illum_frac.is_finite() && (0.0..=1.0).contains(&illum_frac)) {
        return Err("illum_frac must be finite in [0,1]".into());
    }
    if !(dayside_illum_min.is_finite()
        && terminator_illum_min.is_finite()
        && dayside_illum_min > terminator_illum_min
        && terminator_illum_min >= 0.0
        && dayside_illum_min <= 1.0)
    {
        return Err("illum thresholds invalid".into());
    }
    for (name, v) in [
        ("dayside_v", dayside_v),
        ("shadow_v", shadow_v),
        ("nightside_floor_v", nightside_floor_v),
        ("nightside_extreme_v", nightside_extreme_v),
    ] {
        if !v.is_finite() {
            return Err(format!("{name} must be finite"));
        }
    }

    if illum_frac >= dayside_illum_min {
        Ok((ChargingClass::DaysideLowPos, dayside_v))
    } else if illum_frac >= terminator_illum_min {
        Ok((ChargingClass::TerminatorShadow, shadow_v))
    } else if sep_active || in_magnetotail {
        Ok((ChargingClass::NightsideExtremeNeg, nightside_extreme_v))
    } else {
        Ok((ChargingClass::NightsideHighNeg, nightside_floor_v))
    }
}

pub fn evaluate_surface_charging(
    illum_frac: f64,
    sep_active: bool,
    in_magnetotail: bool,
    dayside_illum_min: f64,
    terminator_illum_min: f64,
    dayside_v: f64,
    shadow_v: f64,
    nightside_floor_v: f64,
    nightside_extreme_v: f64,
) -> Result<Value, String> {
    let (cls, phi) = classify_charging(
        illum_frac,
        sep_active,
        in_magnetotail,
        dayside_illum_min,
        terminator_illum_min,
        dayside_v,
        shadow_v,
        nightside_floor_v,
        nightside_extreme_v,
    )?;
    Ok(json!({
        "schema": CHARGING_SCHEMA,
        "oracle": CHARGING_ORACLE,
        "illum_frac": (illum_frac * 1e9).round() / 1e9,
        "sep_active": sep_active,
        "in_magnetotail": in_magnetotail,
        "charging_class": cls.as_str(),
        "surface_potential_v": phi,
        "equation": "piecewise illum/SEP/magnetotail → class+φ_s",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_ccmc_live_solver": true,
            "cited_zheng_stubbs_anchors": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_surface_charging_from_catalog(
    catalog_json: &str,
    illum_frac: f64,
    sep_active: bool,
    in_magnetotail: bool,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let thr = root
        .get("thresholds")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.thresholds required".to_string())?;
    let phi = root
        .get("phi_v")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.phi_v required".to_string())?;
    let mut doc = evaluate_surface_charging(
        illum_frac,
        sep_active,
        in_magnetotail,
        f64_req(thr, "dayside_illum_min")?,
        f64_req(thr, "terminator_illum_min")?,
        f64_req(phi, "dayside_v")?,
        f64_req(phi, "shadow_v")?,
        f64_req(phi, "nightside_floor_v")?,
        f64_req(phi, "nightside_extreme_v")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_surface_charging_file(
    catalog_path: &Path,
    illum_frac: f64,
    sep_active: bool,
    in_magnetotail: bool,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_surface_charging_from_catalog(&text, illum_frac, sep_active, in_magnetotail)
}

#[cfg(test)]
mod charging_tests {
    use super::*;

    #[test]
    fn dayside_vs_night_sign() {
        let (d_cls, d_phi) =
            classify_charging(0.95, false, false, 0.85, 0.05, 3.0, -48.0, -100.0, -1000.0)
                .unwrap();
        let (n_cls, n_phi) =
            classify_charging(0.0, false, false, 0.85, 0.05, 3.0, -48.0, -100.0, -1000.0).unwrap();
        assert_eq!(d_cls, ChargingClass::DaysideLowPos);
        assert_eq!(n_cls, ChargingClass::NightsideHighNeg);
        assert!(d_phi > 0.0 && n_phi < 0.0);
    }

    #[test]
    fn sep_extreme() {
        let (cls, phi) =
            classify_charging(0.0, true, false, 0.85, 0.05, 3.0, -48.0, -100.0, -1000.0).unwrap();
        assert_eq!(cls, ChargingClass::NightsideExtremeNeg);
        assert_eq!(phi, -1000.0);
    }
}
