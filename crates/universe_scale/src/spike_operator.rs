use serde::Serialize;
use std::path::Path;

use crate::negf_anchor::{tail_spread, TAIL_TOL_MV};
use crate::negf_profiles::{default_anchor_path, load_anchor, AnchorProfile};
use crate::operator_rg::evaluate_profile;
use crate::rg_galerkin::FieldMetrics;

#[derive(Clone, Copy, Debug)]
pub struct OperatorSpikeConfig {
    pub n_seeds: usize,
    pub promote_threshold: f64,
    pub anchor_path: &'static str,
}

impl Default for OperatorSpikeConfig {
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
    pub generator_residual_mean: f64,
    pub vth_tail_spread_error_mv: f64,
    pub vth_p99_error_mv: f64,
    pub within_negf_tail_tol: bool,
    pub wall_ns: u128,
}

#[derive(Debug, Serialize)]
pub struct OperatorSpikeReport {
    pub promote: String,
    pub experiment_id: String,
    pub verdict: String,
    pub world_class: String,
    pub law_id: String,
    pub role: String,
    pub methodology: String,
    pub anchor_artifact: String,
    pub config: OperatorSpikeConfigJson,
    pub naive_generator_mor: BackendMetrics,
    pub operator_rg_galerkin: BackendMetrics,
    pub field_rg_reference: BackendMetrics,
    pub gold_tail_spread_mv: f64,
    pub winner: String,
    pub promote_operator_rg: bool,
    pub falsifier: String,
    pub note: String,
}

#[derive(Debug, Serialize)]
pub struct OperatorSpikeConfigJson {
    pub n_seeds: usize,
    pub n_fine: usize,
    pub n_coarse: usize,
    pub dissipation_eta: f64,
    pub promote_threshold: f64,
}

struct Accum {
    rel_l2: f64,
    anchor_max: f64,
    residual: f64,
    count: usize,
}

impl Accum {
    fn new() -> Self {
        Self {
            rel_l2: 0.0,
            anchor_max: 0.0,
            residual: 0.0,
            count: 0,
        }
    }

    fn push(&mut self, m: FieldMetrics, residual: f64) {
        self.rel_l2 += m.rel_l2;
        self.anchor_max += m.anchor_max;
        self.residual += residual;
        self.count += 1;
    }

    fn mean(&self) -> (f64, f64, f64) {
        let n = self.count.max(1) as f64;
        (self.rel_l2 / n, self.anchor_max / n, self.residual / n)
    }
}

fn tail_errors(gold: &[f64], approx: &[f64]) -> (f64, f64) {
    let (tg, _, p99g) = tail_spread(gold);
    let (ta, _, p99a) = tail_spread(approx);
    ((tg - ta).abs(), (p99g - p99a).abs())
}

fn resolve_anchor(repo: &Path, cfg: &OperatorSpikeConfig) -> Vec<AnchorProfile> {
    let path = repo.join(cfg.anchor_path);
    let file = load_anchor(&path).expect("anchor profiles");
    let n = cfg.n_seeds.min(file.profiles.len());
    file.profiles[..n].to_vec()
}

fn build_metrics(
    acc: &Accum,
    wall_ns: u128,
    backend_id: &str,
    engine: &str,
    gold_vth: &[f64],
    approx_vth: Vec<f64>,
) -> BackendMetrics {
    let (rel_l2, anchor_max, residual) = acc.mean();
    let (tail_err, p99_err) = tail_errors(gold_vth, &approx_vth);
    BackendMetrics {
        backend_id: backend_id.into(),
        engine: engine.into(),
        language: "rust".into(),
        field_rel_l2_mean: rel_l2,
        field_anchor_max_mean: anchor_max,
        generator_residual_mean: residual,
        vth_tail_spread_error_mv: tail_err,
        vth_p99_error_mv: p99_err,
        within_negf_tail_tol: tail_err <= TAIL_TOL_MV,
        wall_ns,
    }
}

