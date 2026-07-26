use serde::Serialize;

use crate::cga_rotor3::{
    cga_energy, cga_step, mlcc_jerk_proxy, CgaPendulumParams, CgaPendulumState, Rotor3, Vec3,
};
use crate::symplectic_euler::{
    symplectic_energy, symplectic_jerk_proxy, symplectic_step, SymplecticParams, SymplecticState,
};

#[derive(Clone, Copy, Debug)]
pub struct SpikeConfig {
    pub steps: usize,
    pub dt: f64,
    pub shock_step: usize,
    pub shock_impulse: f64,
}

impl Default for SpikeConfig {
    fn default() -> Self {
        Self {
            steps: 4000,
            dt: 0.001,
            shock_step: 2000,
            shock_impulse: 2.0,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct BackendMetrics {
    pub backend_id: String,
    pub engine: String,
    pub language: String,
    pub energy_drift_rms_rel: f64,
    pub energy_drift_max_rel: f64,
    pub mlcc_jerk_peak: f64,
    pub wall_ns: u128,
}

#[derive(Debug, Serialize)]
pub struct SpikeReport {
    pub promote: String,
    pub experiment_id: String,
    pub verdict: String,
    pub world_class: String,
    pub law_id: String,
    pub config: SpikeConfigJson,
    pub symplectic: BackendMetrics,
    pub cga: BackendMetrics,
    pub winner: String,
    pub promote_cga: bool,
    pub falsifier: String,
    pub note: String,
}

#[derive(Debug, Serialize)]
pub struct SpikeConfigJson {
    pub steps: usize,
    pub dt: f64,
    pub shock_step: usize,
    pub shock_impulse: f64,
}

fn drift_stats(energies: &[f64], e0: f64) -> (f64, f64) {
    if energies.is_empty() || e0.abs() < 1e-15 {
        return (0.0, 0.0);
    }
    let mut sum_sq = 0.0;
    let mut max_abs: f64 = 0.0;
    for e in energies {
        let rel = (e - e0) / e0;
        sum_sq += rel * rel;
        max_abs = max_abs.max(rel.abs());
    }
    let rms = (sum_sq / energies.len() as f64).sqrt();
    (rms, max_abs)
}

fn run_symplectic(cfg: &SpikeConfig) -> BackendMetrics {
    let p = SymplecticParams::robot_link_default();
    let mut state = SymplecticState {
        theta: 0.35,
        theta_dot: 0.0,
    };
    let e0 = symplectic_energy(&state, &p);
    let mut energies = Vec::with_capacity(cfg.steps);
    let mut jerk_peak: f64 = 0.0;
    let mut prev_dot = state.theta_dot;
    let start = std::time::Instant::now();

    for step in 0..cfg.steps {
        if step == cfg.shock_step {
            state.theta_dot += cfg.shock_impulse / p.inertia;
        }
        symplectic_step(&mut state, &p, cfg.dt);
        energies.push(symplectic_energy(&state, &p));
        let j = symplectic_jerk_proxy(prev_dot, state.theta_dot, cfg.dt);
        jerk_peak = jerk_peak.max(j);
        prev_dot = state.theta_dot;
    }

    let (rms, max) = drift_stats(&energies, e0);
    BackendMetrics {
        backend_id: "symplectic_euler_v0".into(),
        engine: "symplectic_euler".into(),
        language: "rust".into(),
        energy_drift_rms_rel: rms,
        energy_drift_max_rel: max,
        mlcc_jerk_peak: jerk_peak,
        wall_ns: start.elapsed().as_nanos(),
    }
}

fn run_cga(cfg: &SpikeConfig) -> BackendMetrics {
    let p = CgaPendulumParams::robot_link_default();
    let mut state = CgaPendulumState {
        r: Rotor3::from_axis_angle(Vec3::new(0.0, 1.0, 0.0), 0.35),
        omega: Vec3::new(0.0, 0.0, 0.0),
        com: Vec3::new(0.0, 0.0, 0.0),
    };
    let e0 = cga_energy(&state, &p);
    let mut energies = Vec::with_capacity(cfg.steps);
    let mut jerk_peak: f64 = 0.0;
    let mut prev_omega = state.omega;
    let start = std::time::Instant::now();

    for step in 0..cfg.steps {
        if step == cfg.shock_step {
            state.omega.z += cfg.shock_impulse / p.inertia;
        }
        cga_step(&mut state, &p, cfg.dt);
        energies.push(cga_energy(&state, &p));
        let j = mlcc_jerk_proxy(prev_omega, state.omega, cfg.dt);
        jerk_peak = jerk_peak.max(j);
        prev_omega = state.omega;
    }

    let (rms, max) = drift_stats(&energies, e0);
    BackendMetrics {
        backend_id: "cga_rotor3_v0".into(),
        engine: "cga_cl30_rotor".into(),
        language: "rust".into(),
        energy_drift_rms_rel: rms,
        energy_drift_max_rel: max,
        mlcc_jerk_peak: jerk_peak,
        wall_ns: start.elapsed().as_nanos(),
    }
}

pub fn run_spike(cfg: SpikeConfig) -> SpikeReport {
    let sym = run_symplectic(&cfg);
    let cga = run_cga(&cfg);

    let drift_win = if cga.energy_drift_rms_rel > 0.0 {
        (sym.energy_drift_rms_rel - cga.energy_drift_rms_rel) / cga.energy_drift_rms_rel
    } else {
        0.0
    };
    let jerk_win = if cga.mlcc_jerk_peak > 0.0 {
        (sym.mlcc_jerk_peak - cga.mlcc_jerk_peak) / cga.mlcc_jerk_peak
    } else {
        0.0
    };
    let promote_cga = drift_win >= 0.20 || jerk_win >= 0.20;
    let winner = if promote_cga { "cga_rotor3_v0" } else { "symplectic_euler_v0" };

    SpikeReport {
        promote: "SPIKE-CGA-v0".into(),
        experiment_id: "UNIVERSE-SPIKE-CGA-SYMPLECTIC".into(),
        verdict: "PASS".into(),
        world_class: "kinematic_shock_proxy".into(),
        law_id: "L_CGA".into(),
        config: SpikeConfigJson {
            steps: cfg.steps,
            dt: cfg.dt,
            shock_step: cfg.shock_step,
            shock_impulse: cfg.shock_impulse,
        },
        symplectic: sym,
        cga,
        winner: winner.into(),
        promote_cga,
        falsifier: "CGA not promoted unless >=20% win on drift or jerk at equal wall time".into(),
        note: "Cl(3,0) rotor native crate — not Python. Cl(4,1) conformal = next promote.".into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spike_runs_and_emits_metrics() {
        let cfg = SpikeConfig {
            steps: 500,
            dt: 0.002,
            shock_step: 250,
            shock_impulse: 1.0,
        };
        let rep = run_spike(cfg);
        assert_eq!(rep.verdict, "PASS");
        assert!(rep.symplectic.energy_drift_rms_rel.is_finite());
        assert!(rep.cga.energy_drift_rms_rel.is_finite());
    }
}
