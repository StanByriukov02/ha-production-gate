//! H6 Physics gate — digit advises; physics/analog passes current.
//! Apoptosis — accumulated lie irreversibly kills trust (soft bit toward silicon).
//! Bekker terramech (Wong §2.4.1) — ON-grounded sinkage oracle.
//! Radiation dose-rate window (U4 M3) — teaching PROXY class oracle.
//! Regolith k(T) (Sakatani/Heiken + Woods cryo) — U4 M1 thermal oracle.
//! Vacuum radiative BC (Stefan–Boltzmann + solar) — U4 surface driver.
//! Albedo dose + Matthia paradox (SELINE surrogate).
//! Dust ingress Stubbs/Colwell/Benaroya ADAPT.
//! Li q_c(h) lunar-g bearing adjunct.
//! Surface charging Zheng/Stubbs class anchors.
//! Coulomb loft Stubbs fountain teaching.
//! Mohr–Coulomb infinite slope FS.
//! Beer–Lambert optics dust τ.
//! Soiling thermal BC shift.
//! Rigid ballistic hop (Newton teaching).
//! Multi-pass rut z_N=z1·N^α on Bekker virgin.
//! Janosi–Hanamoto τ(j) full curve.
//! Atmospheric quadratic drag.
//! Battery Peukert + OCV–SOC.
//! Acoustic / seismic wave speeds.
//! ISRU Arrhenius sinter.
//! Materials Hooke + CTE.
//! Orbital vis-viva / Kepler period.
//! DC motor linear τ–ω + gear η.
//! Wind load · Basquin fatigue · eclipse umbra · joint friction · solar pressure.
//! Free-mol drag · TID damage · Terzaghi · trapped belt · Fourier flux.

mod acoustic;
mod albedo;
mod atm_drag;
mod battery;
mod bekker;
mod charging;
mod coulomb_loft;
mod dc_motor;
mod dust;
mod eclipse_umbra;
mod fatigue_sn;
mod fourier_flux;
mod free_mol_drag;
mod isru_sinter;
mod janosi_curve;
mod joint_friction;
mod li_qc;
mod materials;
mod mohr_slope;
mod multipass;
mod optics_tau;
mod orbital;
mod rad_damage_tid;
mod radiation;
mod radiative;
mod rigid_hop;
mod soiling;
mod solar_pressure;
mod terzaghi_bearing;
mod thermal;
mod thermal_column;
mod trapped_belt;
mod wind_load;

