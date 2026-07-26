//! Generator RG — coarsen Liouville + dissipation operator, not Laplacian field only.
//!
//! Fine evolution (toy metriplectic split):
//!   dx/dt = G_rev x + G_irr x + s  ,  G_rev = -L_diff  ,  G_irr = -diag(kappa)
//! Steady state: (L + D) x = b  with Dirichlet rows pinned.

use crate::linear::{
    l2_norm, mat_mul, mat_vec_mul, solve_symmetric_positive_definite, transpose, vec_sub,
};
use crate::negf_anchor::{N_BLOCKS_TILE, N_SITES_FULL, SITES_PER_BLOCK};
use crate::rg_galerkin::{
    build_fine_laplacian, build_restriction, field_metrics, prolongate_piecewise_constant,
    vth_from_field, FieldMetrics, LaplacianProblem,
};

const DVTH_SCALE: f64 = 10.0;
/// Irreversible relaxation strength relative to diffusive coupling.
const DISSIPATION_ETA: f64 = 0.12;

pub struct GeneratorProblem {
    pub l_diff: Vec<Vec<f64>>,
    pub kappa: Vec<f64>,
    pub a_steady: Vec<Vec<f64>>,
    pub b: Vec<f64>,
}

fn gamma_at(profile: &[f64], i: usize) -> f64 {
    (1.0 + profile[i].abs() / DVTH_SCALE).max(0.25)
}

fn add_diagonal(a: &mut [Vec<f64>], kappa: &[f64]) {
    for i in 0..a.len() {
        a[i][i] += kappa[i];
    }
}

pub fn build_fine_generator(profile: &[f64]) -> GeneratorProblem {
    let lap = build_fine_laplacian(profile);
    let n = N_SITES_FULL;
    let mut kappa = vec![0.0; n];
    for i in 1..n - 1 {
        kappa[i] = DISSIPATION_ETA * gamma_at(profile, i);
    }
    let mut a_steady = lap.l_fine.clone();
    add_diagonal(&mut a_steady, &kappa);
    GeneratorProblem {
        l_diff: lap.l_fine,
        kappa,
        a_steady,
        b: lap.b_fine,
    }
}

pub fn solve_steady(prob: &GeneratorProblem) -> Vec<f64> {
    solve_symmetric_positive_definite(&prob.a_steady, &prob.b).expect("fine generator steady")
}

pub fn generator_residual(prob: &GeneratorProblem, x: &[f64]) -> f64 {
    let ax = mat_vec_mul(&prob.a_steady, x);
    let res = vec_sub(&ax, &prob.b);
    l2_norm(&res) / l2_norm(&prob.b).max(1e-12)
}

fn block_gamma_kappa_avgs(profile: &[f64]) -> (Vec<f64>, Vec<f64>) {
    let mut gamma_c = vec![0.0; N_BLOCKS_TILE];
    let mut kappa_c = vec![0.0; N_BLOCKS_TILE];
    for k in 0..N_BLOCKS_TILE {
        let start = k * SITES_PER_BLOCK;
        let mut g_sum = 0.0;
        let mut k_sum = 0.0;
        for i in start..start + SITES_PER_BLOCK {
            let g = gamma_at(profile, i);
            g_sum += g;
            k_sum += DISSIPATION_ETA * g;
        }
        gamma_c[k] = g_sum / SITES_PER_BLOCK as f64;
        kappa_c[k] = k_sum / SITES_PER_BLOCK as f64;
    }
    (gamma_c, kappa_c)
}

fn build_coarse_chain(gamma_c: &[f64], kappa_c: &[f64]) -> (Vec<Vec<f64>>, Vec<f64>) {
    let nc = gamma_c.len();
    let mut a = vec![vec![0.0; nc]; nc];
    let mut b = vec![0.0; nc];
    a[0][0] = 1.0;
    b[0] = 0.0;
    if nc == 1 {
        return (a, b);
    }
    for i in 1..nc - 1 {
        let gl = gamma_c[i - 1];
        let gr = gamma_c[i];
        a[i][i - 1] = -gl;
        a[i][i] = gl + gr + kappa_c[i];
        a[i][i + 1] = -gr;
    }
    a[nc - 1][nc - 1] = 1.0;
    b[nc - 1] = 1.0;
    (a, b)
}

