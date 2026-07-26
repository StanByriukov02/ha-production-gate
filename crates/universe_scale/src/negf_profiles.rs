//! Anchor profiles exported from Python exp_m1_02 (MT19937 parity).

use std::path::Path;

use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct AnchorFile {
    pub rng_seed: i64,
    pub n_seeds: usize,
    pub profiles: Vec<AnchorProfile>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct AnchorProfile {
    pub profile: Vec<f64>,
    pub vth_gold: f64,
    pub vth_heuristic: f64,
}

pub fn load_anchor(path: &Path) -> Result<AnchorFile, String> {
    let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

pub fn default_anchor_path() -> &'static str {
    "results/platform_bpass/universe/negf_spike_profiles_v1.json"
}
