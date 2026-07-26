//! SE(3) Lie exp-map single step — host reference for LieIntegratorPort Rust backend.

use serde::{Deserialize, Serialize};

use crate::cga_rotor3::Rotor3;

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct Motor7 {
    pub qw: f64,
    pub qx: f64,
    pub qy: f64,
    pub qz: f64,
    pub tx: f64,
    pub ty: f64,
    pub tz: f64,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct LieStepInput {
    pub pose: Motor7,
    pub omega: [f64; 3],
    pub linear: [f64; 3],
    pub dt: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LieStepOutput {
    pub pose: Motor7,
    pub quat_norm: f64,
    pub rotation_frobenius_err: f64,
    pub on_manifold: bool,
    pub backend_id: String,
}

fn rotor_from_motor(m: &Motor7) -> Rotor3 {
    Rotor3 {
        s: m.qw,
        b12: m.qx,
        b23: m.qy,
        b31: m.qz,
    }
}

fn motor_from_rotor(r: Rotor3, t: (f64, f64, f64)) -> Motor7 {
    Motor7 {
        qw: r.s,
        qx: r.b12,
        qy: r.b23,
        qz: r.b31,
        tx: t.0,
        ty: t.1,
        tz: t.2,
    }
}

fn quat_norm(m: &Motor7) -> f64 {
    (m.qw * m.qw + m.qx * m.qx + m.qy * m.qy + m.qz * m.qz).sqrt()
}

fn rotation_frobenius_err(m: &Motor7) -> f64 {
    let w = m.qw;
    let x = m.qx;
    let y = m.qy;
    let z = m.qz;
    let r00 = 1.0 - 2.0 * (y * y + z * z);
    let r01 = 2.0 * (x * y - z * w);
    let r02 = 2.0 * (x * z + y * w);
    let r10 = 2.0 * (x * y + z * w);
    let r11 = 1.0 - 2.0 * (x * x + z * z);
    let r12 = 2.0 * (y * z - x * w);
    let r20 = 2.0 * (x * z - y * w);
    let r21 = 2.0 * (y * z + x * w);
    let r22 = 1.0 - 2.0 * (x * x + y * y);
    let e00 = r00 * r00 + r10 * r10 + r20 * r20 - 1.0;
    let e01 = r00 * r01 + r10 * r11 + r20 * r21;
    let e02 = r00 * r02 + r10 * r12 + r20 * r22;
    let e11 = r01 * r01 + r11 * r11 + r21 * r21 - 1.0;
    let e12 = r01 * r02 + r11 * r12 + r21 * r22;
    let e22 = r02 * r02 + r12 * r12 + r22 * r22 - 1.0;
    (e00 * e00 + e01 * e01 + e02 * e02 + e11 * e11 + e12 * e12 + e22 * e22).sqrt()
}

/// R_new = R ⊗ exp(ω·dt); translation += v·dt (world-frame slice matching Python host).
pub fn lie_exp_step(inp: &LieStepInput) -> LieStepOutput {
    let ox = inp.omega[0];
    let oy = inp.omega[1];
    let oz = inp.omega[2];
    let omega_mag = (ox * ox + oy * oy + oz * oz).sqrt();
    let mut r = rotor_from_motor(&inp.pose);
    if omega_mag > 1e-12 {
        let axis = crate::cga_rotor3::Vec3::new(ox / omega_mag, oy / omega_mag, oz / omega_mag);
        let delta = Rotor3::from_axis_angle(axis, omega_mag * inp.dt);
        r = delta.mul(r).normalize();
    }
    let lx = inp.linear[0] * inp.dt;
    let ly = inp.linear[1] * inp.dt;
    let lz = inp.linear[2] * inp.dt;
    let pose = motor_from_rotor(
        r,
        (
            inp.pose.tx + lx,
            inp.pose.ty + ly,
            inp.pose.tz + lz,
        ),
    );
    let qn = quat_norm(&pose);
    let rot_err = rotation_frobenius_err(&pose);
    let on = (qn - 1.0).abs() <= 1e-4 && rot_err <= 1e-3;
    LieStepOutput {
        pose,
        quat_norm: qn,
        rotation_frobenius_err: rot_err,
        on_manifold: on,
        backend_id: "lie_rust_cga_exp_v1".to_string(),
    }
}
