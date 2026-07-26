use universe_scale::{run_spike, SpikeConfig};

fn main() {
    let report = run_spike(SpikeConfig::default());
    println!("{}", serde_json::to_string_pretty(&report).expect("json"));
}