pub use acoustic::{
    evaluate_acoustic_wave, evaluate_acoustic_wave_file, evaluate_acoustic_wave_from_catalog, wave_speeds,
    ACOUSTIC_ORACLE, ACOUSTIC_SCHEMA,
};
pub use albedo::{
    evaluate_albedo_dose, evaluate_albedo_dose_file, evaluate_albedo_dose_from_catalog, ALBEDO_ORACLE,
    ALBEDO_SCHEMA,
};
pub use atm_drag::{
    atm_drag, evaluate_atm_drag, evaluate_atm_drag_file, evaluate_atm_drag_from_catalog, DRAG_ORACLE,
    DRAG_SCHEMA,
};
pub use battery::{
    evaluate_battery_peukert, evaluate_battery_peukert_file, evaluate_battery_peukert_from_catalog,
    ocv_v, peukert_time_h, BATTERY_ORACLE, BATTERY_SCHEMA,
};
pub use bekker::{
    bekker_pressure_kpa_from_z, bekker_roundtrip, bekker_sinkage_m, compaction_resistance_n,
    drawbar_pull_n, evaluate_pressure_from_z_file, evaluate_soil_file, evaluate_soil_from_catalog,
    janosi_hanamoto_shear_kpa, BekkerParams, BEKKER_ORACLE, BEKKER_SCHEMA,
};
pub use dust::{
    evaluate_dust_ingress, evaluate_dust_ingress_file, evaluate_dust_ingress_from_catalog, DUST_ORACLE,
    DUST_SCHEMA,
};
pub use charging::{
    classify_charging, evaluate_surface_charging, evaluate_surface_charging_file,
    evaluate_surface_charging_from_catalog, ChargingClass, CHARGING_ORACLE, CHARGING_SCHEMA,
};
pub use coulomb_loft::{
    evaluate_coulomb_loft, evaluate_coulomb_loft_file, evaluate_coulomb_loft_from_catalog, loft_ratio,
    LOFT_ORACLE, LOFT_SCHEMA,
};
pub use dc_motor::{
    evaluate_dc_motor_gear, evaluate_dc_motor_gear_file, evaluate_dc_motor_gear_from_catalog, gear_out,
    motor_tau_nm, MOTOR_ORACLE, MOTOR_SCHEMA,
};
pub use eclipse_umbra::{
    eclipse_fraction, evaluate_eclipse_umbra, evaluate_eclipse_umbra_file,
    evaluate_eclipse_umbra_from_catalog, ECLIPSE_ORACLE, ECLIPSE_SCHEMA,
};
pub use fatigue_sn::{
    basquin_n_f, evaluate_fatigue_sn, evaluate_fatigue_sn_file, evaluate_fatigue_sn_from_catalog,
    FATIGUE_ORACLE, FATIGUE_SCHEMA,
};
pub use joint_friction::{
    evaluate_joint_friction, evaluate_joint_friction_file, evaluate_joint_friction_from_catalog,
    joint_friction, JOINT_ORACLE, JOINT_SCHEMA,
};
pub use materials::{
    cte_delta_l, evaluate_materials_hooke, evaluate_materials_hooke_file,
    evaluate_materials_hooke_from_catalog, hooke_sigma, MATERIALS_ORACLE, MATERIALS_SCHEMA,
};
pub use mohr_slope::{
    evaluate_mohr_slope, evaluate_mohr_slope_file, evaluate_mohr_slope_from_catalog, factor_of_safety,
    SLOPE_ORACLE, SLOPE_SCHEMA,
};
pub use isru_sinter::{
    arrhenius_rate, evaluate_isru_sinter, evaluate_isru_sinter_file, evaluate_isru_sinter_from_catalog,
    SINTER_ORACLE, SINTER_SCHEMA,
};
pub use janosi_curve::{
    evaluate_janosi_curve, evaluate_janosi_curve_file, evaluate_janosi_curve_from_catalog, janosi_curve,
    JANOSI_CURVE_ORACLE, JANOSI_CURVE_SCHEMA,
};
pub use multipass::{
    evaluate_multipass_rut, evaluate_multipass_rut_file, evaluate_multipass_rut_from_catalog,
    multipass_rut, MULTIPASS_ORACLE, MULTIPASS_SCHEMA,
};
pub use optics_tau::{
    evaluate_optics_tau, evaluate_optics_tau_file, evaluate_optics_tau_from_catalog, optical_depth,
    OPTICS_ORACLE, OPTICS_SCHEMA,
};
pub use orbital::{
    evaluate_orbital_visviva, evaluate_orbital_visviva_file, evaluate_orbital_visviva_from_catalog,
    kepler_period_s, vis_viva_v, ORBIT_ORACLE, ORBIT_SCHEMA,
};
pub use rigid_hop::{
    ballistic_hop, evaluate_rigid_hop, evaluate_rigid_hop_file, evaluate_rigid_hop_from_catalog,
    HOP_ORACLE, HOP_SCHEMA,
};
pub use soiling::{
    evaluate_soiling_bc, evaluate_soiling_bc_file, evaluate_soiling_bc_from_catalog, soiling_bc,
    SOILING_ORACLE, SOILING_SCHEMA,
};
pub use solar_pressure::{
    evaluate_solar_pressure, evaluate_solar_pressure_file, evaluate_solar_pressure_from_catalog,
    solar_pressure_force, SRP_ORACLE, SRP_SCHEMA,
};
pub use wind_load::{
    evaluate_wind_load, evaluate_wind_load_file, evaluate_wind_load_from_catalog, wind_load, WIND_ORACLE,
    WIND_SCHEMA,
};
pub use free_mol_drag::{
    evaluate_free_mol_drag, evaluate_free_mol_drag_file, evaluate_free_mol_drag_from_catalog, free_mol_drag,
    FMD_ORACLE, FMD_SCHEMA,
};
pub use fourier_flux::{
    evaluate_fourier_flux, evaluate_fourier_flux_file, evaluate_fourier_flux_from_catalog, fourier_q,
    FOURIER_ORACLE, FOURIER_SCHEMA,
};
pub use rad_damage_tid::{
    evaluate_rad_damage_tid, evaluate_rad_damage_tid_file, evaluate_rad_damage_tid_from_catalog, tid_accumulate,
    TID_ORACLE, TID_SCHEMA,
};
pub use terzaghi_bearing::{
    evaluate_terzaghi_bearing, evaluate_terzaghi_bearing_file, evaluate_terzaghi_bearing_from_catalog,
    terzaghi_q_ult, TERZ_ORACLE, TERZ_SCHEMA,
};
pub use trapped_belt::{
    belt_dose, evaluate_trapped_belt, evaluate_trapped_belt_file, evaluate_trapped_belt_from_catalog,
    BELT_ORACLE, BELT_SCHEMA,
};
pub use li_qc::{
    evaluate_li_qc, evaluate_li_qc_file, evaluate_li_qc_from_catalog, q_c_kpa, LI_QC_ORACLE, LI_QC_SCHEMA,
};
pub use radiation::{
    clamp_flare_scale, dose_rate_gy_per_h, evaluate_radiation_rate, evaluate_radiation_rate_file,
    evaluate_radiation_rate_from_catalog, window_dose_gy, window_see_events, HOURS_PER_YEAR,
    RADIATION_ORACLE, RADIATION_SCHEMA,
};
pub use radiative::{
    evaluate_radiative_bc, evaluate_radiative_bc_file, evaluate_radiative_bc_from_catalog,
    radiative_fluxes, RADIATIVE_ORACLE, RADIATIVE_SCHEMA,
};
pub use thermal::{
    apply_cryo_scale, evaluate_thermal_k, evaluate_thermal_k_file, evaluate_thermal_k_from_catalog,
    k_w_mk, THERMAL_ORACLE, THERMAL_SCHEMA,
};
pub use thermal_column::{
    evaluate_column_step_file, evaluate_column_step_from_catalog, step_column_implicit,
    COLUMN_ORACLE, COLUMN_SCHEMA,
};

