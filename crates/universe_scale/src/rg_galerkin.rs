//! Laplacian network RG (Galerkin) vs naive MOR forward solves.

use crate::linear::{l2_norm, mat_mul, mat_vec_mul, solve_symmetric_positive_definite, transpose, vec_sub};
use crate::negf_anchor::{N_BLOCKS_TILE, N_SITES_FULL, SITES_PER_BLOCK};

const DVTH_SCALE: f64 = 10.0;

pub struct LaplacianProblem {
    pub l_fine: Vec<Vec<f64>>,
    pub b_fine: Vec<f64>,
}

fn gamma_at(profile: &[f64], i: usize) -> f64 {
    (1.0 + profile[i].abs() / DVTH_SCALE).max(0.25)
}

pub fn build_fine_laplacian(profile: &[f64]) -> LaplacianProblem {
    let n = N_SITES_FULL;
    let mut l = vec![vec![0.0; n]; n];
    let mut b = vec![0.0; n];

    // Dirichlet: phi[0] = 0
    l[0][0] = 1.0;
    b[0] = 0.0;

    for i in 1..n - 1 {
        let gl = gamma_at(profile, i - 1);
        let gr = gamma_at(profile, i);
        l[i][i - 1] = -gl;
        l[i][i] = gl + gr;
        l[i][i + 1] = -gr;
    }

    // Dirichlet: phi[n-1] = 1
    l[n - 1][n - 1] = 1.0;
    b[n - 1] = 1.0;

    LaplacianProblem {
        l_fine: l,
        b_fine: b,
    }
}

pub fn solve_fine(prob: &LaplacianProblem) -> Vec<f64> {
    solve_symmetric_positive_definite(&prob.l_fine, &prob.b_fine).expect("fine solve")
}

fn block_index(i: usize) -> usize {
    i / SITES_PER_BLOCK
}

pub fn build_restriction() -> Vec<Vec<f64>> {
    let mut r = vec![vec![0.0; N_SITES_FULL]; N_BLOCKS_TILE];
    let w = 1.0 / SITES_PER_BLOCK as f64;
    for k in 0..N_BLOCKS_TILE {
        let start = k * SITES_PER_BLOCK;
        for i in start..start + SITES_PER_BLOCK {
            r[k][i] = w;
        }
    }
    r
}

pub fn prolongate_piecewise_constant(x_c: &[f64]) -> Vec<f64> {
    (0..N_SITES_FULL)
        .map(|i| x_c[block_index(i)])
        .collect()
}

fn build_coarse_laplacian(gamma_c: &[f64]) -> (Vec<Vec<f64>>, Vec<f64>) {
    let nc = gamma_c.len();
    let mut l_c = vec![vec![0.0; nc]; nc];
    let mut b_c = vec![0.0; nc];
    l_c[0][0] = 1.0;
    b_c[0] = 0.0;
    if nc == 1 {
        return (l_c, b_c);
    }
    for i in 1..nc - 1 {
        let gl = gamma_c[i - 1];
        let gr = gamma_c[i];
        l_c[i][i - 1] = -gl;
        l_c[i][i] = gl + gr;
        l_c[i][i + 1] = -gr;
    }
    l_c[nc - 1][nc - 1] = 1.0;
    b_c[nc - 1] = 1.0;
    (l_c, b_c)
}

/// B1 naive MOR forward: average gamma per block, solve coarse chain, prolongate.
pub fn solve_naive_mor_forward(profile: &[f64]) -> Vec<f64> {
    let mut gamma_c = vec![0.0; N_BLOCKS_TILE];
    for k in 0..N_BLOCKS_TILE {
        let start = k * SITES_PER_BLOCK;
        let sum: f64 = (start..start + SITES_PER_BLOCK)
            .map(|i| gamma_at(profile, i))
            .sum();
        gamma_c[k] = sum / SITES_PER_BLOCK as f64;
    }
    let (l_c, b_c) = build_coarse_laplacian(&gamma_c);
    let x_c = solve_symmetric_positive_definite(&l_c, &b_c).expect("naive coarse solve");
    prolongate_piecewise_constant(&x_c)
}

/// B2 RG Galerkin: L_c = R L R^T, b_c = R b, x_hat = R^T x_c.
pub fn solve_rg_galerkin(prob: &LaplacianProblem) -> Vec<f64> {
    let r = build_restriction();
    let rt = transpose(&r);
    let l_c = mat_mul(&mat_mul(&r, &prob.l_fine), &rt);
    let b_c = mat_vec_mul(&r, &prob.b_fine);
    let x_c = solve_symmetric_positive_definite(&l_c, &b_c).expect("rg coarse solve");
    mat_vec_mul(&rt, &x_c)
}

pub fn anchor_interface_indices() -> Vec<usize> {
    let mut idx = Vec::new();
    for b in 0..N_BLOCKS_TILE - 1 {
        let boundary = (b + 1) * SITES_PER_BLOCK - 1;
        idx.push(boundary);
        idx.push(boundary + 1);
    }
    idx
}

pub fn field_metrics(x_fine: &[f64], x_hat: &[f64]) -> FieldMetrics {
    let diff = vec_sub(x_fine, x_hat);
    let rel_l2 = l2_norm(&diff) / l2_norm(x_fine).max(1e-12);
    let anchors = anchor_interface_indices();
    let mut anchor_errs = Vec::new();
    for &i in &anchors {
        anchor_errs.push((x_fine[i] - x_hat[i]).abs());
    }
    let anchor_max = anchor_errs.iter().copied().fold(0.0_f64, f64::max);
    let anchor_mean = if anchor_errs.is_empty() {
        0.0
    } else {
        anchor_errs.iter().sum::<f64>() / anchor_errs.len() as f64
    };
    FieldMetrics {
        rel_l2,
        anchor_max,
        anchor_mean,
    }
}

#[derive(Clone, Copy, Debug)]
pub struct FieldMetrics {
    pub rel_l2: f64,
    pub anchor_max: f64,
    pub anchor_mean: f64,
}

/// Vth proxy from solved potential + disorder (thermal coupling to device metric).
pub fn vth_from_field(x: &[f64], profile: &[f64]) -> f64 {
    let disorder_sum: f64 = profile.iter().sum();
    let phi_coupling: f64 = x
        .iter()
        .zip(profile.iter())
        .map(|(phi, d)| phi * d)
        .sum();
    crate::negf_anchor::BASELINE_MV + disorder_sum + phi_coupling
}
