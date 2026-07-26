//! 1D thermal column implicit step (U4 M1).
//!
//! Backward-Euler diffusion with surface flux BC:
//!   rho*cp * dT/dt = d/dz ( k(T) dT/dz )
//! Surface: flux q_in into top node (half-cell).
//! k(T) from thermal.rs (Sakatani + optional cryo).
//!
//! Not 3D FEM. Not MEASURED.

use crate::thermal::{apply_cryo_scale, k_w_mk};
use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const COLUMN_SCHEMA: &str = "ha_thermal_column_step_eval_v1";
pub const COLUMN_ORACLE: &str = "ha_physics_gate_thermal_column";

fn solve_tridiagonal(a: &[f64], b: &[f64], c: &[f64], d: &[f64]) -> Result<Vec<f64>, String> {
    let n = d.len();
    if n == 0 || a.len() != n || b.len() != n || c.len() != n {
        return Err("tridiagonal length mismatch".into());
    }
    let mut cp = vec![0.0; n];
    let mut dp = vec![0.0; n];
    let mut denom = b[0];
    if denom.abs() < 1e-30 {
        denom = 1e-30;
    }
    if n > 1 {
        cp[0] = c[0] / denom;
    }
    dp[0] = d[0] / denom;
    for i in 1..n {
        denom = b[i] - a[i] * cp[i - 1];
        if denom.abs() < 1e-30 {
            denom = 1e-30;
        }
        if i < n - 1 {
            cp[i] = c[i] / denom;
        }
        dp[i] = (d[i] - a[i] * dp[i - 1]) / denom;
    }
    let mut x = vec![0.0; n];
    x[n - 1] = dp[n - 1];
    for i in (0..n - 1).rev() {
        x[i] = dp[i] - cp[i] * x[i + 1];
    }
    Ok(x)
}

fn k_interface(k_a: f64, k_b: f64) -> f64 {
    0.5 * (k_a + k_b)
}

fn node_k(
    t_k: f64,
    k_solid: f64,
    b_rad: f64,
    apply_cryo: bool,
    t_cryo: f64,
    cryo_scale: f64,
) -> Result<f64, String> {
    let base = k_w_mk(k_solid, b_rad, t_k)?;
    let (k, _) = if apply_cryo {
        apply_cryo_scale(base, t_k, t_cryo, cryo_scale)?
    } else {
        (base, 1.0)
    };
    Ok(k.max(1e-9))
}

fn implicit_system(
    t_old: &[f64],
    dt_s: f64,
    dz: f64,
    rho_cp: f64,
    q_in: f64,
    k_nodes: &[f64],
) -> Result<Vec<f64>, String> {
    let n = t_old.len();
    let mut a = vec![0.0; n];
    let mut b = vec![0.0; n];
    let mut c = vec![0.0; n];
    let mut d = vec![0.0; n];

    if n == 1 {
        let k01 = k_nodes[0];
        b[0] = rho_cp * dz / (2.0 * dt_s) + k01 / dz;
        d[0] = rho_cp * dz / (2.0 * dt_s) * t_old[0] + q_in;
        return solve_tridiagonal(&a, &b, &c, &d);
    }

    let k01 = k_interface(k_nodes[0], k_nodes[1]);
    b[0] = rho_cp * dz / (2.0 * dt_s) + k01 / dz;
    c[0] = -k01 / dz;
    d[0] = rho_cp * dz / (2.0 * dt_s) * t_old[0] + q_in;

    for i in 1..n - 1 {
        let k_im1 = k_interface(k_nodes[i - 1], k_nodes[i]);
        let k_ip1 = k_interface(k_nodes[i], k_nodes[i + 1]);
        a[i] = -k_im1 / dz;
        b[i] = rho_cp / dt_s + (k_im1 + k_ip1) / dz;
        c[i] = -k_ip1 / dz;
        d[i] = rho_cp / dt_s * t_old[i];
    }

    let k_nb = k_interface(k_nodes[n - 2], k_nodes[n - 1]);
    a[n - 1] = -k_nb / dz;
    b[n - 1] = rho_cp * dz / (2.0 * dt_s) + k_nb / dz;
    d[n - 1] = rho_cp * dz / (2.0 * dt_s) * t_old[n - 1];

    solve_tridiagonal(&a, &b, &c, &d)
}