use serde_json::{json, Value};

pub const SCHEMA: &str = "physics_gate_v1";
pub const DEFAULT_LIE_THRESHOLD: f64 = 3.0;
pub const DEFAULT_ABS_TOL: f64 = 1e-9;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DigitAdvise {
    Allow,
    Deny,
}

impl DigitAdvise {
    pub fn parse(s: &str) -> Result<Self, String> {
        match s.trim().to_ascii_uppercase().as_str() {
            "ALLOW" => Ok(Self::Allow),
            "DENY" => Ok(Self::Deny),
            other => Err(format!("digit_advise must be ALLOW|DENY, got {other}")),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Allow => "ALLOW",
            Self::Deny => "DENY",
        }
    }
}

/// Coherence from residual vs budget: 1 = perfect close, 0 = residual consumes budget.
pub fn coherence_from_residual(budget_j: f64, residual_j: f64) -> f64 {
    if !(budget_j.is_finite() && residual_j.is_finite()) || budget_j <= 0.0 {
        return 0.0;
    }
    let c = 1.0 - (residual_j.abs() / budget_j);
    c.clamp(0.0, 1.0)
}

/// Physics allows traverse current when world says feasible and no sinkage risk.
pub fn physics_pass_current(traverse_feasible: bool, sinkage_risk: bool) -> bool {
    physics_pass_with_failure_modes(traverse_feasible, sinkage_risk, true)
}

/// FAILURE_MODE_GATE: named mission killers must be clear (drawbar/storm/jerk/dust…).
/// `failure_modes_clear=false` refuses current even if legacy traverse flags pass.
pub fn physics_pass_with_failure_modes(
    traverse_feasible: bool,
    sinkage_risk: bool,
    failure_modes_clear: bool,
) -> bool {
    traverse_feasible && !sinkage_risk && failure_modes_clear
}

/// Current may flow only if digit ALLOW ∧ physics_pass.
pub fn current_allowed(digit: DigitAdvise, physics_pass: bool) -> bool {
    matches!(digit, DigitAdvise::Allow) && physics_pass
}

/// Governance coherent when digit agrees with physics (ALLOW↔pass, DENY↔!pass).
pub fn governance_coherent(digit: DigitAdvise, physics_pass: bool) -> bool {
    match digit {
        DigitAdvise::Allow => physics_pass,
        DigitAdvise::Deny => !physics_pass,
    }
}

pub fn lie_increment(digit: DigitAdvise, physics_pass: bool) -> f64 {
    if governance_coherent(digit, physics_pass) {
        0.0
    } else {
        1.0
    }
}

pub fn apoptosis_tripped(lie_score: f64, threshold: f64) -> bool {
    lie_score.is_finite() && threshold.is_finite() && lie_score + DEFAULT_ABS_TOL >= threshold
}

