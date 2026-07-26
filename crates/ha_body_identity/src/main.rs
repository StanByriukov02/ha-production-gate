use clap::{Parser, Subcommand};
use ha_body_identity::{emit_body_identity_v1, hash_file, validate_body_identity_v1, SCHEMA};
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "ha-body-identity")]
#[command(about = "H-body (Chip x Body Identity) hash and validate")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// SHA-256 hex digest of file (stdout, hex only)
    Hash {
        #[arg(long)]
        file: PathBuf,
    },
    /// Validate body_identity_v1 JSON file (exit 0 = OK)
    Validate {
        #[arg(long)]
        json: PathBuf,
        /// If set, re-hash this body file and require match to identity
        #[arg(long)]
        file: Option<PathBuf>,
    },
    /// Emit body_identity_v1 JSON for a file
    Emit {
        #[arg(long)]
        file: PathBuf,
        #[arg(long)]
        kind: String,
        #[arg(long = "source-name")]
        source_name: String,
        #[arg(long = "chain-id")]
        chain_id: Option<String>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Hash { file } => {
            let hex = hash_file(&file).map_err(|e| format!("hash failed: {e}"))?;
            println!("{hex}");
        }
        Commands::Validate { json, file } => {
            let text = fs::read_to_string(&json).map_err(|e| format!("read json: {e}"))?;
            match validate_body_identity_v1(&text) {
                Ok(()) => {}
                Err(errors) => {
                    for e in &errors {
                        eprintln!("{e}");
                    }
                    return Err(String::new());
                }
            }
            if let Some(body_path) = file {
                let value: serde_json::Value =
                    serde_json::from_str(&text).map_err(|e| format!("json: {e}"))?;
                let want = value
                    .get("body_sha256")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| "missing body_sha256".to_string())?;
                let got = hash_file(&body_path).map_err(|e| format!("hash body: {e}"))?;
                if got != want {
                    return Err(format!("body_identity_mismatch: file={got} identity={want}"));
                }
                if let Some(want_len) = value.get("bytes_len").and_then(|v| v.as_u64()) {
                    let len = fs::metadata(&body_path)
                        .map_err(|e| format!("stat: {e}"))?
                        .len();
                    if len != want_len {
                        return Err(format!(
                            "body_identity_len_mismatch: file={len} identity={want_len}"
                        ));
                    }
                }
            }
            println!("OK");
        }
        Commands::Emit {
            file,
            kind,
            source_name,
            chain_id,
            out,
        } => {
            if kind.is_empty() {
                return Err("kind must be non-empty".into());
            }
            if source_name.is_empty() {
                return Err("source-name must be non-empty".into());
            }
            let data = fs::read(&file).map_err(|e| format!("read file: {e}"))?;
            let bytes_len = data.len() as u64;
            let body_sha256 = ha_body_identity::hash_bytes(&data);
            let value = emit_body_identity_v1(
                &body_sha256,
                bytes_len,
                &kind,
                &source_name,
                chain_id.as_deref(),
            );
            let pretty = serde_json::to_string_pretty(&value).map_err(|e| format!("json: {e}"))?;
            if let Some(out_path) = out {
                fs::write(&out_path, pretty.clone() + "\n")
                    .map_err(|e| format!("write out: {e}"))?;
            }
            println!("{pretty}");
            let _ = SCHEMA;
        }
    }
    Ok(())
}