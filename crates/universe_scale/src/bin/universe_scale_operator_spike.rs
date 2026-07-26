use universe_scale::{run_operator_spike, OperatorSpikeConfig};

fn main() {
    let report = run_operator_spike(OperatorSpikeConfig::default());
    println!("{}", serde_json::to_string_pretty(&report).expect("json"));
}
