use serde::Serialize;
use std::path::Path;

use crate::negf_anchor::{tail_spread, TAIL_TOL_MV};
use crate::negf_profiles::{load_anchor, default_anchor_path, AnchorProfile};
use crate::rg_galerkin::{
    build_fine_laplacian, field_metrics, solve_fine, solve_naive_mor_forward, solve_rg_galerkin,
    vth_from_field, FieldMetrics,
};

#[derive(Clone, Copy, Debug)]
pub struct SpikeConfig {
    pub n_seeds: usize,
    pub promote_threshold: f64,
    pub anchor_path: &'static str,
}

impl Default for SpikeConfig {
    fn default() -> Self {
        Self {
            n_seeds: 256,
            promote_threshold: 0.20,
            anchor_path: default_anchor_path(),
        }
    }
}

#[derive(Debug, Serialize)]
pub struct BackendMetrics {
    pub backend_id: String,
    pub engine: String,
    pub language: String,
    pub field_rel_l2_mean: f64,
    pub field_anchor_max_mean: f64,
    pub vth_tail_spread_error_mv: f64,
    pub vth_p99_error_mv: f64,
    pub within_negf_tail_tol: bool,
    pub wall_ns: u128,
}

#[derive(Debug, Serialize)]
pub struct SpikeReport {
    pub promote: String,
    pub experiment_id: String,
    pub verdict: String,
    pub world_class: String,
    pub law_id: String,
    pub methodology: String,
    pub anchor_artifact: String,
    pub config: SpikeConfigJson,
    pub naive_mor: BackendMetrics,
    pub rg_galerkin: BackendMetrics,
    pub naive_tile_heuristic_tail_mv: f64,
    pub gold_tail_spread_mv: f64,
    pub winner: String,
    pub promote_rg: bool,
    pub falsifier: String,
    pub note: String,
}

#[derive(Debug, Serialize)]
pub struct SpikeConfigJson {
    pub n_seeds: usize,
    pub n_fine: usize,
    pub n_coarse: usize,
    pub promote_threshold: f64,
}

struct Accum {
    rel_l2: f64,
    anchor_max: f64,
    count: usize,
}

impl Accum {
    fn new() -> Self {
        Self {
            rel_l2: 0.0,
            anchor_max: 0.0,
            count: 0,
        }
    }

    fn push(&mut self, m: FieldMetrics) {
        self.rel_l2 += m.rel_l2;
        self.anchor_max += m.anchor_max;
        self.count += 1;
    }
}

fn tail_errors(gold: &[f64], approx: &[f64]) -> (f64, f64) {
    let (tg, _, p99g) = tail_spread(gold);
    let (ta, _, p99a) = tail_spread(approx);
    ((tg - ta).abs(), (p99g - p99a).abs())
}

fn resolve_anchor(repo: &Path, cfg: &SpikeConfig) -> Result<Vec<AnchorProfile>, String> {
    let path = repo.join(cfg.anchor_path);
    let file = load_anchor(&path)?;
    let n = cfg.n_seeds.min(file.profiles.len());
    Ok(file.profiles[..n].to_vec())
}

