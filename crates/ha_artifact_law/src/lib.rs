//! Artifact Existence Law — one Rust oracle for pack/project truth.
//! Law: artifact NULL without Safe∧Hostile + actuation_truth + energy + gate + intact fuse
//! (+ body identity when body present).

use ha_body_identity::{hash_file, validate_body_identity_v1};
use ha_energy_ledger::{validate_energy_claim_v1, DEFAULT_ABS_TOL};
use ha_iron_attestation::{check_iron_at_root, IronCheckResult};
use ha_physics_gate::validate_physics_gate_v1;
use ha_silicon_fuse::fuse_status;
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

pub const SCHEMA: &str = "law_receipt_v1";
pub const LAW_ID: &str = "LIE_MUST_COST_PHYSICALLY_H8_H7_H6_IRON_H9_H10";
pub const REQUIRED: &[&str] = &["safe", "hostile"];

#[derive(Debug, Clone, Default)]
pub struct VerifyOpts {
    pub require_iron: bool,
    pub reject_soft_stub: bool,
    pub iron_path: Option<PathBuf>,
    /// World robotics × physics: require open body + closed_loop + soil Dual falsifier
    pub world_join: bool,
}

#[derive(Debug, Default)]
pub struct LawResult {
    pub ok: bool,
    pub errors: Vec<String>,
    pub conditions: Vec<String>,
    pub run_ids: serde_json::Map<String, Value>,
    pub iron: Option<IronCheckResult>,
}

fn read_json(path: &Path) -> Result<Value, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("read {}: {e}", path.display()))?;
    serde_json::from_str(&text).map_err(|e| format!("json {}: {e}", path.display()))
}

fn latest_runs_by_condition(runs_dir: &Path) -> Result<serde_json::Map<String, Value>, Vec<String>> {
    let mut errors = Vec::new();
    let mut latest: serde_json::Map<String, Value> = serde_json::Map::new();
    if !runs_dir.is_dir() {
        errors.push("missing_runs_dir".into());
        return Err(errors);
    }
    let entries = fs::read_dir(runs_dir).map_err(|e| vec![format!("read_runs: {e}")])?;
    for ent in entries.flatten() {
        let path = ent.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        if !name.starts_with("run-") {
            continue;
        }
        match read_json(&path) {
            Ok(doc) => {
                let cond = doc
                    .get("condition")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                if !REQUIRED.contains(&cond.as_str()) {
                    continue;
                }
                let ts = doc
                    .get("timestamp_utc")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let replace = match latest.get(&cond) {
                    None => true,
                    Some(prev) => {
                        let pts = prev
                            .get("timestamp_utc")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        ts.as_str() >= pts
                    }
                };
                if replace {
                    latest.insert(cond, doc);
                }
            }
            Err(e) => errors.push(e),
        }
    }
    if !errors.is_empty() && latest.is_empty() {
        return Err(errors);
    }
    Ok(latest)
}

fn check_actuation_truth(doc: &Value, cond: &str, errors: &mut Vec<String>) {
    let at = match doc.get("actuation_truth") {
        Some(v) if v.get("schema").and_then(|s| s.as_str()) == Some("actuation_truth_v1") => v,
        _ => {
            errors.push(format!("missing_actuation_truth:{cond}"));
            return;
        }
    };
    for role in ["stub", "planner"] {
        let leg = at.get(role);
        if !leg.map(|l| l.is_object()).unwrap_or(false) {
            errors.push(format!("hollow_actuation_truth:{cond}:{role}:not_object"));
            continue;
        }
        let leg = leg.unwrap();
        if leg
            .get("command")
            .and_then(|c| c.as_str())
            .unwrap_or("")
            .is_empty()
        {
            errors.push(format!("hollow_actuation_truth:{cond}:{role}:empty_command"));
        }
        if !leg
            .get("world_before")
            .map(|w| w.get("cursor_m").is_some())
            .unwrap_or(false)
        {
            errors.push(format!(
                "hollow_actuation_truth:{cond}:{role}:missing_world_before"
            ));
        }
        if !leg
            .get("world_after")
            .map(|w| w.get("cursor_m").is_some())
            .unwrap_or(false)
        {
            errors.push(format!(
                "hollow_actuation_truth:{cond}:{role}:missing_world_after"
            ));
        }
    }
}

fn check_closed_loop(doc: &Value, cond: &str, errors: &mut Vec<String>) {
    let loop_v = match doc.get("closed_loop_v1") {
        Some(v) if v.is_object() => v,
        _ => {
            errors.push(format!("missing_closed_loop_v1:{cond}"));
            return;
        }
    };
    if !loop_v.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        let fals = loop_v
            .get("active_falsifier")
            .and_then(|v| v.as_str())
            .unwrap_or("?");
        errors.push(format!("closed_loop_v1_FAIL:{cond}:{fals}"));
    }
}

