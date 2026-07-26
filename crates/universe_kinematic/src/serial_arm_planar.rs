//! Planar serial revolute arm — FK, Jacobian, damped IK, symplectic dynamics.
//! Crown engine slot for lunar scout 3-DOF teaching chain.

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SerialArmParams {
    pub link_lengths: Vec<f64>,
    pub link_masses: Vec<f64>,
    pub g: f64,
}

impl SerialArmParams {
    pub fn scout_3dof_lunar() -> Self {
        Self {
            link_lengths: vec![0.25, 0.28, 0.22],
            link_masses: vec![0.45, 0.38, 0.22],
            g: 1.62,
        }
    }

    pub fn n(&self) -> usize {
        self.link_lengths.len()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SerialArmState {
    pub q: Vec<f64>,
    pub q_dot: Vec<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FkReport {
    pub ee_x: f64,
    pub ee_y: f64,
    pub ee_theta: f64,
    pub joint_world_angles: Vec<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IkReport {
    pub q: Vec<f64>,
    pub ee_x: f64,
    pub ee_y: f64,
    pub iterations: usize,
    pub final_error_m: f64,
    pub converged: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JacobianReport {
    pub j_flat: Vec<f64>,
    pub rows: usize,
    pub cols: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SymplecticReport {
    pub steps: usize,
    pub dt: f64,
    pub energy0: f64,
    pub max_rel_drift: f64,
    pub final_state: SerialArmState,
    pub backend_id: String,
}

fn cumulative_angles(q: &[f64]) -> Vec<f64> {
    let mut out = Vec::with_capacity(q.len());
    let mut acc = 0.0;
    for &qi in q {
        acc += qi;
        out.push(acc);
    }
    out
}

pub fn forward_kinematics(params: &SerialArmParams, q: &[f64]) -> FkReport {
    let n = params.n();
    assert_eq!(q.len(), n);
    let thetas = cumulative_angles(q);
    let mut x = 0.0;
    let mut y = 0.0;
    for i in 0..n {
        x += params.link_lengths[i] * thetas[i].cos();
        y += params.link_lengths[i] * thetas[i].sin();
    }
    FkReport {
        ee_x: x,
        ee_y: y,
        ee_theta: *thetas.last().unwrap_or(&0.0),
        joint_world_angles: thetas,
    }
}

pub fn jacobian_ee(params: &SerialArmParams, q: &[f64]) -> JacobianReport {
    let n = params.n();
    let thetas = cumulative_angles(q);
    let mut j_flat = vec![0.0; 2 * n];
    for j in 0..n {
        let mut dx = 0.0;
        let mut dy = 0.0;
        for i in j..n {
            dx -= params.link_lengths[i] * thetas[i].sin();
            dy += params.link_lengths[i] * thetas[i].cos();
        }
        j_flat[j] = dx;
        j_flat[n + j] = dy;
    }
    JacobianReport {
        j_flat,
        rows: 2,
        cols: n,
    }
}

pub fn inverse_kinematics_dls(
    params: &SerialArmParams,
    target_x: f64,
    target_y: f64,
    q0: &[f64],
    max_iter: usize,
    lambda: f64,
    tol_m: f64,
) -> IkReport {
    let n = params.n();
    let mut q = q0.to_vec();
    let mut err = f64::INFINITY;
    let mut iters = 0usize;
    for k in 0..max_iter {
        iters = k + 1;
        let fk = forward_kinematics(params, &q);
        let ex = target_x - fk.ee_x;
        let ey = target_y - fk.ee_y;
        err = (ex * ex + ey * ey).sqrt();
        if err <= tol_m {
            break;
        }
        let j = jacobian_ee(params, &q);
        // A = J J^T + lambda^2 I  (2x2), valid for any n
        let mut a00 = lambda * lambda;
        let mut a01 = 0.0;
        let mut a11 = lambda * lambda;
        for col in 0..n {
            let j0 = j.j_flat[col];
            let j1 = j.j_flat[n + col];
            a00 += j0 * j0;
            a01 += j0 * j1;
            a11 += j1 * j1;
        }
        let det = a00 * a11 - a01 * a01;
        if det.abs() < 1e-12 {
            break;
        }
        let inv00 = a11 / det;
        let inv01 = -a01 / det;
        let inv11 = a00 / det;
        let v0 = inv00 * ex + inv01 * ey;
        let v1 = inv01 * ex + inv11 * ey;
        for i in 0..n {
            q[i] += j.j_flat[i] * v0 + j.j_flat[n + i] * v1;
        }
    }
    let fk = forward_kinematics(params, &q);
    IkReport {
        q,
        ee_x: fk.ee_x,
        ee_y: fk.ee_y,
        iterations: iters,
        final_error_m: err,
        converged: err <= tol_m,
    }
}

fn mass_matrix(params: &SerialArmParams, q: &[f64]) -> Vec<f64> {
    let n = params.n();
    let thetas = cumulative_angles(q);
    let mut m = vec![0.0; n * n];
    for i in 0..n {
        for j in 0..n {
            let mut mij = 0.0;
            for k in i.max(j)..n {
                let ck = thetas[k].cos();
                let sk = thetas[k].sin();
                let px = -params.link_lengths[k] * sk;
                let py = params.link_lengths[k] * ck;
                mij += params.link_masses[k] * (px * px + py * py);
            }
            m[i * n + j] = mij;
            m[j * n + i] = mij;
        }
    }
    m
}

fn gravity_vector(params: &SerialArmParams, q: &[f64]) -> Vec<f64> {
    let n = params.n();
    let thetas = cumulative_angles(q);
    let mut gvec = vec![0.0; n];
    for j in 0..n {
        let mut gj = 0.0;
        for i in j..n {
            gj += params.link_masses[i] * params.g * params.link_lengths[i] * thetas[i].cos();
        }
        gvec[j] = gj;
    }
    gvec
}

fn kinetic_energy(params: &SerialArmParams, state: &SerialArmState) -> f64 {
    let n = params.n();
    let m = mass_matrix(params, &state.q);
    let mut ke = 0.0;
    for i in 0..n {
        for j in 0..n {
            ke += 0.5 * m[i * n + j] * state.q_dot[i] * state.q_dot[j];
        }
    }
    ke
}

fn potential_energy(params: &SerialArmParams, state: &SerialArmState) -> f64 {
    let thetas = cumulative_angles(&state.q);
    let mut pe = 0.0;
    for i in 0..params.n() {
        pe += params.link_masses[i] * params.g * params.link_lengths[i] * thetas[i].sin();
    }
    pe
}

fn solve_3x3(m: &[f64; 9], b: &[f64; 3]) -> [f64; 3] {
    let det = m[0] * (m[4] * m[8] - m[5] * m[7])
        - m[1] * (m[3] * m[8] - m[5] * m[6])
        + m[2] * (m[3] * m[7] - m[4] * m[6]);
    if det.abs() < 1e-12 {
        return [0.0, 0.0, 0.0];
    }
    let inv_det = 1.0 / det;
    [
        inv_det
            * (b[0] * (m[4] * m[8] - m[5] * m[7])
                + b[1] * (m[2] * m[7] - m[1] * m[8])
                + b[2] * (m[1] * m[5] - m[2] * m[4])),
        inv_det
            * (b[0] * (m[5] * m[6] - m[3] * m[8])
                + b[1] * (m[0] * m[8] - m[2] * m[6])
                + b[2] * (m[2] * m[3] - m[0] * m[5])),
        inv_det
            * (b[0] * (m[3] * m[7] - m[4] * m[6])
                + b[1] * (m[1] * m[6] - m[0] * m[7])
                + b[2] * (m[0] * m[4] - m[1] * m[3])),
    ]
}

pub fn symplectic_serial_arm_step(
    mut state: SerialArmState,
    params: &SerialArmParams,
    torques: &[f64],
    steps: usize,
    dt: f64,
) -> SymplecticReport {
    let n = params.n();
    let e0 = kinetic_energy(params, &state) + potential_energy(params, &state);
    let e0_abs = e0.abs().max(1e-9);
    let mut max_rel = 0.0_f64;

    for _ in 0..steps {
        let m_flat = mass_matrix(params, &state.q);
        let gvec = gravity_vector(params, &state.q);
        let mut m3 = [0.0; 9];
        for i in 0..n {
            for j in 0..n {
                m3[i * 3 + j] = m_flat[i * n + j];
            }
        }
        let mut rhs = [0.0; 3];
        for i in 0..n {
            rhs[i] = torques.get(i).copied().unwrap_or(0.0) - gvec[i];
        }
        let qdd = solve_3x3(&m3, &rhs);
        for i in 0..n {
            state.q_dot[i] += qdd[i] * dt;
            state.q[i] += state.q_dot[i] * dt;
        }
        let e = kinetic_energy(params, &state) + potential_energy(params, &state);
        max_rel = max_rel.max((e - e0).abs() / e0_abs);
    }

    SymplecticReport {
        steps,
        dt,
        energy0: e0,
        max_rel_drift: max_rel,
        final_state: state,
        backend_id: "serial_arm_planar_symplectic_v1".into(),
    }
}

pub fn fk_ik_roundtrip_error(
    params: &SerialArmParams,
    q_seed: &[f64],
) -> f64 {
    let fk = forward_kinematics(params, q_seed);
    let ik = inverse_kinematics_dls(params, fk.ee_x, fk.ee_y, q_seed, 80, 0.08, 1e-6);
    let fk2 = forward_kinematics(params, &ik.q);
    let dx = fk.ee_x - fk2.ee_x;
    let dy = fk.ee_y - fk2.ee_y;
    (dx * dx + dy * dy).sqrt()
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GraspForceReport {
    pub commanded_force_n: f64,
    pub allowed_max_force_n: f64,
    pub applied_force_n: f64,
    pub gripper_torque_nm: f64,
    pub force_limited: bool,
    pub ramp_complete: bool,
    pub backend_id: String,
}

/// Force-limited grasp ramp — teaching proxy maps normal force → gripper joint torque.
pub fn grasp_force_step(
    commanded_force_n: f64,
    allowed_max_force_n: f64,
    current_applied_force_n: f64,
    gripper_lever_arm_m: f64,
    ramp_rate_n_per_s: f64,
    dt: f64,
) -> GraspForceReport {
    let allowed = allowed_max_force_n.max(0.0);
    let capped_cmd = commanded_force_n.max(0.0).min(allowed);
    let delta = ramp_rate_n_per_s.max(0.0) * dt.max(0.0);
    let next = if capped_cmd > current_applied_force_n {
        (current_applied_force_n + delta).min(capped_cmd)
    } else if capped_cmd < current_applied_force_n {
        (current_applied_force_n - delta).max(capped_cmd)
    } else {
        capped_cmd
    };
    let force_limited = commanded_force_n > allowed + 1e-9;
    let gripper_torque_nm = next * gripper_lever_arm_m.max(1e-6);
    let ramp_complete = (next - capped_cmd).abs() < 1e-6;
    GraspForceReport {
        commanded_force_n,
        allowed_max_force_n: allowed,
        applied_force_n: next,
        gripper_torque_nm,
        force_limited,
        ramp_complete,
        backend_id: "serial_arm_planar_grasp_force_v1".into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn grasp_force_ramp_and_cap() {
        let r0 = grasp_force_step(30.0, 25.0, 0.0, 0.04, 200.0, 0.005);
        assert!(r0.force_limited);
        assert!(r0.applied_force_n <= 25.0 + 1e-9);
        let r1 = grasp_force_step(20.0, 25.0, 0.0, 0.04, 200.0, 0.1);
        assert!(r1.applied_force_n >= 19.9);
        assert!(r1.ramp_complete);
    }

    #[test]
    fn fk_reach_positive() {
        let p = SerialArmParams::scout_3dof_lunar();
        let fk = forward_kinematics(&p, &[0.3, 0.4, -0.2]);
        assert!(fk.ee_x.is_finite());
        assert!(fk.ee_y.is_finite());
    }

    #[test]
    fn fk_1dof_lc2_bench() {
        let p = SerialArmParams {
            link_lengths: vec![0.05],
            link_masses: vec![0.12],
            g: 9.81,
        };
        let fk = forward_kinematics(&p, &[0.35]);
        assert!((fk.ee_x - 0.05 * 0.35_f64.cos()).abs() < 1e-9);
        assert!((fk.ee_y - 0.05 * 0.35_f64.sin()).abs() < 1e-9);
    }
}