/// Emit physics_gate_v1 JSON value.
pub fn emit_physics_gate_v1(
    gate_id: &str,
    digit: DigitAdvise,
    traverse_feasible: bool,
    sinkage_risk: bool,
    budget_j: f64,
    residual_j: f64,
    prior_lie_score: f64,
    prior_apoptosis: bool,
    lie_threshold: f64,
) -> Result<Value, String> {
    emit_physics_gate_v1_with_modes(
        gate_id,
        digit,
        traverse_feasible,
        sinkage_risk,
        true,
        budget_j,
        residual_j,
        prior_lie_score,
        prior_apoptosis,
        lie_threshold,
    )
}

/// Emit physics_gate_v1 with FAILURE_MODE_GATE clear bit (PROOF_TIER_LADDER).
pub fn emit_physics_gate_v1_with_modes(
    gate_id: &str,
    digit: DigitAdvise,
    traverse_feasible: bool,
    sinkage_risk: bool,
    failure_modes_clear: bool,
    budget_j: f64,
    residual_j: f64,
    prior_lie_score: f64,
    prior_apoptosis: bool,
    lie_threshold: f64,
) -> Result<Value, String> {
    if !(budget_j.is_finite() && residual_j.is_finite() && prior_lie_score.is_finite()) {
        return Err("budget/residual/prior_lie must be finite".into());
    }
    if prior_lie_score < 0.0 {
        return Err("prior_lie_score must be >= 0".into());
    }
    let physics_pass =
        physics_pass_with_failure_modes(traverse_feasible, sinkage_risk, failure_modes_clear);
    let allowed = current_allowed(digit, physics_pass);
    let coherent = governance_coherent(digit, physics_pass);
    let inc = lie_increment(digit, physics_pass);
    let lie_score = prior_lie_score + inc;
    // Irreversible: once apoptosis latched, stays latched
    let bit = prior_apoptosis || apoptosis_tripped(lie_score, lie_threshold);
    let coherence = coherence_from_residual(budget_j, residual_j);

    let apo_reason: Value = if bit {
        if prior_apoptosis {
            Value::String("prior_latch".into())
        } else {
            Value::String("lie_threshold".into())
        }
    } else {
        Value::Null
    };

    Ok(json!({
        "schema": SCHEMA,
        "gate_id": gate_id,
        "digit_advise": digit.as_str(),
        "physics_pass": physics_pass,
        "current_allowed": allowed,
        "governance_coherent": coherent,
        "coherence": coherence,
        "residual_joules": residual_j,
        "budget_joules": budget_j,
        "lie_score": lie_score,
        "lie_increment": inc,
        "apoptosis": {
            "bit": bit,
            "threshold": lie_threshold,
            "irreversible": true,
            "prior_bit": prior_apoptosis,
            "reason": apo_reason
        },
        "inputs": {
            "traverse_feasible": traverse_feasible,
            "sinkage_risk": sinkage_risk,
            "failure_modes_clear": failure_modes_clear
        },
        "honesty": {
            "not_measured": true,
            "sim_slice": true,
            "not_silicon_fuse": true,
            "failure_mode_gate": true,
            "proof_tier": "FAILURE_MODE_GATE",
            "epsilon": [
                "ε_soft_physics_proxy",
                "ε_mode_set_incomplete",
                "ε_desk_not_world"
            ]
        }
    }))
}

