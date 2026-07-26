//! NEGF tile anchor constants and tail statistics.

pub const N_SITES_FULL: usize = 16;
pub const N_BLOCKS_TILE: usize = 4;
pub const SITES_PER_BLOCK: usize = N_SITES_FULL / N_BLOCKS_TILE;
pub const BASELINE_MV: f64 = 400.0;
pub const TAIL_TOL_MV: f64 = 18.0;
pub const N_SEEDS: usize = 256;
pub const RNG_SEED: i64 = 20260615;

pub fn percentile(sorted_vals: &[f64], q: f64) -> f64 {
    if sorted_vals.is_empty() {
        return 0.0;
    }
    let idx = ((q * sorted_vals.len() as f64).ceil() as usize)
        .saturating_sub(1)
        .min(sorted_vals.len() - 1);
    sorted_vals[idx]
}

pub fn tail_spread(values: &[f64]) -> (f64, f64, f64) {
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p50 = percentile(&sorted, 0.5);
    let p99 = percentile(&sorted, 0.99);
    (p99 - p50, p50, p99)
}
