use clap::{Parser, Subcommand};
use ha_energy_ledger::{
    compaction_work_joules, emit_energy_claim_v1, kinetic_tax_joules, validate_energy_claim_v1,
    DEFAULT_ABS_TOL, DEFAULT_TAX_ALPHA, DEFAULT_TAX_BASE_J, SCHEMA,
};
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "ha-energy-ledger")]
#[command(about = "H7 Energy Ledger / kinetic tax (Rust oracle)")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Soft kinetic tax joules from action magnitude (stdout: float)
    Tax {
        #[arg(long)]
        magnitude: f64,
        #[arg(long, default_value_t = DEFAULT_TAX_BASE_J)]
        base: f64,
        #[arg(long, default_value_t = DEFAULT_TAX_ALPHA)]
        alpha: f64,
    },
    /// Compaction work joules from Bekker Rc and distance (stdout: float)
    Work {
        #[arg(long)]
        rc_n: f64,
        #[arg(long)]
        distance_m: f64,
    },
    /// Validate energy_claim_v1 JSON (exit 0 = balanced OK)
    Validate {
        #[arg(long)]
        json: PathBuf,
        #[arg(long, default_value_t = DEFAULT_ABS_TOL)]
        abs_tol: f64,
    },
    /// Emit balanced energy_claim_v1 JSON
    Emit {
        #[arg(long)]
        budget: f64,
        #[arg(long = "spent-actuation")]
        spent_actuation: f64,
        #[arg(long = "kinetic-tax")]
        kinetic_tax: f64,
        #[arg(long = "claim-id", default_value = "claim")]
        claim_id: String,
        #[arg(long)]
        out: Option<PathBuf>,
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
        Commands::Tax {
            magnitude,
            base,
            alpha,
        } => {
            let t = kinetic_tax_joules(magnitude, base, alpha);
            if !t.is_finite() {
                return Err("tax not finite".into());
            }
            println!("{t}");
            let _ = SCHEMA;
        }
        Commands::Work { rc_n, distance_m } => {
            let w = compaction_work_joules(rc_n, distance_m);
            if !w.is_finite() {
                return Err("work not finite".into());
            }
            println!("{w}");
        }
        Commands::Validate { json, abs_tol } => {
            let text = fs::read_to_string(&json).map_err(|e| format!("read json: {e}"))?;
            match validate_energy_claim_v1(&text, abs_tol) {
                Ok(()) => println!("OK"),
                Err(errors) => {
                    for e in &errors {
                        eprintln!("{e}");
                    }
                    return Err(String::new());
                }
            }
        }
        Commands::Emit {
            budget,
            spent_actuation,
            kinetic_tax,
            claim_id,
            out,
        } => {
            let value = emit_energy_claim_v1(budget, spent_actuation, kinetic_tax, &claim_id)?;
            let pretty = serde_json::to_string_pretty(&value).map_err(|e| format!("json: {e}"))?;
            validate_energy_claim_v1(&pretty, DEFAULT_ABS_TOL).map_err(|errs| errs.join("; "))?;
            if let Some(out_path) = out {
                fs::write(&out_path, pretty.clone() + "\n")
                    .map_err(|e| format!("write out: {e}"))?;
            }
            println!("{pretty}");
        }
    }
    Ok(())
}