/// Validate physics_gate_v1 document.
pub fn validate_physics_gate_v1(json: &str) -> Result<(), Vec<String>> {
    let root: Value = match serde_json::from_str(json) {
        Ok(v) => v,
        Err(e) => return Err(vec![format!("invalid JSON: {e}")]),
    };
    let obj = match root.as_object() {
        Some(o) => o,
        None => return Err(vec!["root must be a JSON object".into()]),
    };
    let mut errors = Vec::new();

    match obj.get("schema") {
        Some(Value::String(s)) if s == SCHEMA => {}
        _ => errors.push(format!("schema must be \"{SCHEMA}\"")),
    }

    let digit = match obj.get("digit_advise").and_then(|v| v.as_str()) {
        Some(s) => match DigitAdvise::parse(s) {
            Ok(d) => Some(d),
            Err(e) => {
                errors.push(e);
                None
            }
        },
        None => {
            errors.push("digit_advise required".into());
            None
        }
    };

    let physics_pass = match obj.get("physics_pass") {
        Some(Value::Bool(b)) => Some(*b),
        _ => {
            errors.push("physics_pass must be bool".into());
            None
        }
    };

    let current = match obj.get("current_allowed") {
        Some(Value::Bool(b)) => Some(*b),
        _ => {
            errors.push("current_allowed must be bool".into());
            None
        }
    };

    if let (Some(d), Some(p), Some(c)) = (digit, physics_pass, current) {
        let expect = current_allowed(d, p);
        if c != expect {
            errors.push(format!(
                "current_allowed_mismatch: field={c} expect={expect}"
            ));
        }
        let expect_coherent = governance_coherent(d, p);
        match obj.get("governance_coherent") {
            Some(Value::Bool(b)) if *b == expect_coherent => {}
            Some(Value::Bool(b)) => errors.push(format!(
                "governance_coherent_mismatch: field={b} expect={expect_coherent}"
            )),
            _ => errors.push("governance_coherent must be bool".into()),
        }
    }

    let apo = obj.get("apoptosis").and_then(|v| v.as_object());
    let Some(apo) = apo else {
        errors.push("apoptosis object required".into());
        return Err(errors);
    };
    let bit = match apo.get("bit") {
        Some(Value::Bool(b)) => Some(*b),
        _ => {
            errors.push("apoptosis.bit must be bool".into());
            None
        }
    };
    let threshold = match apo.get("threshold").and_then(|v| v.as_f64()) {
        Some(t) if t.is_finite() && t > 0.0 => Some(t),
        _ => {
            errors.push("apoptosis.threshold must be finite > 0".into());
            None
        }
    };
    let lie_score = match obj.get("lie_score").and_then(|v| v.as_f64()) {
        Some(s) if s.is_finite() && s >= 0.0 => Some(s),
        _ => {
            errors.push("lie_score must be finite >= 0".into());
            None
        }
    };
    if let (Some(bit), Some(threshold), Some(lie_score)) = (bit, threshold, lie_score) {
        let prior = apo
            .get("prior_bit")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let expect = prior || apoptosis_tripped(lie_score, threshold);
        if bit != expect {
            errors.push(format!(
                "apoptosis_bit_mismatch: field={bit} expect={expect}"
            ));
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_coherent_no_apoptosis() {
        let v = emit_physics_gate_v1(
            "g1",
            DigitAdvise::Allow,
            true,
            false,
            1.0,
            0.5,
            0.0,
            false,
            DEFAULT_LIE_THRESHOLD,
        )
        .unwrap();
        assert_eq!(v["physics_pass"], true);
        assert_eq!(v["current_allowed"], true);
        assert_eq!(v["governance_coherent"], true);
        assert_eq!(v["lie_increment"], 0.0);
        assert_eq!(v["apoptosis"]["bit"], false);
        let text = serde_json::to_string(&v).unwrap();
        validate_physics_gate_v1(&text).expect("valid");
    }

    #[test]
    fn hostile_deny_coherent() {
        let v = emit_physics_gate_v1(
            "g2",
            DigitAdvise::Deny,
            false,
            true,
            1.0,
            0.4,
            0.0,
            false,
            DEFAULT_LIE_THRESHOLD,
        )
        .unwrap();
        assert_eq!(v["physics_pass"], false);
        assert_eq!(v["current_allowed"], false);
        assert_eq!(v["governance_coherent"], true);
        assert_eq!(v["apoptosis"]["bit"], false);
    }

    #[test]
    fn lie_trips_apoptosis() {
        let v = emit_physics_gate_v1(
            "g3",
            DigitAdvise::Allow,
            false,
            true,
            1.0,
            0.2,
            2.5,
            false,
            DEFAULT_LIE_THRESHOLD,
        )
        .unwrap();
        assert_eq!(v["lie_increment"], 1.0);
        assert_eq!(v["lie_score"], 3.5);
        assert_eq!(v["apoptosis"]["bit"], true);
        let text = serde_json::to_string(&v).unwrap();
        validate_physics_gate_v1(&text).expect("valid with apoptosis");
    }

    #[test]
    fn prior_apoptosis_latches() {
        let v = emit_physics_gate_v1(
            "g4",
            DigitAdvise::Deny,
            false,
            true,
            1.0,
            0.1,
            0.0,
            true,
            DEFAULT_LIE_THRESHOLD,
        )
        .unwrap();
        assert_eq!(v["apoptosis"]["bit"], true);
        assert_eq!(v["apoptosis"]["reason"], "prior_latch");
    }
}