/// One Picard-implicit column step. Returns new T vector and surface dT.
pub fn step_column_implicit(
    t_k: &[f64],
    dt_s: f64,
    dz: f64,
    rho_cp: f64,
    q_in_w_m2: f64,
    k_solid: f64,
    b_rad: f64,
    apply_cryo: bool,
    t_cryo: f64,
    cryo_scale: f64,
    picard_iters: usize,
    t_lo: f64,
    t_hi: f64,
) -> Result<(Vec<f64>, f64, f64), String> {
    if t_k.is_empty() {
        return Err("t_k empty".into());
    }
    if !(dt_s.is_finite() && dt_s > 0.0) {
        return Err("dt_s must be finite > 0".into());
    }
    if !(dz.is_finite() && dz > 0.0) {
        return Err("dz must be finite > 0".into());
    }
    if !(rho_cp.is_finite() && rho_cp > 0.0) {
        return Err("rho_cp must be finite > 0".into());
    }
    if !q_in_w_m2.is_finite() {
        return Err("q_in must be finite".into());
    }
    if !(t_lo < t_hi) {
        return Err("t_lo must be < t_hi".into());
    }
    let iters = picard_iters.max(1);
    let t_old = t_k.to_vec();
    let t0 = t_old[0];
    let mut t_guess = t_old.clone();
    for _ in 0..iters {
        let mut k_nodes = Vec::with_capacity(t_guess.len());
        for &t in &t_guess {
            k_nodes.push(node_k(t, k_solid, b_rad, apply_cryo, t_cryo, cryo_scale)?);
        }
        t_guess = implicit_system(&t_old, dt_s, dz, rho_cp, q_in_w_m2, &k_nodes)?;
    }
    let t_raw = t_guess[0];
    let mut t_out = Vec::with_capacity(t_guess.len());
    for t in t_guess {
        t_out.push(t.max(t_lo).min(t_hi));
    }
    let d_surf = t_out[0] - t0;
    Ok((t_out, d_surf, t_raw))
}

pub fn evaluate_column_step_from_catalog(
    catalog_json: &str,
    material_id: &str,
    t_k: &[f64],
    dt_h: f64,
    dz_m: f64,
    rho_cp: f64,
    q_in_w_m2: f64,
    apply_cryo: bool,
    picard_iters: usize,
    t_lo: f64,
    t_hi: f64,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let mats = root
        .get("materials")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "catalog.missing materials".to_string())?;
    let mat = mats
        .get(material_id)
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("unknown material_id={material_id}"))?;
    let k_solid = mat
        .get("k_solid_w_mk")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "k_solid_w_mk required".to_string())?;
    let b_rad = mat
        .get("b_rad")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "b_rad required".to_string())?;
    let cryo = root
        .get("cryo_leg")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "cryo_leg required".to_string())?;
    let t_cryo = cryo
        .get("t_cryo_k")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "t_cryo_k required".to_string())?;
    let cryo_scale = cryo
        .get("k_scale_below_t_cryo")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "k_scale_below_t_cryo required".to_string())?;

    let dt_s = dt_h * 3600.0;
    let (t_out, d_surf, t_raw) = step_column_implicit(
        t_k,
        dt_s,
        dz_m,
        rho_cp,
        q_in_w_m2,
        k_solid,
        b_rad,
        apply_cryo,
        t_cryo,
        cryo_scale,
        picard_iters,
        t_lo,
        t_hi,
    )?;
    Ok(json!({
        "schema": COLUMN_SCHEMA,
        "oracle": COLUMN_ORACLE,
        "material_id": material_id,
        "dt_h": dt_h,
        "dz_m": dz_m,
        "rho_cp": rho_cp,
        "q_in_w_m2": q_in_w_m2,
        "apply_cryo": apply_cryo,
        "picard_iters": picard_iters.max(1),
        "t_k_in": t_k,
        "t_k_out": t_out,
        "dT_surface_k": (d_surf * 1e9).round() / 1e9,
        "t_surface_raw_k": (t_raw * 1e9).round() / 1e9,
        "envelope_k": [t_lo, t_hi],
        "equation": "rho*cp*dT/dt = d/dz(k dT/dz); surface q_in; Picard on k(T)",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "one_d_not_3d_fem": true
        }
    }))
}

pub fn evaluate_column_step_file(
    catalog_path: &Path,
    material_id: &str,
    t_k: &[f64],
    dt_h: f64,
    dz_m: f64,
    rho_cp: f64,
    q_in_w_m2: f64,
    apply_cryo: bool,
    picard_iters: usize,
    t_lo: f64,
    t_hi: f64,
) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_column_step_from_catalog(
        &text,
        material_id,
        t_k,
        dt_h,
        dz_m,
        rho_cp,
        q_in_w_m2,
        apply_cryo,
        picard_iters,
        t_lo,
        t_hi,
    )
}

#[cfg(test)]
mod column_tests {
    use super::*;

    #[test]
    fn heating_raises_surface() {
        let t0 = vec![220.0, 220.0, 220.0];
        let (tout, d, _) = step_column_implicit(
            &t0, 900.0, 0.1, 1.28e6, 50.0, 0.0154, 2.45e-10, false, 150.0, 0.1, 2, 100.0, 400.0,
        )
        .unwrap();
        assert!(d > 0.0);
        assert!(tout[0] > t0[0]);
    }
}
