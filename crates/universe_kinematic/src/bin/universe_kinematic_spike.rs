use std::env;

use universe_kinematic::{run_spike, SpikeConfig};

fn parse_f64(flag: &str, args: &[String], default: f64) -> f64 {
    for (i, a) in args.iter().enumerate() {
        if a == flag {
            if let Some(v) = args.get(i + 1) {
                return v.parse().unwrap_or(default);
            }
        }
    }
    default
}

fn parse_usize(flag: &str, args: &[String], default: usize) -> usize {
    for (i, a) in args.iter().enumerate() {
        if a == flag {
            if let Some(v) = args.get(i + 1) {
                return v.parse().unwrap_or(default);
            }
        }
    }
    default
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut cfg = SpikeConfig::default();
    cfg.steps = parse_usize("--steps", &args, cfg.steps);
    cfg.dt = parse_f64("--dt", &args, cfg.dt);
    cfg.shock_step = parse_usize("--shock-step", &args, cfg.shock_step);
    cfg.shock_impulse = parse_f64("--shock-impulse", &args, cfg.shock_impulse);
    let report = run_spike(cfg);
    let json = serde_json::to_string_pretty(&report).expect("json");
    println!("{json}");
}
