//! ha-world-join — stranger latch: Rust law --world-join + native rrbot FK.
//!
//! Python may *produce* Dual runs. This binary is the oracle that decides
//! whether the pack is world-robotics×physics honest.
//!
//! TABU: product_ready · MEASURED · Python as oracle.

use clap::Parser;
use ha_artifact_law::{emit_law_receipt_with, verify_artifact_root_with, VerifyOpts};
use serde_json::json;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, ExitCode, Stdio};

#[derive(Parser)]
#[command(name = "ha-world-join")]
#[command(about = "World robotics × physics — Rust oracle (not Python glue)")]
struct Cli {
    /// Pack or project root (must already contain Dual Safe∧Hostile runs)
    #[arg(long)]
    root: PathBuf,
    #[arg(long)]
    out: Option<PathBuf>,
    /// Also run native tree FK on fixtures/open_registry rrbot tree JSON
    #[arg(long, default_value_t = true)]
    kinematics: bool,
    /// Path to rrbot tree JSON (default: repo fixtures)
    #[arg(long)]
    tree: Option<PathBuf>,
    #[arg(long, default_value_t = false)]
    allow_fail: bool,
}

fn repo_root_from_cwd() -> PathBuf {
    // Walk up looking for Cargo.toml workspace
    let mut p = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    for _ in 0..8 {
        if p.join("Cargo.toml").is_file() && p.join("crates").is_dir() {
            return p;
        }
        if !p.pop() {
            break;
        }
    }
    PathBuf::from(".")
}

fn bin_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
}

/// Stranger kit: bins travel together. Prefer beside ha-world-join, then env, then repo.
fn kinematics_step_bin() -> Result<PathBuf, String> {
    let name = if cfg!(windows) {
        "manipulator_kinematics_step.exe"
    } else {
        "manipulator_kinematics_step"
    };
    if let Ok(env) = std::env::var("HA_KINEMATICS_BIN") {
        let p = PathBuf::from(env);
        if p.is_file() {
            return Ok(p);
        }
        return Err(format!("HA_KINEMATICS_BIN set but missing: {}", p.display()));
    }
    let beside = bin_dir().join(name);
    if beside.is_file() {
        return Ok(beside);
    }
    let repo = repo_root_from_cwd()
        .join("target")
        .join("release")
        .join(name);
    if repo.is_file() {
        return Ok(repo);
    }
    Err(
        "manipulator_kinematics_step missing — place beside ha-world-join, set HA_KINEMATICS_BIN, or cargo build -p universe_kinematic --release --bin manipulator_kinematics_step"
            .into(),
    )
}

fn run_rrbot_fk(tree_path: &PathBuf) -> Result<serde_json::Value, String> {
    let tree: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(tree_path).map_err(|e| format!("read tree: {e}"))?,
    )
    .map_err(|e| format!("tree json: {e}"))?;
    let mut input = tree.clone();
    if let Some(obj) = input.as_object_mut() {
        obj.insert("op".into(), json!("fk_tree_se3"));
        if !obj.contains_key("q_by_name") {
            obj.insert(
                "q_by_name".into(),
                json!({"joint1": 0.2, "joint2": -0.3}),
            );
        }
        if !obj.contains_key("target_link") {
            obj.insert("target_link".into(), json!("tool_link"));
        }
        if !obj.contains_key("root_link") {
            obj.insert("root_link".into(), json!("base_link"));
        }
    }
    let bin = kinematics_step_bin()?;

    let mut child = Command::new(&bin)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("spawn manipulator_kinematics_step ({}): {e}", bin.display()))?;
    {
        let mut stdin = child.stdin.take().ok_or("stdin")?;
        stdin
            .write_all(input.to_string().as_bytes())
            .map_err(|e| format!("write stdin: {e}"))?;
    }
    let out = child
        .wait_with_output()
        .map_err(|e| format!("wait kinematics: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "kinematics FAIL rc={:?} stderr={}",
            out.status.code(),
            String::from_utf8_lossy(&out.stderr)
        ));
    }
    serde_json::from_slice(&out.stdout).map_err(|e| format!("kinematics json: {e}"))
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => code,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<ExitCode, String> {
    let cli = Cli::parse();
    let opts = VerifyOpts {
        world_join: true,
        ..VerifyOpts::default()
    };
    let result = verify_artifact_root_with(&cli.root, &opts);
    let mut receipt = emit_law_receipt_with(&cli.root, &result, &opts);

    let mut kin_ok = true;
    let mut kin_val = json!(null);
    if cli.kinematics {
        let tree = cli.tree.unwrap_or_else(|| {
            repo_root_from_cwd()
                .join("fixtures")
                .join("open_registry")
                .join("kinematics")
                .join("ros_rrbot_tree_se3_v1.json")
        });
        match run_rrbot_fk(&tree) {
            Ok(v) => {
                kin_val = v;
                let verdict = kin_val
                    .get("verdict")
                    .and_then(|x| x.as_str())
                    .unwrap_or("");
                kin_ok = verdict == "MANIPULATOR_FK_TREE_SE3_PASS";
            }
            Err(e) => {
                kin_ok = false;
                kin_val = json!({"ok": false, "error": e});
            }
        }
        if let Some(obj) = receipt.as_object_mut() {
            obj.insert(
                "native_kinematics".into(),
                json!({
                    "robot": "ros_rrbot_tree_se3_v1",
                    "ok": kin_ok,
                    "result": kin_val,
                    "oracle": "manipulator_kinematics_step"
                }),
            );
        }
    }

    let out_path = cli
        .out
        .unwrap_or_else(|| cli.root.join("WORLD_JOIN_LAW_RECEIPT_v1.json"));
    let pretty = serde_json::to_string_pretty(&receipt).map_err(|e| e.to_string())?;
    std::fs::create_dir_all(out_path.parent().unwrap_or(cli.root.as_path()))
        .map_err(|e| e.to_string())?;
    std::fs::write(&out_path, pretty.clone() + "\n").map_err(|e| e.to_string())?;
    println!("{pretty}");

    let ok = result.ok && kin_ok;
    if ok || cli.allow_fail {
        if ok {
            eprintln!("WORLD_JOIN PASS — Rust law + native kinematics");
        }
        Ok(ExitCode::SUCCESS)
    } else {
        Err(format!(
            "WORLD_JOIN FAIL law_ok={} kin_ok={} errors={}",
            result.ok,
            kin_ok,
            result.errors.join(", ")
        ))
    }
}
