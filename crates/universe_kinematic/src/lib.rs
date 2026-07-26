//! Native kinematic backends for universe kernel spike #6.
//! Python is glue only — this crate is the CGA-class engine slot.

pub mod cga_rotor3;
pub mod lie_multibody_double_pendulum;
pub mod lie_se3_step;
pub mod serial_arm_planar;
pub mod serial_chain_se3;
pub mod kinematic_tree_se3;
pub mod spike;
pub mod symplectic_euler;

pub use spike::{run_spike, SpikeConfig, SpikeReport};
