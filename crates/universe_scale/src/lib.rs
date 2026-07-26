//! Native scale-bridge backends — Laplacian RG · operator RG (Liouville+dissipation).

pub mod linear;
pub mod negf_anchor;
pub mod negf_profiles;
pub mod operator_rg;
pub mod rg_galerkin;
pub mod spike;
pub mod spike_operator;

pub use spike::{run_spike, SpikeConfig, SpikeReport};
pub use spike_operator::{run_operator_spike, OperatorSpikeConfig, OperatorSpikeReport};