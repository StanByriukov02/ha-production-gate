//! JSON stdin/stdout — 2-link double pendulum symplectic energy drift probe.

use serde::{Deserialize, Serialize};
use std::io::{self, Read};

use universe_kinematic::lie_multibody_double_pendulum::{
    symplectic_double_pendulum_chain, DoublePendulumParams, DoublePendulumState,
};

#[derive(Deserialize)]
struct Input {
    steps: usize,
    dt: f64,
    theta1: f64,
    theta2: f64,
    theta1_dot: f64,
    theta2_dot: f64,
}

#[derive(Serialize)]
struct Output {
    verdict: String,
    report: universe_kinematic::lie_multibody_double_pendulum::DoublePendulumEnergyReport,
}

fn main() {
    let mut buf = String::new();
    io::stdin().read_to_string(&mut buf).expect("stdin");
    let inp: Input = serde_json::from_str(&buf).expect("json");
    let state = DoublePendulumState {
        theta1: inp.theta1,
        theta2: inp.theta2,
        theta1_dot: inp.theta1_dot,
        theta2_dot: inp.theta2_dot,
    };
    let report = symplectic_double_pendulum_chain(state, &DoublePendulumParams::default(), inp.steps, inp.dt);
    let pass = report.max_rel_drift <= 0.45;
    let out = Output {
        verdict: if pass {
            "LIE_MULTIBODY_G5_PASS".into()
        } else {
            "LIE_MULTIBODY_G5_FAIL".into()
        },
        report,
    };
    println!("{}", serde_json::to_string(&out).expect("serialize"));
}