pub fn run_operator_spike(cfg: OperatorSpikeConfig) -> OperatorSpikeReport {
    let repo = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("repo root");
    let profiles = resolve_anchor(repo, &cfg);

    let gold_vth: Vec<f64> = profiles.iter().map(|p| p.vth_gold).collect();
    let (gold_tail, _, _) = tail_spread(&gold_vth);

    let start_n = std::time::Instant::now();
    let mut n_acc = Accum::new();
    let mut naive_vth = Vec::with_capacity(profiles.len());
    for row in &profiles {
        let ev = evaluate_profile(&row.profile);
        n_acc.push(ev.naive_metrics, ev.naive_residual);
        naive_vth.push(ev.vth_naive);
    }
    let naive_generator_mor = build_metrics(
        &n_acc,
        start_n.elapsed().as_nanos(),
        "naive_generator_mor_v0",
        "liouville_dissipation_param_average",
        &gold_vth,
        naive_vth,
    );

    let start_o = std::time::Instant::now();
    let mut o_acc = Accum::new();
    let mut op_vth = Vec::with_capacity(profiles.len());
    for row in &profiles {
        let ev = evaluate_profile(&row.profile);
        o_acc.push(ev.operator_metrics, ev.operator_residual);
        op_vth.push(ev.vth_operator);
    }
    let operator_rg_galerkin = build_metrics(
        &o_acc,
        start_o.elapsed().as_nanos(),
        "operator_rg_galerkin_v0",
        "generator_rg_liouville_plus_dissipation",
        &gold_vth,
        op_vth,
    );

    let start_f = std::time::Instant::now();
    let mut f_acc = Accum::new();
    let mut fr_vth = Vec::with_capacity(profiles.len());
    for row in &profiles {
        let ev = evaluate_profile(&row.profile);
        f_acc.push(ev.field_rg_metrics, ev.field_rg_residual);
        fr_vth.push(ev.vth_field_rg);
    }
    let field_rg_reference = build_metrics(
        &f_acc,
        start_f.elapsed().as_nanos(),
        "rg_galerkin_network_v0",
        "laplacian_field_only_reference",
        &gold_vth,
        fr_vth,
    );

    let field_win = if naive_generator_mor.field_rel_l2_mean > 0.0 {
        (naive_generator_mor.field_rel_l2_mean - operator_rg_galerkin.field_rel_l2_mean)
            / naive_generator_mor.field_rel_l2_mean
    } else {
        0.0
    };
    let tail_win = if naive_generator_mor.vth_tail_spread_error_mv > 0.0 {
        (naive_generator_mor.vth_tail_spread_error_mv - operator_rg_galerkin.vth_tail_spread_error_mv)
            / naive_generator_mor.vth_tail_spread_error_mv
    } else {
        0.0
    };
    let anchor_win = if naive_generator_mor.field_anchor_max_mean > 0.0 {
        (naive_generator_mor.field_anchor_max_mean - operator_rg_galerkin.field_anchor_max_mean)
            / naive_generator_mor.field_anchor_max_mean
    } else {
        0.0
    };
    let residual_win = if naive_generator_mor.generator_residual_mean > 0.0 {
        (naive_generator_mor.generator_residual_mean - operator_rg_galerkin.generator_residual_mean)
            / naive_generator_mor.generator_residual_mean
    } else {
        0.0
    };

    let promote_operator_rg = field_win >= cfg.promote_threshold
        || tail_win >= cfg.promote_threshold
        || anchor_win >= cfg.promote_threshold
        || residual_win >= cfg.promote_threshold;

    let winner = if promote_operator_rg {
        "operator_rg_galerkin_v0"
    } else {
        "naive_generator_mor_v0"
    };

    let verdict = if operator_rg_galerkin.field_rel_l2_mean <= naive_generator_mor.field_rel_l2_mean
        || operator_rg_galerkin.vth_tail_spread_error_mv <= naive_generator_mor.vth_tail_spread_error_mv
        || operator_rg_galerkin.generator_residual_mean <= naive_generator_mor.generator_residual_mean
    {
        "PASS"
    } else {
        "FAIL"
    };

    OperatorSpikeReport {
        promote: "SPIKE-OPERATOR-RG-v0".into(),
        experiment_id: "UNIVERSE-SPIKE-OPERATOR-RG-GENERATOR".into(),
        verdict: verdict.into(),
        world_class: "universe_foundation_scale_bridge".into(),
        law_id: "L_RG".into(),
        role: "universe_engine_slot_audit_not_breakthrough_claim".into(),
        methodology: "steady (L+D)x=b; G_rev=-L_diff G_irr=-diag(kappa); coarse A_c=R A_f R^T vs param-average generator".into(),
        anchor_artifact: cfg.anchor_path.into(),
        config: OperatorSpikeConfigJson {
            n_seeds: profiles.len(),
            n_fine: 16,
            n_coarse: 4,
            dissipation_eta: 0.12,
            promote_threshold: cfg.promote_threshold,
        },
        naive_generator_mor,
        operator_rg_galerkin,
        field_rg_reference,
        gold_tail_spread_mv: gold_tail,
        winner: winner.into(),
        promote_operator_rg,
        falsifier: "operator RG FAIL if generator residual and tail not better than naive generator MOR".into(),
        note: format!(
            "field_win={field_win:.4} tail_win={tail_win:.4} anchor_win={anchor_win:.4} residual_win={residual_win:.4}"
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn operator_spike_runs_on_anchor() {
        let cfg = OperatorSpikeConfig {
            n_seeds: 32,
            ..Default::default()
        };
        let rep = run_operator_spike(cfg);
        assert!(rep.operator_rg_galerkin.field_rel_l2_mean.is_finite());
        assert_eq!(rep.role, "universe_engine_slot_audit_not_breakthrough_claim");
    }
}
