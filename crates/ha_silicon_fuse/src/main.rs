use clap::{Parser, Subcommand};
use ha_silicon_fuse::{
    fuse_bind_body, fuse_blow, fuse_current_allowed, fuse_ensure, fuse_status,
    validate_silicon_fuse_json, SCHEMA,
};
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "ha-silicon-fuse")]
#[command(about = "H6-iron C eFUSE / secure-element apoptosis oracle")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Ensure {
        #[arg(long)]
        fuse: PathBuf,
    },
    Status {
        #[arg(long)]
        fuse: PathBuf,
    },
    Blow {
        #[arg(long)]
        fuse: PathBuf,
        #[arg(long = "lie-score", default_value_t = 0.0)]
        lie_score: f64,
    },
    BindBody {
        #[arg(long)]
        fuse: PathBuf,
        #[arg(long = "body-sha256")]
        body_sha256: String,
    },
    /// Print 1 if current may flow, 0 if blocked
    CurrentGate {
        #[arg(long)]
        fuse: PathBuf,
    },
    Validate {
        #[arg(long)]
        json: PathBuf,
    },
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            if !e.is_empty() {
                eprintln!("{e}");
            }
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Ensure { fuse } => {
            fuse_ensure(&fuse)?;
            println!("OK");
            let _ = SCHEMA;
        }
        Commands::Status { fuse } => {
            let v = fuse_status(&fuse)?;
            println!("{}", serde_json::to_string_pretty(&v).map_err(|e| e.to_string())?);
        }
        Commands::Blow { fuse, lie_score } => {
            let v = fuse_blow(&fuse, lie_score)?;
            println!("{}", serde_json::to_string_pretty(&v).map_err(|e| e.to_string())?);
        }
        Commands::BindBody { fuse, body_sha256 } => {
            let v = fuse_bind_body(&fuse, &body_sha256)?;
            println!("{}", serde_json::to_string_pretty(&v).map_err(|e| e.to_string())?);
        }
        Commands::CurrentGate { fuse } => {
            let ok = fuse_current_allowed(&fuse)?;
            println!("{}", if ok { "1" } else { "0" });
        }
        Commands::Validate { json } => {
            let text = fs::read_to_string(&json).map_err(|e| format!("read: {e}"))?;
            match validate_silicon_fuse_json(&text) {
                Ok(()) => println!("OK"),
                Err(errors) => {
                    for e in &errors {
                        eprintln!("{e}");
                    }
                    return Err(String::new());
                }
            }
        }
    }
    Ok(())
}