fn check_world_join_soil_dual(
    latest: &serde_json::Map<String, Value>,
    errors: &mut Vec<String>,
) {
    let safe = latest.get("safe");
    let hostile = latest.get("hostile");
    if safe.is_none() || hostile.is_none() {
        // missing_condition already reported
        return;
    }
    let safe = safe.unwrap();
    let hostile = hostile.unwrap();

    for (cond, doc) in [("safe", safe), ("hostile", hostile)] {
        check_closed_loop(doc, cond, errors);
    }

    let h_dual = hostile.get("dual").filter(|d| d.is_object());
    let Some(h_dual) = h_dual else {
        return;
    };
    let stub = h_dual
        .get("stub_command")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let plan = h_dual
        .get("regolith_command")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if stub.is_empty() || plan.is_empty() {
        errors.push("world_join_hostile_commands_missing".into());
    } else if stub == plan {
        errors.push(format!(
            "world_join_hostile_commands_not_diverged:{stub}=={plan}"
        ));
    } else if stub != "traverse" || plan != "recover" {
        // Allow other diverge pairs but prefer the soil falsifier contract
        if !h_dual
            .get("diverged")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
        {
            errors.push("world_join_hostile_dual_not_diverged".into());
        }
    }

    // Soft-soil Hostile: sinkage_risk must be asserted on gate inputs or dual_block physics
    let sinkage = hostile
        .pointer("/physics_gate/inputs/sinkage_risk")
        .and_then(|v| v.as_bool())
        .or_else(|| {
            hostile
                .pointer("/dual_block/physics/sinkage_risk")
                .and_then(|v| v.as_bool())
        })
        .or_else(|| {
            hostile
                .pointer("/dual_block/physics/sinkage_mm")
                .and_then(|v| v.as_f64())
                .map(|mm| mm >= 15.0)
        });
    match sinkage {
        Some(true) => {}
        Some(false) => errors.push("world_join_hostile_sinkage_risk_false".into()),
        None => errors.push("world_join_hostile_sinkage_risk_missing".into()),
    }

    // Safe: stub/planner aligned traverse (soil allows motion)
    if let Some(s_dual) = safe.get("dual").filter(|d| d.is_object()) {
        let s_stub = s_dual
            .get("stub_command")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let s_plan = s_dual
            .get("regolith_command")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if s_stub != "traverse" || s_plan != "traverse" {
            errors.push(format!(
                "world_join_safe_not_aligned_traverse:{s_stub}/{s_plan}"
            ));
        }
        if s_dual
            .get("diverged")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
        {
            errors.push("world_join_safe_unexpected_diverge".into());
        }
    }
}

fn check_world_join_body_required(root: &Path, errors: &mut Vec<String>) {
    let body_dir = root.join("body");
    if !body_dir.is_dir() {
        errors.push("world_join_missing_body".into());
        return;
    }
    let id_path = body_dir.join("BODY_IDENTITY_v1.json");
    if !id_path.is_file() {
        errors.push("world_join_missing_body_identity".into());
    }
    // Prefer a real geometry file (URDF/MJCF), not only assembly recipe
    let mut has_geom = false;
    if let Ok(rd) = fs::read_dir(&body_dir) {
        for ent in rd.flatten() {
            let p = ent.path();
            let ext = p
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("")
                .to_ascii_lowercase();
            if matches!(ext.as_str(), "urdf" | "mjcf" | "xml") {
                has_geom = true;
                break;
            }
        }
    }
    if !has_geom {
        // preset packs may only have recipe — still require identity; note soft for world-join
        let project_path = root.join("project.json");
        let mut byo = false;
        if project_path.is_file() {
            if let Ok(proj) = read_json(&project_path) {
                let kind = proj
                    .pointer("/body/kind")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                byo = matches!(kind, "urdf" | "mjcf" | "json_pack");
            }
        }
        if byo {
            errors.push("world_join_missing_urdf_bytes".into());
        }
    }
}

fn check_dual(doc: &Value, cond: &str, errors: &mut Vec<String>) {
    let dual = doc.get("dual");
    if !dual.map(|d| d.is_object()).unwrap_or(false) {
        errors.push(format!("missing_dual:{cond}"));
        return;
    }
    if cond == "hostile" && !dual.unwrap().get("diverged").and_then(|v| v.as_bool()).unwrap_or(false)
    {
        errors.push("hostile_dual_not_diverged".into());
    }
}

