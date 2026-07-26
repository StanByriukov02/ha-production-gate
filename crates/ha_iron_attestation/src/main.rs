use clap::{Parser, Subcommand};
use ha_iron_attestation::{
    check_iron_at_root, check_reuse_bar, emit_soft_stub_from_fuse, find_attestation_path, FILENAME,
};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "ha-iron-attestation")]
#[command(about = "H10 BYO iron socket — soft stub + validate (not OTP)")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Emit soft-stub attestation from SE_FUSE.bin (CI / local bridge)
    Stub {
        #[arg(long)]
        fuse: PathBuf,
        #[arg(long)]
        out: Option<PathBuf>,
        #[arg(long)]
        body_sha256: Option<String>,
        #[arg(long)]
        challenge: Option<String>,
    },
    /// Validate attestation at path or under root
    Validate {
        #[arg(long)]
        root: Option<PathBuf>,
        #[arg(long)]
        attestation: Option<PathBuf>,
        #[arg(long, default_value_t = false)]
        require_iron: bool,
        #[arg(long, default_value_t = false)]
        reject_soft_stub: bool,
    },
    /// Soft reuse bar — same body + iron across two packs/bots
    ReuseCheck {
        #[arg(long)]
        a: PathBuf,
        #[arg(long)]
        b: PathBuf,
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
        Commands::Stub {
            fuse,
            out,
            body_sha256,
            challenge,
        } => {
            let doc = emit_soft_stub_from_fuse(
                &fuse,
                body_sha256.as_deref(),
                challenge.as_deref(),
            )?;
            let out_path = out.unwrap_or_else(|| {
                fuse.parent()
                    .unwrap_or_else(|| std::path::Path::new("."))
                    .join(FILENAME)
            });
            if let Some(parent) = out_path.parent() {
                std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            let pretty = serde_json::to_string_pretty(&doc).map_err(|e| e.to_string())?;
            std::fs::write(&out_path, pretty.clone() + "\n").map_err(|e| e.to_string())?;
            println!("{pretty}");
            Ok(ExitCode::SUCCESS)
        }
        Commands::Validate {
            root,
            attestation,
            require_iron,
            reject_soft_stub,
        } => {
            let root = root.unwrap_or_else(|| PathBuf::from("."));
            let explicit = attestation.or_else(|| find_attestation_path(&root, None));
            let result = check_iron_at_root(
                &root,
                explicit.as_deref(),
                require_iron,
                reject_soft_stub,
            );
            let receipt = serde_json::json!({
                "schema": "iron_check_v1",
                "ok": result.ok || (!require_iron && !result.present),
                "present": result.present,
                "backend": result.backend,
                "provider_id": result.provider_id,
                "path": result.path.as_ref().map(|p| p.display().to_string()),
                "errors": result.errors,
            });
            println!("{}", serde_json::to_string_pretty(&receipt).unwrap());
            let pass = if require_iron {
                result.ok
            } else if result.present {
                result.ok
            } else {
                true
            };
            if pass {
                Ok(ExitCode::SUCCESS)
            } else {
                Err(format!("IRON FAIL: {}", result.errors.join(", ")))
            }
        }
        Commands::ReuseCheck { a, b } => match check_reuse_bar(&a, &b) {
            Ok(doc) => {
                println!("{}", serde_json::to_string_pretty(&doc).unwrap());
                Ok(ExitCode::SUCCESS)
            }
            Err(errs) => {
                let doc = serde_json::json!({
                    "schema": "iron_reuse_bar_v1",
                    "ok": false,
                    "errors": errs,
                });
                println!("{}", serde_json::to_string_pretty(&doc).unwrap());
                Err(format!("REUSE FAIL: {}", errs.join(", ")))
            }
        },
    }
}
