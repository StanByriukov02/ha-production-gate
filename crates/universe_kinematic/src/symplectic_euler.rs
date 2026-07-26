//! Symplectic Euler baseline — same rigid link, Euler angles (reference, not production robot).

use crate::cga_rotor3::{mlcc_jerk_proxy, Vec3};

#[derive(Clone, Copy, Debug)]
pub struct SymplecticState {
    pub theta: f64,
    pub theta_dot: f64,
}

pub struct SymplecticParams {
    pub mass: f64,
    pub length: f64,
    pub gravity: f64,
    pub inertia: f64,
}

impl SymplecticParams {
    pub fn robot_link_default() -> Self {
        Self {
            mass: 1.0,
            length: 0.5,
            gravity: 9.81,
            inertia: 0.25,
        }
    }
}

pub fn symplectic_energy(state: &SymplecticState, p: &SymplecticParams) -> f64 {
    let height = -p.length * state.theta.cos();
    0.5 * p.inertia * state.theta_dot * state.theta_dot + p.mass * p.gravity * height
}

pub fn symplectic_step(state: &mut SymplecticState, p: &SymplecticParams, dt: f64) {
    let torque = -p.mass * p.gravity * p.length * state.theta.sin();
    let alpha = torque / p.inertia;
    state.theta_dot += alpha * dt;
    state.theta += state.theta_dot * dt;
}

pub fn symplectic_omega_vec(theta_dot: f64) -> Vec3 {
    Vec3::new(0.0, 0.0, theta_dot)
}

pub fn symplectic_jerk_proxy(prev_dot: f64, dot: f64, dt: f64) -> f64 {
    mlcc_jerk_proxy(
        symplectic_omega_vec(prev_dot),
        symplectic_omega_vec(dot),
        dt,
    )
}