fn check_energy(doc: &Value, cond: &str, errors: &mut Vec<String>) {
    let claim = match doc.get("energy_claim") {
        Some(v) => v,
        None => {
            errors.push(format!("missing_energy_claim:{cond}"));
            return;
        }
    };
    let text = match serde_json::to_string(claim) {
        Ok(t) => t,
        Err(e) => {
            errors.push(format!("energy_claim:{cond}:{e}"));
            return;
        }
    };
    if let Err(errs) = validate_energy_claim_v1(&text, DEFAULT_ABS_TOL) {
        for e in errs {
            errors.push(format!("energy_claim:{cond}:{e}"));
        }
    }
}

fn check_physics_gate(doc: &Value, cond: &str, errors: &mut Vec<String>) {
    let gate = match doc.get("physics_gate") {
        Some(v) => v,
        None => {
            errors.push(format!("missing_physics_gate:{cond}"));
            return;
        }
    };
    let text = match serde_json::to_string(gate) {
        Ok(t) => t,
        Err(e) => {
            errors.push(format!("physics_gate:{cond}:{e}"));
            return;
        }
    };
    if let Err(errs) = validate_physics_gate_v1(&text) {
        for e in errs {
            errors.push(format!("physics_gate:{cond}:{e}"));
        }
    }
    if gate
        .pointer("/apoptosis/bit")
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
    {
        errors.push(format!("apoptosis_latched:{cond}"));
    }
    if !gate
        .get("governance_coherent")
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
    {
        errors.push(format!("governance_incoherent:{cond}"));
    }
}

fn check_silicon_fuse_on_run(doc: &Value, cond: &str, root: &Path, errors: &mut Vec<String>) {
    let fuse = match doc.get("silicon_fuse") {
        Some(v) => v,
        None => {
            errors.push(format!("missing_silicon_fuse:{cond}"));
            return;
        }
    };
    if fuse.get("schema").and_then(|s| s.as_str()) != Some("silicon_fuse_v1") {
        errors.push(format!("missing_silicon_fuse:{cond}"));
        return;
    }
    if fuse.get("blown").and_then(|v| v.as_bool()).unwrap_or(true) {
        errors.push(format!("silicon_fuse_blown:{cond}"));
    }
    // Snapshot must agree with live SE_FUSE.bin when present
    let fuse_path = root.join("SE_FUSE.bin");
    if fuse_path.is_file() {
        if let Ok(live) = fuse_status(&fuse_path) {
            let live_blown = live.get("blown").and_then(|v| v.as_bool()).unwrap_or(true);
            let snap_blown = fuse.get("blown").and_then(|v| v.as_bool()).unwrap_or(true);
            if live_blown != snap_blown {
                errors.push(format!("silicon_fuse_snapshot_mismatch:{cond}"));
            }
        }
    }
}

fn identity_body_sha(root: &Path) -> Option<String> {
    let id_path = root.join("body").join("BODY_IDENTITY_v1.json");
    if !id_path.is_file() {
        return None;
    }
    let id = read_json(&id_path).ok()?;
    id.get("body_sha256")
        .and_then(|v| v.as_str())
        .map(|s| s.to_ascii_lowercase())
}

fn scan_claim_theater(doc: &Value, prefix: &str, errors: &mut Vec<String>) {
    if doc.get("product_ready").and_then(|v| v.as_bool()) == Some(true) {
        errors.push(format!("claim_product_ready:{prefix}"));
    }
    if doc.get("not_measured").and_then(|v| v.as_bool()) == Some(false) {
        errors.push(format!("claim_measured:{prefix}"));
    }
    if let Some(h) = doc.get("honesty") {
        if h.get("not_measured").and_then(|v| v.as_bool()) == Some(false) {
            errors.push(format!("claim_measured:{prefix}"));
        }
        if h.get("not_product_ready").and_then(|v| v.as_bool()) == Some(false) {
            errors.push(format!("claim_product_ready:{prefix}"));
        }
    }
    if let Some(tier) = doc.get("proof_tier").and_then(|v| v.as_str()) {
        let t = tier.to_ascii_uppercase();
        if t.contains("MEASURED") || t == "T3" || t == "FIELD" || t.contains("MEASURED_FIELD") {
            errors.push(format!("claim_measured_tier:{prefix}"));
        }
    }
}