/// B1 naive generator MOR: average gamma+kappa per block, assemble coarse generator, prolongate.
pub fn solve_naive_generator_mor(profile: &[f64]) -> Vec<f64> {
    let (gamma_c, kappa_c) = block_gamma_kappa_avgs(profile);
    let (a_c, b_c) = build_coarse_chain(&gamma_c, &kappa_c);
    let x_c = solve_symmetric_positive_definite(&a_c, &b_c).expect("naive generator coarse");
    prolongate_piecewise_constant(&x_c)
}

/// B2 operator RG: A_c = R A_f R^T, b_c = R b, x_hat = R^T x_c.
pub fn solve_operator_rg_galerkin(prob: &GeneratorProblem) -> Vec<f64> {
    let r = build_restriction();
    let rt = transpose(&r);
    let a_c = mat_mul(&mat_mul(&r, &prob.a_steady), &rt);
    let b_c = mat_vec_mul(&r, &prob.b);
    let x_c = solve_symmetric_positive_definite(&a_c, &b_c).expect("operator rg coarse");
    mat_vec_mul(&rt, &x_c)
}

/// Reference: field-only RG on Laplacian (previous spike — not generator).
pub fn solve_field_rg_reference(lap: &LaplacianProblem) -> Vec<f64> {
    let r = build_restriction();
    let rt = transpose(&r);
    let l_c = mat_mul(&mat_mul(&r, &lap.l_fine), &rt);
    let b_c = mat_vec_mul(&r, &lap.b_fine);
    let x_c = solve_symmetric_positive_definite(&l_c, &b_c).expect("field rg");
    mat_vec_mul(&rt, &x_c)
}

pub fn evaluate_profile(profile: &[f64]) -> ProfileEval {
    let prob = build_fine_generator(profile);
    let x_gold = solve_steady(&prob);
    let lap = build_fine_laplacian(profile);
    let x_naive = solve_naive_generator_mor(profile);
    let x_op = solve_operator_rg_galerkin(&prob);
    let x_field_rg = solve_field_rg_reference(&lap);
    let naive_metrics = field_metrics(&x_gold, &x_naive);
    let operator_metrics = field_metrics(&x_gold, &x_op);
    let field_rg_metrics = field_metrics(&x_gold, &x_field_rg);
    let naive_residual = generator_residual(&prob, &x_naive);
    let operator_residual = generator_residual(&prob, &x_op);
    let field_rg_residual = generator_residual(&prob, &x_field_rg);
    let vth_gold = vth_from_field(&x_gold, profile);
    let vth_naive = vth_from_field(&x_naive, profile);
    let vth_operator = vth_from_field(&x_op, profile);
    let vth_field_rg = vth_from_field(&x_field_rg, profile);
    ProfileEval {
        gold: x_gold,
        naive_generator: x_naive,
        operator_rg: x_op,
        field_rg: x_field_rg,
        naive_metrics,
        operator_metrics,
        field_rg_metrics,
        naive_residual,
        operator_residual,
        field_rg_residual,
        vth_gold,
        vth_naive,
        vth_operator,
        vth_field_rg,
    }
}

pub struct ProfileEval {
    pub gold: Vec<f64>,
    pub naive_generator: Vec<f64>,
    pub operator_rg: Vec<f64>,
    pub field_rg: Vec<f64>,
    pub naive_metrics: FieldMetrics,
    pub operator_metrics: FieldMetrics,
    pub field_rg_metrics: FieldMetrics,
    pub naive_residual: f64,
    pub operator_residual: f64,
    pub field_rg_residual: f64,
    pub vth_gold: f64,
    pub vth_naive: f64,
    pub vth_operator: f64,
    pub vth_field_rg: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn operator_rg_runs() {
        let profile = vec![0.1; N_SITES_FULL];
        let ev = evaluate_profile(&profile);
        assert!(ev.operator_metrics.rel_l2.is_finite());
        assert!(ev.operator_residual.is_finite());
    }
}
