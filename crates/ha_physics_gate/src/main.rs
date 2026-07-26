use clap::{Parser, Subcommand};
use ha_physics_gate::{
    bekker_roundtrip, evaluate_acoustic_wave_file, evaluate_albedo_dose_file,
    evaluate_atm_drag_file, evaluate_battery_peukert_file, evaluate_column_step_file,
    evaluate_coulomb_loft_file, evaluate_dc_motor_gear_file, evaluate_dust_ingress_file,
    evaluate_eclipse_umbra_file, evaluate_fatigue_sn_file, evaluate_isru_sinter_file,
    evaluate_janosi_curve_file, evaluate_joint_friction_file, evaluate_li_qc_file,
    evaluate_materials_hooke_file, evaluate_mohr_slope_file, evaluate_multipass_rut_file,
    evaluate_optics_tau_file, evaluate_orbital_visviva_file, evaluate_pressure_from_z_file,
    evaluate_radiation_rate, evaluate_radiation_rate_file, evaluate_radiative_bc_file,
    evaluate_rigid_hop_file, evaluate_soil_file, evaluate_soiling_bc_file,
    evaluate_solar_pressure_file, evaluate_surface_charging_file, evaluate_terzaghi_bearing_file,
    evaluate_thermal_k_file, evaluate_trapped_belt_file, evaluate_wind_load_file,
    evaluate_fourier_flux_file, evaluate_free_mol_drag_file, evaluate_rad_damage_tid_file,
    janosi_hanamoto_shear_kpa, validate_physics_gate_v1, BekkerParams,
    DigitAdvise, DEFAULT_LIE_THRESHOLD, SCHEMA, emit_physics_gate_v1_with_modes,
};
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "ha-physics-gate")]
#[command(about = "H6 Physics gate / apoptosis + Bekker ON terramech (Rust oracle)")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Emit physics_gate_v1 JSON
    Emit {
        #[arg(long = "gate-id")]
        gate_id: String,
        #[arg(long = "digit-advise")]
        digit_advise: String,
        /// true|false
        #[arg(long = "traverse-feasible")]
        traverse_feasible: String,
        /// true|false
        #[arg(long = "sinkage-risk")]
        sinkage_risk: String,
        /// true|false — FAILURE_MODE_GATE clear (default true)
        #[arg(long = "failure-modes-clear", default_value = "true")]
        failure_modes_clear: String,
        #[arg(long = "budget-j")]
        budget_j: f64,
        #[arg(long = "residual-j")]
        residual_j: f64,
        #[arg(long = "prior-lie", default_value_t = 0.0)]
        prior_lie: f64,
        /// true|false
        #[arg(long = "prior-apoptosis", default_value = "false")]
        prior_apoptosis: String,
        #[arg(long = "lie-threshold", default_value_t = DEFAULT_LIE_THRESHOLD)]
        lie_threshold: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Validate physics_gate_v1 JSON
    Validate {
        #[arg(long)]
        json: PathBuf,
    },
    /// Evaluate Bekker sinkage from ON-grounded soil catalog (Rust oracle)
    #[command(name = "bekker-eval")]
    BekkerEval {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "soil-id")]
        soil_id: String,
        #[arg(long = "p-kpa")]
        p_kpa: Option<f64>,
        #[arg(long = "b-m")]
        b_m: Option<f64>,
        #[arg(long = "area-m2")]
        area_m2: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Bekker identity thermometer: z(p) then p'(z) must close (not field MEASURED)
    #[command(name = "bekker-roundtrip")]
    BekkerRoundtrip {
        #[arg(long)]
        n: f64,
        #[arg(long)]
        kc: f64,
        #[arg(long = "k-phi")]
        k_phi: f64,
        #[arg(long = "b-m")]
        b_m: f64,
        #[arg(long = "p-kpa")]
        p_kpa: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Bekker p from z for catalog soil (inverse thermometer)
    #[command(name = "bekker-from-z")]
    BekkerFromZ {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "soil-id")]
        soil_id: String,
        #[arg(long = "z-m")]
        z_m: f64,
        #[arg(long = "b-m")]
        b_m: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Janosi–Hanamoto shear τ=(c+p tanφ)(1-e^{-j/K}) — optional terramech slice
    #[command(name = "bekker-shear")]
    BekkerShear {
        #[arg(long = "c-kpa")]
        c_kpa: f64,
        #[arg(long = "phi-deg")]
        phi_deg: f64,
        #[arg(long = "k-m")]
        k_m: f64,
        #[arg(long = "p-kpa")]
        p_kpa: f64,
        #[arg(long = "j-m")]
        j_m: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// U4 M3 radiation window: dD=(D_annual/H_year)*dt*clamp(flare)
    #[command(name = "radiation-rate")]
    RadiationRate {
        #[arg(long)]
        catalog: Option<PathBuf>,
        #[arg(long = "site-id")]
        site_id: Option<String>,
        #[arg(long = "annual-gy")]
        annual_gy: Option<f64>,
        #[arg(long = "annual-see")]
        annual_see: Option<f64>,
        #[arg(long = "dt-h")]
        dt_h: f64,
        #[arg(long = "flare-scale", default_value_t = 1.0)]
        flare_scale: f64,
        #[arg(long = "flare-lo", default_value_t = 1.0)]
        flare_lo: f64,
        #[arg(long = "flare-hi", default_value_t = 12.0)]
        flare_hi: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// U4 M1 regolith k(T): k=k_solid+b_rad*T^3 · optional Woods cryo leg
    #[command(name = "thermal-k")]
    ThermalK {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "material-id")]
        material_id: String,
        #[arg(long = "t-k")]
        t_k: f64,
        /// Apply Woods cryo scale when T < t_cryo from catalog
        #[arg(long, default_value_t = false)]
        cryo: bool,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Vacuum radiative BC: q_rad=eps*sigma*(T^4-Tsky^4); q_solar=(1-A)*S*illum
    #[command(name = "radiative-bc")]
    RadiativeBc {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        zone: String,
        #[arg(long = "t-k")]
        t_k: f64,
        #[arg(long)]
        illum: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// U4 1D thermal column implicit Picard step
    #[command(name = "thermal-column-step")]
    ThermalColumnStep {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "material-id")]
        material_id: String,
        /// Comma-separated node temperatures [K]
        #[arg(long = "t-k")]
        t_k: String,
        #[arg(long = "dt-h")]
        dt_h: f64,
        #[arg(long = "dz-m")]
        dz_m: f64,
        #[arg(long = "rho-cp")]
        rho_cp: f64,
        #[arg(long = "q-in")]
        q_in: f64,
        #[arg(long, default_value_t = false)]
        cryo: bool,
        #[arg(long = "picard", default_value_t = 2)]
        picard: usize,
        #[arg(long = "t-lo", default_value_t = 40.0)]
        t_lo: f64,
        #[arg(long = "t-hi", default_value_t = 400.0)]
        t_hi: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// SELINE-surrogate albedo split + Matthia shield paradox
    #[command(name = "albedo-dose")]
    AlbedoDose {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "site-class")]
        site_class: String,
        #[arg(long = "shield-g-cm2", default_value_t = 0.0)]
        shield_g_cm2: f64,
        #[arg(long = "anchor-gy")]
        anchor_gy: f64,
        #[arg(long = "see-base")]
        see_base: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Stubbs/Colwell dust ingress rate + accumulation
    #[command(name = "dust-ingress")]
    DustIngress {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        zone: String,
        #[arg(long)]
        seal: String,
        #[arg(long = "n-sols", default_value_t = 1.0)]
        n_sols: f64,
        #[arg(long = "mit", default_value_t = 0.0)]
        mit: f64,
        #[arg(long = "gap-mm", default_value_t = 0.5)]
        gap_mm: f64,
        #[arg(long = "prev", default_value_t = 0.0)]
        prev: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Li lunar-g q_c(h) teaching fit (GAP-MR-11 adjunct)
    #[command(name = "li-qc")]
    LiQc {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "depth-mm")]
        depth_mm: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Zheng/Stubbs surface charging class + φ_s
    #[command(name = "surface-charging")]
    SurfaceCharging {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        illum: f64,
        #[arg(long, action = clap::ArgAction::SetTrue)]
        sep: bool,
        #[arg(long, action = clap::ArgAction::SetTrue)]
        magnetotail: bool,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Stubbs Coulomb loft ratio (qE vs mg)
    #[command(name = "coulomb-loft")]
    CoulombLoft {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "phi-v")]
        phi_v: f64,
        #[arg(long = "r-um")]
        r_um: Option<f64>,
        #[arg(long = "rho")]
        rho: Option<f64>,
        #[arg(long = "lambda-d")]
        lambda_d: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Mohr–Coulomb infinite slope FS
    #[command(name = "mohr-slope")]
    MohrSlope {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "theta-deg")]
        theta_deg: f64,
        #[arg(long = "z-m")]
        z_m: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Beer–Lambert dust optical depth
    #[command(name = "optics-tau")]
    OpticsTau {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "mass-g-m2")]
        mass_g_m2: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Soiling thermal BC (A/eps/R_th)
    #[command(name = "soiling-bc")]
    SoilingBc {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "mass-g-m2")]
        mass_g_m2: f64,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Newtonian ballistic hop
    #[command(name = "rigid-hop")]
    RigidHop {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "v-up")]
        v_up: Option<f64>,
        #[arg(long = "v-h")]
        v_h: Option<f64>,
        #[arg(long)]
        body: Option<String>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Multi-pass rut z_N=z1·N^α on Bekker virgin
    #[command(name = "multipass-rut")]
    MultipassRut {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "soil-id")]
        soil_id: String,
        #[arg(long = "n-passes")]
        n_passes: Option<f64>,
        #[arg(long = "p-kpa")]
        p_kpa: Option<f64>,
        #[arg(long = "b-m")]
        b_m: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Janosi–Hanamoto τ(j) full curve
    #[command(name = "janosi-curve")]
    JanosiCurve {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long = "soil-id")]
        soil_id: String,
        #[arg(long = "p-kpa")]
        p_kpa: Option<f64>,
        #[arg(long = "j-max")]
        j_max: Option<f64>,
        #[arg(long = "n-points")]
        n_points: Option<usize>,
        #[arg(long = "area")]
        area: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Quadratic atmospheric drag
    #[command(name = "atm-drag")]
    AtmDrag {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        body: String,
        #[arg(long)]
        v: Option<f64>,
        #[arg(long)]
        cd: Option<f64>,
        #[arg(long)]
        area: Option<f64>,
        #[arg(long)]
        mass: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Peukert discharge + linear OCV–SOC
    #[command(name = "battery-peukert")]
    BatteryPeukert {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long = "i-a")]
        i_a: Option<f64>,
        #[arg(long)]
        soc: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Elastic wave speeds + attenuation
    #[command(name = "acoustic-wave")]
    AcousticWave {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        medium: String,
        #[arg(long = "path-m")]
        path_m: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Arrhenius ISRU sinter + energy
    #[command(name = "isru-sinter")]
    IsruSinter {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        recipe: String,
        #[arg(long = "t-k")]
        t_k: Option<f64>,
        #[arg(long = "t-s")]
        t_s: Option<f64>,
        #[arg(long = "p-w")]
        p_w: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Hooke + CTE materials
    #[command(name = "materials-hooke")]
    MaterialsHooke {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        mat: String,
        #[arg(long)]
        eps: Option<f64>,
        #[arg(long = "dt-k")]
        dt_k: Option<f64>,
        #[arg(long = "l-m")]
        l_m: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Two-body vis-viva + Kepler period
    #[command(name = "orbital-visviva")]
    OrbitalVisviva {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        body: String,
        #[arg(long = "r-km")]
        r_km: Option<f64>,
        #[arg(long = "a-km")]
        a_km: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// DC motor linear τ–ω + gear η
    #[command(name = "dc-motor-gear")]
    DcMotorGear {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long = "omega-rad-s")]
        omega_rad_s: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Earth wind dynamic pressure load
    #[command(name = "wind-load")]
    WindLoad {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long = "v-m-s")]
        v_m_s: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Basquin fatigue S–N
    #[command(name = "fatigue-sn")]
    FatigueSn {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        mat: String,
        #[arg(long = "sigma-a-mpa")]
        sigma_a_mpa: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Circular beta=0 eclipse fraction
    #[command(name = "eclipse-umbra")]
    EclipseUmbra {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        orbit: String,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Coulomb joint friction
    #[command(name = "joint-friction")]
    JointFriction {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long = "n-n")]
        n_n: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Solar radiation pressure
    #[command(name = "solar-pressure")]
    SolarPressure {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long = "i-rad")]
        i_rad: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Free-molecular drag
    #[command(name = "free-mol-drag")]
    FreeMolDrag {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// TID damage accumulate
    #[command(name = "rad-damage-tid")]
    RadDamageTid {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long = "t-h")]
        t_h: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Terzaghi bearing
    #[command(name = "terzaghi-bearing")]
    TerzaghiBearing {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Trapped belt class
    #[command(name = "trapped-belt")]
    TrappedBelt {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long = "t-h")]
        t_h: Option<f64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    /// Fourier conduction flux
    #[command(name = "fourier-flux")]
    FourierFlux {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        pack: String,
        #[arg(long = "dt-k")]
        dt_k: Option<f64>,
        #[arg(long = "dx-m")]
        dx_m: Option<f64>,
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

fn parse_bool_flag(name: &str, raw: &str) -> Result<bool, String> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "true" | "1" | "yes" => Ok(true),
        "false" | "0" | "no" => Ok(false),
        other => Err(format!("{name} must be true|false, got {other}")),
    }
}

fn run() -> Result<(), String> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Emit {
            gate_id,
            digit_advise,
            traverse_feasible,
            sinkage_risk,
            failure_modes_clear,
            budget_j,
            residual_j,
            prior_lie,
            prior_apoptosis,
            lie_threshold,
            out,
        } => {
            let digit = DigitAdvise::parse(&digit_advise)?;
            let traverse_feasible = parse_bool_flag("traverse-feasible", &traverse_feasible)?;
            let sinkage_risk = parse_bool_flag("sinkage-risk", &sinkage_risk)?;
            let failure_modes_clear =
                parse_bool_flag("failure-modes-clear", &failure_modes_clear)?;
            let prior_apoptosis = parse_bool_flag("prior-apoptosis", &prior_apoptosis)?;
            let value = emit_physics_gate_v1_with_modes(
                &gate_id,
                digit,
                traverse_feasible,
                sinkage_risk,
                failure_modes_clear,
                budget_j,
                residual_j,
                prior_lie,
                prior_apoptosis,
                lie_threshold,
            )?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            let _ = SCHEMA;
            Ok(())
        }
        Commands::Validate { json } => {
            let text = fs::read_to_string(&json).map_err(|e| e.to_string())?;
            match validate_physics_gate_v1(&text) {
                Ok(()) => {
                    println!("PHYSICS_GATE VALIDATE PASS");
                    Ok(())
                }
                Err(errs) => Err(errs.join("; ")),
            }
        }
        Commands::BekkerEval {
            catalog,
            soil_id,
            p_kpa,
            b_m,
            area_m2,
            out,
        } => {
            let value = evaluate_soil_file(&catalog, &soil_id, p_kpa, b_m, area_m2)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::BekkerRoundtrip {
            n,
            kc,
            k_phi,
            b_m,
            p_kpa,
            out,
        } => {
            let value = bekker_roundtrip(BekkerParams {
                n,
                kc,
                k_phi,
                b_m,
                p_kpa,
            })?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            if !value
                .get("physics_closure_ok")
                .and_then(|v| v.as_bool())
                .unwrap_or(false)
            {
                return Err("bekker roundtrip residual exceeds eps".into());
            }
            Ok(())
        }
        Commands::BekkerFromZ {
            catalog,
            soil_id,
            z_m,
            b_m,
            out,
        } => {
            let value = evaluate_pressure_from_z_file(&catalog, &soil_id, z_m, b_m)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::BekkerShear {
            c_kpa,
            phi_deg,
            k_m,
            p_kpa,
            j_m,
            out,
        } => {
            let tau = janosi_hanamoto_shear_kpa(c_kpa, phi_deg, k_m, p_kpa, j_m)?;
            let value = serde_json::json!({
                "schema": "ha_bekker_shear_v1",
                "oracle": "ha_physics_gate_bekker",
                "model": "janosi_hanamoto",
                "c_kpa": c_kpa,
                "phi_deg": phi_deg,
                "K_m": k_m,
                "p_kpa": p_kpa,
                "j_m": j_m,
                "tau_kpa": (tau * 1e9_f64).round() / 1e9_f64,
                "equation": "tau = (c + p*tan(phi))*(1 - exp(-j/K))",
                "honesty": {
                    "not_measured": true,
                    "python_not_oracle": true
                }
            });
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::RadiationRate {
            catalog,
            site_id,
            annual_gy,
            annual_see,
            dt_h,
            flare_scale,
            flare_lo,
            flare_hi,
            out,
        } => {
            let value = if let Some(path) = catalog {
                let sid = site_id.ok_or_else(|| "site-id required with --catalog".to_string())?;
                evaluate_radiation_rate_file(&path, &sid, dt_h, flare_scale)?
            } else {
                let annual =
                    annual_gy.ok_or_else(|| "annual-gy required without --catalog".to_string())?;
                let see = annual_see.ok_or_else(|| {
                    "annual-see required without --catalog (no airborne SEE default)".to_string()
                })?;
                evaluate_radiation_rate(
                    annual,
                    see,
                    dt_h,
                    flare_scale,
                    flare_lo,
                    flare_hi,
                    site_id.as_deref(),
                )?
            };
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::ThermalK {
            catalog,
            material_id,
            t_k,
            cryo,
            out,
        } => {
            let value = evaluate_thermal_k_file(&catalog, &material_id, t_k, cryo)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::RadiativeBc {
            catalog,
            zone,
            t_k,
            illum,
            out,
        } => {
            let value = evaluate_radiative_bc_file(&catalog, &zone, t_k, illum)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::ThermalColumnStep {
            catalog,
            material_id,
            t_k,
            dt_h,
            dz_m,
            rho_cp,
            q_in,
            cryo,
            picard,
            t_lo,
            t_hi,
            out,
        } => {
            let temps: Vec<f64> = t_k
                .split(',')
                .map(|s| {
                    s.trim()
                        .parse::<f64>()
                        .map_err(|e| format!("bad t-k token '{s}': {e}"))
                })
                .collect::<Result<Vec<_>, _>>()?;
            if temps.is_empty() {
                return Err("t-k must list at least one temperature".into());
            }
            let value = evaluate_column_step_file(
                &catalog,
                &material_id,
                &temps,
                dt_h,
                dz_m,
                rho_cp,
                q_in,
                cryo,
                picard,
                t_lo,
                t_hi,
            )?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::AlbedoDose {
            catalog,
            site_class,
            shield_g_cm2,
            anchor_gy,
            see_base,
            out,
        } => {
            let value =
                evaluate_albedo_dose_file(&catalog, &site_class, shield_g_cm2, anchor_gy, see_base)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::DustIngress {
            catalog,
            zone,
            seal,
            n_sols,
            mit,
            gap_mm,
            prev,
            out,
        } => {
            let value =
                evaluate_dust_ingress_file(&catalog, &zone, &seal, mit, gap_mm, n_sols, prev)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::LiQc {
            catalog,
            depth_mm,
            out,
        } => {
            let value = evaluate_li_qc_file(&catalog, depth_mm)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::SurfaceCharging {
            catalog,
            illum,
            sep,
            magnetotail,
            out,
        } => {
            let value = evaluate_surface_charging_file(&catalog, illum, sep, magnetotail)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::CoulombLoft {
            catalog,
            phi_v,
            r_um,
            rho,
            lambda_d,
            out,
        } => {
            let value = evaluate_coulomb_loft_file(&catalog, phi_v, r_um, rho, lambda_d)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::MohrSlope {
            catalog,
            theta_deg,
            z_m,
            out,
        } => {
            let value = evaluate_mohr_slope_file(&catalog, theta_deg, z_m)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::OpticsTau {
            catalog,
            mass_g_m2,
            out,
        } => {
            let value = evaluate_optics_tau_file(&catalog, mass_g_m2)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::SoilingBc {
            catalog,
            mass_g_m2,
            out,
        } => {
            let value = evaluate_soiling_bc_file(&catalog, mass_g_m2)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::RigidHop {
            catalog,
            v_up,
            v_h,
            body,
            out,
        } => {
            let value = evaluate_rigid_hop_file(&catalog, v_up, v_h, body.as_deref())?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::MultipassRut {
            catalog,
            soil_id,
            n_passes,
            p_kpa,
            b_m,
            out,
        } => {
            let value = evaluate_multipass_rut_file(&catalog, &soil_id, n_passes, p_kpa, b_m)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::JanosiCurve {
            catalog,
            soil_id,
            p_kpa,
            j_max,
            n_points,
            area,
            out,
        } => {
            let value =
                evaluate_janosi_curve_file(&catalog, &soil_id, p_kpa, j_max, n_points, area)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::AtmDrag {
            catalog,
            body,
            v,
            cd,
            area,
            mass,
            out,
        } => {
            let value = evaluate_atm_drag_file(&catalog, &body, v, cd, area, mass)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::BatteryPeukert {
            catalog,
            pack,
            i_a,
            soc,
            out,
        } => {
            let value = evaluate_battery_peukert_file(&catalog, &pack, i_a, soc)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::AcousticWave {
            catalog,
            medium,
            path_m,
            out,
        } => {
            let value = evaluate_acoustic_wave_file(&catalog, &medium, path_m)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::IsruSinter {
            catalog,
            recipe,
            t_k,
            t_s,
            p_w,
            out,
        } => {
            let value = evaluate_isru_sinter_file(&catalog, &recipe, t_k, t_s, p_w)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::MaterialsHooke {
            catalog,
            mat,
            eps,
            dt_k,
            l_m,
            out,
        } => {
            let value = evaluate_materials_hooke_file(&catalog, &mat, eps, dt_k, l_m)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::OrbitalVisviva {
            catalog,
            body,
            r_km,
            a_km,
            out,
        } => {
            let value = evaluate_orbital_visviva_file(&catalog, &body, r_km, a_km)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::DcMotorGear {
            catalog,
            pack,
            omega_rad_s,
            out,
        } => {
            let value = evaluate_dc_motor_gear_file(&catalog, &pack, omega_rad_s)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::WindLoad {
            catalog,
            pack,
            v_m_s,
            out,
        } => {
            let value = evaluate_wind_load_file(&catalog, &pack, v_m_s)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::FatigueSn {
            catalog,
            mat,
            sigma_a_mpa,
            out,
        } => {
            let value = evaluate_fatigue_sn_file(&catalog, &mat, sigma_a_mpa)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::EclipseUmbra {
            catalog,
            orbit,
            out,
        } => {
            let value = evaluate_eclipse_umbra_file(&catalog, &orbit)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::JointFriction {
            catalog,
            pack,
            n_n,
            out,
        } => {
            let value = evaluate_joint_friction_file(&catalog, &pack, n_n)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::SolarPressure {
            catalog,
            pack,
            i_rad,
            out,
        } => {
            let value = evaluate_solar_pressure_file(&catalog, &pack, i_rad)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::FreeMolDrag { catalog, pack, out } => {
            let value = evaluate_free_mol_drag_file(&catalog, &pack)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::RadDamageTid {
            catalog,
            pack,
            t_h,
            out,
        } => {
            let value = evaluate_rad_damage_tid_file(&catalog, &pack, t_h)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::TerzaghiBearing { catalog, pack, out } => {
            let value = evaluate_terzaghi_bearing_file(&catalog, &pack)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::TrappedBelt {
            catalog,
            pack,
            t_h,
            out,
        } => {
            let value = evaluate_trapped_belt_file(&catalog, &pack, t_h)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
        Commands::FourierFlux {
            catalog,
            pack,
            dt_k,
            dx_m,
            out,
        } => {
            let value = evaluate_fourier_flux_file(&catalog, &pack, dt_k, dx_m)?;
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            if let Some(path) = out {
                fs::write(&path, format!("{text}\n")).map_err(|e| e.to_string())?;
            } else {
                println!("{text}");
            }
            Ok(())
        }
    }
}