fn check_honesty_claims(root: &Path, latest: &serde_json::Map<String, Value>, errors: &mut Vec<String>) {
    let project_path = root.join("project.json");
    if project_path.is_file() {
        if let Ok(proj) = read_json(&project_path) {
            scan_claim_theater(&proj, "project", errors);
        }
    }
    let meta_path = root.join("PACK_META_v1.json");
    if meta_path.is_file() {
        if let Ok(meta) = read_json(&meta_path) {
            scan_claim_theater(&meta, "pack_meta", errors);
        }
    }
    for (cond, doc) in latest {
        scan_claim_theater(doc, cond, errors);
    }
}

fn check_body_identity(root: &Path, errors: &mut Vec<String>) {
    let body_dir = root.join("body");
    let id_path = body_dir.join("BODY_IDENTITY_v1.json");
    if !body_dir.is_dir() {
        return; // no body attached — skip
    }
    // If body dir exists but only empty — still may have identity from desk
    if !id_path.is_file() {
        // body present without identity?
        let has_manifest = body_dir.join("manifest.json").is_file();
        if has_manifest || body_dir.read_dir().map(|mut d| d.next().is_some()).unwrap_or(false) {
            errors.push("missing_body_identity".into());
        }
        return;
    }
    let text = match fs::read_to_string(&id_path) {
        Ok(t) => t,
        Err(e) => {
            errors.push(format!("body_identity:{e}"));
            return;
        }
    };
    if let Err(errs) = validate_body_identity_v1(&text) {
        for e in errs {
            errors.push(format!("body_identity:{e}"));
        }
        return;
    }
    let id: Value = match serde_json::from_str(&text) {
        Ok(v) => v,
        Err(e) => {
            errors.push(format!("body_identity:{e}"));
            return;
        }
    };
    let want = id
        .get("body_sha256")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    // Prefer stored_file from project.json body, else manifest.json, else first non-identity file
    let mut candidate = body_dir.join("manifest.json");
    let project_path = root.join("project.json");
    if project_path.is_file() {
        if let Ok(proj) = read_json(&project_path) {
            if let Some(stored) = proj
                .pointer("/body/stored_file")
                .and_then(|v| v.as_str())
            {
                let p = root.join(stored);
                if p.is_file() {
                    candidate = p;
                }
            }
        }
    }
    if !candidate.is_file() {
        errors.push("body_identity_mismatch".into());
        return;
    }
    match hash_file(&candidate) {
        Ok(got) if got == want => {}
        Ok(_) => errors.push("body_identity_mismatch".into()),
        Err(e) => errors.push(format!("body_identity:{e}")),
    }
}

fn check_project_fuse(root: &Path, errors: &mut Vec<String>) {
    let fuse_path = root.join("SE_FUSE.bin");
    if !fuse_path.is_file() {
        errors.push("missing_silicon_fuse_file".into());
        return;
    }
    match fuse_status(&fuse_path) {
        Ok(st) => {
            if st.get("blown").and_then(|v| v.as_bool()).unwrap_or(true) {
                errors.push("silicon_fuse_blown".into());
            }
            let gate = st
                .pointer("/mmio/CURRENT_GATE")
                .and_then(|v| v.as_u64())
                .unwrap_or(0);
            let blown = st.get("blown").and_then(|v| v.as_bool()).unwrap_or(true);
            if !blown && gate != 1 {
                errors.push("silicon_fuse_current_gate_closed".into());
            }
            if blown && gate != 0 {
                errors.push("silicon_fuse_mmio_incoherent".into());
            }
            if let Some(want) = identity_body_sha(root) {
                let bound = st.get("body_bound").and_then(|v| v.as_bool()).unwrap_or(false);
                if !bound {
                    errors.push("silicon_fuse_body_unbound".into());
                } else {
                    let got = st
                        .get("body_sha256")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_ascii_lowercase();
                    if got != want {
                        errors.push("silicon_fuse_body_mismatch".into());
                    }
                }
            }
        }
        Err(e) => {
            if e.contains("TAMPER") {
                errors.push("silicon_fuse_tamper".into());
            } else {
                errors.push(format!("silicon_fuse:{e}"));
            }
        }
    }
}

/// Verify a project or exported pack root directory.
pub fn verify_artifact_root(root: &Path) -> LawResult {
    verify_artifact_root_with(root, &VerifyOpts::default())
}

