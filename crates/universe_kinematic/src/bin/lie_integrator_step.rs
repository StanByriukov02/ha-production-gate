//! CLI — one Lie SE(3) exp step (JSON stdin → JSON stdout).

use std::io::{self, Read};

use universe_kinematic::lie_se3_step::{lie_exp_step, LieStepInput};

fn main() {
    let mut buf = String::new();
    io::stdin()
        .read_to_string(&mut buf)
        .expect("read stdin");
    let inp: LieStepInput = serde_json::from_str(&buf).expect("parse input json");
    let out = lie_exp_step(&inp);
    let json = serde_json::to_string(&out).expect("serialize");
    println!("{json}");
}
