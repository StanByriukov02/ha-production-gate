//! 2-link planar double pendulum — both angles from vertical, mass-matrix Störmer–Verlet (G5 slice).

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct DoublePendulumParams {
    pub m1: f64,
    pub m2: f64,
    pub l1: f64,
    pub l2: f64,
    pub g: f64,
}

impl Default for DoublePendulumParams {
    fn default() -> Self {
        Self {
            m1: 1.0,
            m2: 1.0,
            l1: 0.5,
            l2: 0.5,
            g: 9.81,
        }
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct DoublePendulumState {
    pub theta1: f64,
    pub theta2: f64,
    pub theta1_dot: f64,
    pub theta2_dot: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DoublePendulumEnergyReport {
    pub steps: usize,
    pub dt: f64,
    pub energy0: f64,
    pub max_rel_drift: f64,
    pub backend_id: String,
}

fn kinetic_energy(state: &DoublePendulumState, p: &DoublePendulumParams) -> f64 {
    let (t1, t2, w1, w2) = (
        state.theta1,
        state.theta2,
        state.theta1_dot,
        state.theta2_dot,
    );
    let v1x = p.l1 * w1 * t1.cos();
    let v1y = p.l1 * w1 * t1.sin();
    let v2x = p.l1 * w1 * t1.cos() + p.l2 * w2 * t2.cos();
    let v2y = p.l1 * w1 * t1.sin() + p.l2 * w2 * t2.sin();
    0.5 * p.m1 * (v1x * v1x + v1y * v1y) + 0.5 * p.m2 * (v2x * v2x + v2y * v2y)
}

fn potential_energy(state: &DoublePendulumState, p: &DoublePendulumParams) -> f64 {
    let y1 = -p.l1 * state.theta1.cos();
    let y2 = -p.l1 * state.theta1.cos() - p.l2 * state.theta2.cos();
    p.m1 * p.g * y1 + p.m2 * p.g * y2
}

pub fn total_energy(state: &DoublePendulumState, p: &DoublePendulumParams) -> f64 {
    kinetic_energy(state, p) + potential_energy(state, p)
}

fn accelerations(state: &DoublePendulumState, p: &DoublePendulumParams) -> (f64, f64) {
    let (t1, t2, w1, w2) = (
        state.theta1,
        state.theta2,
        state.theta1_dot,
        state.theta2_dot,
    );
    let delta = t1 - t2;
    let m11 = (p.m1 + p.m2) * p.l1 * p.l1;
    let m22 = p.m2 * p.l2 * p.l2;
    let m12 = p.m2 * p.l1 * p.l2 * delta.cos();
    let f1 = -p.m2 * p.l1 * p.l2 * w2 * w2 * delta.sin() - (p.m1 + p.m2) * p.g * p.l1 * t1.sin();
    let f2 = p.m2 * p.l1 * p.l2 * w1 * w1 * delta.sin() - p.m2 * p.g * p.l2 * t2.sin();
    let det = m11 * m22 - m12 * m12;
    let a1 = (f1 * m22 - f2 * m12) / det;
    let a2 = (f2 * m11 - f1 * m12) / det;
    (a1, a2)
}

pub fn symplectic_double_pendulum_chain(
    mut state: DoublePendulumState,
    p: &DoublePendulumParams,
    steps: usize,
    dt: f64,
) -> DoublePendulumEnergyReport {
    let e0 = total_energy(&state, p);
    let e0_abs = e0.abs().max(1e-9);
    let mut max_rel = 0.0_f64;
    for _ in 0..steps {
        let (a1, a2) = accelerations(&state, p);
        state.theta1_dot += a1 * dt;
        state.theta2_dot += a2 * dt;
        state.theta1 += state.theta1_dot * dt;
        state.theta2 += state.theta2_dot * dt;
        let rel = (total_energy(&state, p) - e0).abs() / e0_abs;
        max_rel = max_rel.max(rel);
    }
    DoublePendulumEnergyReport {
        steps,
        dt,
        energy0: e0,
        max_rel_drift: max_rel,
        backend_id: "lie_multibody_double_pendulum_symplectic_v1".into(),
    }
}