pub fn verify_artifact_root_with(root: &Path, opts: &VerifyOpts) -> LawResult {
    let mut errors: Vec<String> = Vec::new();
    let mut run_ids = serde_json::Map::new();
    let mut conditions = Vec::new();

    let runs_dir = root.join("runs");
    let mut latest_map: serde_json::Map<String, Value> = serde_json::Map::new();
    match latest_runs_by_condition(&runs_dir) {
        Ok(by_cond) => {
            latest_map = by_cond.clone();
            for cond in REQUIRED {
                match by_cond.get(*cond) {
                    None => errors.push(format!("missing_condition:{cond}")),
                    Some(doc) => {
                        conditions.push((*cond).to_string());
                        if let Some(rid) = doc.get("run_id") {
                            run_ids.insert((*cond).to_string(), rid.clone());
                        }
                        check_actuation_truth(doc, cond, &mut errors);
                        check_dual(doc, cond, &mut errors);
                        check_energy(doc, cond, &mut errors);
                        check_physics_gate(doc, cond, &mut errors);
                        check_silicon_fuse_on_run(doc, cond, root, &mut errors);
                    }
                }
            }
        }
        Err(e) => errors.extend(e),
    }

    check_body_identity(root, &mut errors);
    check_project_fuse(root, &mut errors);
    check_honesty_claims(root, &latest_map, &mut errors);

    if opts.world_join {
        check_world_join_body_required(root, &mut errors);
        check_world_join_soil_dual(&latest_map, &mut errors);
    }

    let iron = check_iron_at_root(
        root,
        opts.iron_path.as_deref(),
        opts.require_iron,
        opts.reject_soft_stub,
    );
    errors.extend(iron.errors.iter().cloned());

    LawResult {
        ok: errors.is_empty(),
        errors,
        conditions,
        run_ids,
        iron: Some(iron),
    }
}

pub fn emit_law_receipt(root: &Path, result: &LawResult) -> Value {
    emit_law_receipt_with(root, result, &VerifyOpts::default())
}

pub fn emit_law_receipt_with(root: &Path, result: &LawResult, opts: &VerifyOpts) -> Value {
    let iron = result.iron.as_ref();
    let mut epsilon = vec![
        "ε_inject_not_measured",
        "ε_delta_is_proxy",
        "ε_sim_slice_joules",
        "ε_soft_kinetic_tax",
        "ε_soft_physics_proxy",
        "ε_file_backed_efuse",
        "ε_soft_otp_tamper_detect_not_asic",
        "ε_mmio_sim_not_asic",
        "ε_soft_not_iron",
    ];
    if iron.map(|i| i.present && i.backend.as_deref() == Some("soft_stub")) == Some(true) {
        epsilon.push("ε_soft_stub_attestation");
    }
    let mut oracles = json!({
        "body": "ha_body_identity",
        "energy": "ha_energy_ledger",
        "physics": "ha_physics_gate",
        "fuse": "ha_silicon_fuse",
        "iron": "ha_iron_attestation",
        "aggregator": "ha_artifact_law"
    });
    if opts.world_join {
        oracles
            .as_object_mut()
            .unwrap()
            .insert("world_join".into(), json!("ha_artifact_law_world_join"));
    }
    json!({
        "schema": SCHEMA,
        "law_id": LAW_ID,
        "ok": result.ok,
        "verdict": if result.ok { "PASS" } else { "FAIL" },
        "errors": result.errors,
        "conditions_present": result.conditions,
        "run_ids": result.run_ids,
        "root": root.display().to_string(),
        "iron": {
            "present": iron.map(|i| i.present).unwrap_or(false),
            "ok": iron.map(|i| i.ok).unwrap_or(false),
            "backend": iron.and_then(|i| i.backend.clone()),
            "provider_id": iron.and_then(|i| i.provider_id.clone()),
            "path": iron.and_then(|i| i.path.as_ref().map(|p| p.display().to_string())),
            "socket": "BYO_IRON_H10"
        },
        "oracles": oracles,
        "world_join": {
            "required": opts.world_join,
            "ok": if opts.world_join { result.ok } else { true }
        },
        "honesty": {
            "not_measured": true,
            "sim_slice": true,
            "not_product_ready": true,
            "python_not_oracle": true,
            "epsilon": epsilon
        }
    })
}

pub fn write_law_receipt(root: &Path, out: &Path) -> Result<Value, String> {
    let result = verify_artifact_root(root);
    let receipt = emit_law_receipt(root, &result);
    let pretty = serde_json::to_string_pretty(&receipt).map_err(|e| e.to_string())?;
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(out, pretty + "\n").map_err(|e| e.to_string())?;
    if !result.ok {
        return Err(format!(
            "ARTIFACT_EXISTENCE_LAW FAIL: {}",
            result.errors.join(", ")
        ));
    }
    Ok(receipt)
}

pub fn resolve_verify_root(path: &Path) -> PathBuf {
    path.to_path_buf()
}
