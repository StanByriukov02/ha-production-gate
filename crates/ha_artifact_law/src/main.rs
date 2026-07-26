use clap::{Parser, Subcommand};
use ha_artifact_law::{
    emit_law_receipt_with, verify_artifact_root_with, VerifyOpts, SCHEMA,
};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "ha-artifact-law")]
#[command(about = "Artifact Existence Law — Rust aggregator oracle")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Verify project or pack root; write LAW_RECEIPT_v1.json
    Verify {
        #[arg(long)]
        root: PathBuf,
        #[arg(long)]
        out: Option<PathBuf>,
        /// Exit 0 even on FAIL (still write receipt) — for inspect
        #[arg(long, default_value_t = false)]
        allow_fail: bool,
        /// FAIL if IRON_ATTESTATION_v1 missing / invalid (H10 BYO socket)
        #[arg(long, default_value_t = false)]
        require_iron: bool,
        /// Path to IRON_ATTESTATION_v1.json (default: root or interop/)
        #[arg(long)]
        iron: Option<PathBuf>,
        /// Reject soft_stub backend (orgs that only accept real OTP provider)
        #[arg(long, default_value_t = false)]
        reject_soft_stub: bool,
        /// World robotics × physics: body + closed_loop + soil Dual falsifier (Rust oracle)
        #[arg(long, default_value_t = false)]
        world_join: bool,
    },
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
    match cli.command {
        Commands::Verify {
            root,
            out,
            allow_fail,
            require_iron,
            iron,
            reject_soft_stub,
            world_join,
        } => {
            let out_path = out.unwrap_or_else(|| root.join("LAW_RECEIPT_v1.json"));
            let opts = VerifyOpts {
                require_iron,
                reject_soft_stub,
                iron_path: iron,
                world_join,
            };
            let result = verify_artifact_root_with(&root, &opts);
            let receipt = emit_law_receipt_with(&root, &result, &opts);
            let pretty =
                serde_json::to_string_pretty(&receipt).map_err(|e| e.to_string())?;
            std::fs::create_dir_all(out_path.parent().unwrap_or(root.as_path()))
                .map_err(|e| e.to_string())?;
            std::fs::write(&out_path, pretty.clone() + "\n").map_err(|e| e.to_string())?;
            println!("{pretty}");
            let _ = SCHEMA;
            if result.ok || allow_fail {
                Ok(ExitCode::SUCCESS)
            } else {
                Err(format!(
                    "ARTIFACT_EXISTENCE_LAW FAIL: {}",
                    result.errors.join(", ")
                ))
            }
        }
    }
}