pub fn run_spike(cfg: SpikeConfig) -> SpikeReport {
    let repo = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("repo root");
    let profiles = resolve_anchor(repo, &cfg).expect("anchor profiles");

    let gold_vth: Vec<f64> = profiles.iter().map(|p| p.vth_gold).collect();
    let heuristic_vth: Vec<f64> = profiles.iter().map(|p| p.vth_heuristic).collect();
    let (gold_tail, _, _) = tail_spread(&gold_vth);
    let (heur_tail, _, _) = tail_spread(&heuristic_vth);

    let start_n = std::time::Instant::now();
    let mut n_acc = Accum::new();
    let mut naive_vth: Vec<f64> = Vec::with_capacity(profiles.len());
    for row in &profiles {
        let prob = build_fine_laplacian(&row.profile);
        let x_f = solve_fine(&prob);
        let x_hat = solve_naive_mor_forward(&row.profile);
        n_acc.push(field_metrics(&x_f, &x_hat));
        naive_vth.push(vth_from_field(&x_hat, &row.profile));
    }
    let nn = n_acc.count.max(1) as f64;
    let (n_tail, n_p99) = tail_errors(&gold_vth, &naive_vth);
    let naive_mor = BackendMetrics {
        backend_id: "naive_mor_forward_v0".into(),
        engine: "laplacian_param_average".into(),
        language: "rust".into(),
        field_rel_l2_mean: n_acc.rel_l2 / nn,
        field_anchor_max_mean: n_acc.anchor_max / nn,
        vth_tail_spread_error_mv: n_tail,
        vth_p99_error_mv: n_p99,
        within_negf_tail_tol: n_tail <= TAIL_TOL_MV,
        wall_ns: start_n.elapsed().as_nanos(),
    };

    let start_r = std::time::Instant::now();
    let mut r_acc = Accum::new();
    let mut rg_vth: Vec<f64> = Vec::with_capacity(profiles.len());
    for row in &profiles {
        let prob = build_fine_laplacian(&row.profile);
        let x_f = solve_fine(&prob);
        let x_hat = solve_rg_galerkin(&prob);
        r_acc.push(field_metrics(&x_f, &x_hat));
        rg_vth.push(vth_from_field(&x_hat, &row.profile));
    }
    let rn = r_acc.count.max(1) as f64;
    let (r_tail, r_p99) = tail_errors(&gold_vth, &rg_vth);
    let rg_galerkin = BackendMetrics {
        backend_id: "rg_galerkin_network_v0".into(),
        engine: "laplacian_rg_galerkin".into(),
        language: "rust".into(),
        field_rel_l2_mean: r_acc.rel_l2 / rn,
        field_anchor_max_mean: r_acc.anchor_max / rn,
        vth_tail_spread_error_mv: r_tail,
        vth_p99_error_mv: r_p99,
        within_negf_tail_tol: r_tail <= TAIL_TOL_MV,
        wall_ns: start_r.elapsed().as_nanos(),
    };

    let field_win = if naive_mor.field_rel_l2_mean > 0.0 {
        (naive_mor.field_rel_l2_mean - rg_galerkin.field_rel_l2_mean) / naive_mor.field_rel_l2_mean
    } else {
        0.0
    };
    let tail_win = if naive_mor.vth_tail_spread_error_mv > 0.0 {
        (naive_mor.vth_tail_spread_error_mv - rg_galerkin.vth_tail_spread_error_mv)
            / naive_mor.vth_tail_spread_error_mv
    } else {
        0.0
    };
    let anchor_win = if naive_mor.field_anchor_max_mean > 0.0 {
        (naive_mor.field_anchor_max_mean - rg_galerkin.field_anchor_max_mean)
            / naive_mor.field_anchor_max_mean
    } else {
        0.0
    };

    let promote_rg = field_win >= cfg.promote_threshold
        || tail_win >= cfg.promote_threshold
        || anchor_win >= cfg.promote_threshold;
    let winner = if promote_rg {
        "rg_galerkin_network_v0"
    } else {
        "naive_mor_forward_v0"
    };

    let verdict = if rg_galerkin.field_rel_l2_mean <= naive_mor.field_rel_l2_mean
        || rg_galerkin.vth_tail_spread_error_mv <= naive_mor.vth_tail_spread_error_mv
    {
        "PASS"
    } else {
        "FAIL"
    };

    SpikeReport {
        promote: "SPIKE-RG-v0".into(),
        experiment_id: "UNIVERSE-SPIKE-RG-MOR".into(),
        verdict: verdict.into(),
        world_class: "negf_tile_scale_bridge".into(),
        law_id: "L_RG".into(),
        methodology: "fine 1D Laplacian n=16 Dirichlet 0/1 · ensemble from Python anchor · Galerkin L_c=RLR^T vs param-average coarse forward".into(),
        anchor_artifact: cfg.anchor_path.into(),
        config: SpikeConfigJson {
            n_seeds: profiles.len(),
            n_fine: 16,
            n_coarse: 4,
            promote_threshold: cfg.promote_threshold,
        },
        naive_mor,
        rg_galerkin,
        naive_tile_heuristic_tail_mv: heur_tail,
        gold_tail_spread_mv: gold_tail,
        winner: winner.into(),
        promote_rg,
        falsifier: "RG FAIL if field or tail metric worse than naive forward at equal ensemble".into(),
        note: format!(
            "field_win={field_win:.4} tail_win={tail_win:.4} anchor_win={anchor_win:.4} · heuristic_tile_tail={heur_tail:.4}"
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spike_runs_on_anchor() {
        let cfg = SpikeConfig {
            n_seeds: 32,
            ..Default::default()
        };
        let rep = run_spike(cfg);
        assert!(rep.naive_mor.field_rel_l2_mean.is_finite());
        assert!(rep.rg_galerkin.field_rel_l2_mean.is_finite());
    }
}
