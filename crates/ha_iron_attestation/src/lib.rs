//! H10 BYO iron socket — validate IRON_ATTESTATION_v1.
//! Soft stub is a bridge toward their OTP/HSM — never MEASURED / never product_ready.

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

pub const SCHEMA: &str = "iron_attestation_v1";
pub const FILENAME: &str = "IRON_ATTESTATION_v1.json";
pub const SOFT_STUB_PROVIDER: &str = "ha_soft_stub_v1";
pub const SOFT_STUB_DOMAIN: &str = "HA_IRON_SOFT_STUB_V1";

#[derive(Debug, Clone, Default)]
pub struct IronCheckResult {
    pub present: bool,
    pub ok: bool,
    pub backend: Option<String>,
    pub provider_id: Option<String>,
    pub path: Option<PathBuf>,
    pub errors: Vec<String>,
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(bytes);
    format!("{:x}", h.finalize())
}

/// Deterministic soft-stub response (teaching socket — not OTP MAC).
pub fn soft_stub_response(
    challenge: &str,
    body_sha256: &str,
    blown: bool,
    blow_count: u64,
    current_gate: u64,
) -> String {
    let payload = format!(
        "{SOFT_STUB_DOMAIN}|{challenge}|{}|{}|{blow_count}|{current_gate}",
        body_sha256.to_ascii_lowercase(),
        if blown { "1" } else { "0" }
    );
    sha256_hex(payload.as_bytes())
}

pub fn find_attestation_path(root: &Path, explicit: Option<&Path>) -> Option<PathBuf> {
    if let Some(p) = explicit {
        if p.is_file() {
            return Some(p.to_path_buf());
        }
        return None;
    }
    for cand in [
        root.join(FILENAME),
        root.join("interop").join(FILENAME),
    ] {
        if cand.is_file() {
            return Some(cand);
        }
    }
    None
}

pub fn validate_iron_attestation_v1(value: &Value) -> Result<(), String> {
    let obj = value
        .as_object()
        .ok_or_else(|| "root must be object".to_string())?;
    match obj.get("schema").and_then(|v| v.as_str()) {
        Some(s) if s == SCHEMA => {}
        _ => return Err(format!("schema must be \"{SCHEMA}\"")),
    }
    let backend = obj
        .get("backend")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "backend required".to_string())?;
    match backend {
        "soft_stub" | "otp_device" | "hsm" | "se" => {}
        other => return Err(format!("backend unknown:{other}")),
    }
    if obj.get("provider_id").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
        return Err("provider_id required".into());
    }
    match obj.get("blown") {
        Some(Value::Bool(_)) => {}
        _ => return Err("blown must be bool".into()),
    }
    match obj.get("current_gate") {
        Some(Value::Number(n)) if n.as_u64().is_some() => {}
        _ => return Err("current_gate must be u64".into()),
    }
    match obj.get("blow_count") {
        Some(Value::Number(n)) if n.as_u64().is_some() => {}
        _ => return Err("blow_count must be u64".into()),
    }
    let challenge = obj
        .get("challenge")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if challenge.is_empty() {
        return Err("challenge required".into());
    }
    let response = obj
        .get("response")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if response.is_empty() {
        return Err("response required".into());
    }
    let honesty = obj
        .get("honesty")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "honesty required".to_string())?;
    if honesty.get("not_measured").and_then(|v| v.as_bool()) != Some(true) {
        return Err("honesty.not_measured must be true".into());
    }
    if honesty.get("not_product_ready").and_then(|v| v.as_bool()) != Some(true) {
        return Err("honesty.not_product_ready must be true".into());
    }
    if backend == "soft_stub" {
        if honesty.get("not_otp_silicon").and_then(|v| v.as_bool()) != Some(true) {
            return Err("soft_stub requires honesty.not_otp_silicon=true".into());
        }
        if obj.get("provider_id").and_then(|v| v.as_str()) != Some(SOFT_STUB_PROVIDER) {
            return Err(format!("soft_stub provider_id must be {SOFT_STUB_PROVIDER}"));
        }
    } else if honesty.get("not_otp_silicon").and_then(|v| v.as_bool()) == Some(false) {
        // Real device may set not_otp_silicon=false — still not MEASURED theater via not_measured
    }
    // TABU: attestation must not claim MEASURED / product_ready
    if obj.get("product_ready").and_then(|v| v.as_bool()) == Some(true) {
        return Err("claim_product_ready:attestation".into());
    }
    if let Some(tier) = obj.get("proof_tier").and_then(|v| v.as_str()) {
        let t = tier.to_ascii_uppercase();
        if t.contains("MEASURED") {
            return Err("claim_measured_tier:attestation".into());
        }
    }
    Ok(())
}

fn verify_soft_stub(value: &Value) -> Result<(), String> {
    validate_iron_attestation_v1(value)?;
    let challenge = value.get("challenge").and_then(|v| v.as_str()).unwrap_or("");
    let body = value
        .get("body_sha256")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    let blown = value.get("blown").and_then(|v| v.as_bool()).unwrap_or(true);
    let blow_count = value
        .get("blow_count")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let gate = value
        .get("current_gate")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let want = soft_stub_response(challenge, &body, blown, blow_count, gate);
    let got = value
        .get("response")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if got != want {
        return Err("iron_attestation_response_mismatch".into());
    }
    if blown {
        return Err("iron_attestation_blown".into());
    }
    if gate != 1 {
        return Err("iron_attestation_gate_closed".into());
    }
    Ok(())
}

fn verify_external_provider(attestation_path: &Path) -> Result<(), String> {
    let bin = std::env::var("HA_IRON_PROVIDER_BIN").unwrap_or_default();
    let bin = bin.trim().to_string();
    if bin.is_empty() {
        return Err("iron_provider_missing".into());
    }
    let status = Command::new(&bin)
        .args(["verify", "--attestation", &attestation_path.display().to_string()])
        .status()
        .map_err(|e| format!("iron_provider_exec:{e}"))?;
    if !status.success() {
        return Err("iron_provider_reject".into());
    }
    Ok(())
}

/// Emit soft-stub attestation from live SE_FUSE.bin (+ optional body sha).
pub fn emit_soft_stub_from_fuse(
    fuse_path: &Path,
    body_sha256: Option<&str>,
    challenge: Option<&str>,
) -> Result<Value, String> {
    let st = ha_silicon_fuse::fuse_status(fuse_path)?;
    let blown = st.get("blown").and_then(|v| v.as_bool()).unwrap_or(true);
    let blow_count = st
        .get("blow_count")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let gate = st
        .pointer("/mmio/CURRENT_GATE")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let body = body_sha256
        .map(|s| s.to_ascii_lowercase())
        .or_else(|| {
            st.get("body_sha256")
                .and_then(|v| v.as_str())
                .map(|s| s.to_ascii_lowercase())
        })
        .unwrap_or_default();
    let challenge = challenge.map(|s| s.to_string()).unwrap_or_else(|| {
        let bytes = fs::read(fuse_path).unwrap_or_default();
        format!("soft_stub:{}", sha256_hex(&bytes))
    });
    let response = soft_stub_response(&challenge, &body, blown, blow_count, gate);
    let reuse = reuse_token(&body);
    Ok(json!({
        "schema": SCHEMA,
        "provider_id": SOFT_STUB_PROVIDER,
        "backend": "soft_stub",
        "blown": blown,
        "blow_count": blow_count,
        "current_gate": gate,
        "body_bound": st.get("body_bound").and_then(|v| v.as_bool()).unwrap_or(false),
        "body_sha256": body,
        "reuse_token": reuse,
        "challenge": challenge,
        "response": response,
        "honesty": {
            "not_otp_silicon": true,
            "not_measured": true,
            "not_product_ready": true,
            "file_backed_bridge": true,
            "socket_ready_for_byo_otp": true
        },
        "epsilon": [
            "ε_soft_stub_attestation",
            "ε_file_backed_efuse",
            "ε_soft_not_iron"
        ]
    }))
}

/// Stable token for soft reuse-bar: same body across packs/bots.
pub fn reuse_token(body_sha256: &str) -> String {
    let payload = format!(
        "{SOFT_STUB_DOMAIN}|reuse|{}",
        body_sha256.to_ascii_lowercase()
    );
    sha256_hex(payload.as_bytes())
}

fn identity_sha(root: &Path) -> Option<String> {
    let id_path = root.join("body").join("BODY_IDENTITY_v1.json");
    if !id_path.is_file() {
        return None;
    }
    let id: Value = serde_json::from_str(&fs::read_to_string(id_path).ok()?).ok()?;
    id.get("body_sha256")
        .and_then(|v| v.as_str())
        .map(|s| s.to_ascii_lowercase())
}

fn attestation_doc(root: &Path) -> Result<Value, String> {
    let path = find_attestation_path(root, None).ok_or_else(|| "missing_iron_attestation".to_string())?;
    let text = fs::read_to_string(&path).map_err(|e| format!("iron_attestation_read:{e}"))?;
    serde_json::from_str(&text).map_err(|e| format!("iron_attestation_json:{e}"))
}

/// Soft reuse bar: two roots share body identity + iron attestation reuse_token.
pub fn check_reuse_bar(root_a: &Path, root_b: &Path) -> Result<Value, Vec<String>> {
    let mut errors = Vec::new();
    let a = check_iron_at_root(root_a, None, true, false);
    let b = check_iron_at_root(root_b, None, true, false);
    if !a.ok {
        errors.extend(a.errors.iter().map(|e| format!("a:{e}")));
    }
    if !b.ok {
        errors.extend(b.errors.iter().map(|e| format!("b:{e}")));
    }
    let sha_a = identity_sha(root_a).or_else(|| {
        attestation_doc(root_a)
            .ok()
            .and_then(|d| d.get("body_sha256").and_then(|v| v.as_str()).map(|s| s.to_ascii_lowercase()))
    });
    let sha_b = identity_sha(root_b).or_else(|| {
        attestation_doc(root_b)
            .ok()
            .and_then(|d| d.get("body_sha256").and_then(|v| v.as_str()).map(|s| s.to_ascii_lowercase()))
    });
    match (&sha_a, &sha_b) {
        (Some(x), Some(y)) if x == y && !x.is_empty() => {}
        (Some(_), Some(_)) => errors.push("reuse_body_mismatch".into()),
        _ => errors.push("reuse_body_missing".into()),
    }
    let tok_a = attestation_doc(root_a)
        .ok()
        .and_then(|d| d.get("reuse_token").and_then(|v| v.as_str()).map(|s| s.to_string()));
    let tok_b = attestation_doc(root_b)
        .ok()
        .and_then(|d| d.get("reuse_token").and_then(|v| v.as_str()).map(|s| s.to_string()));
    match (&tok_a, &tok_b) {
        (Some(x), Some(y)) if x == y && !x.is_empty() => {}
        (Some(_), Some(_)) => errors.push("reuse_token_mismatch".into()),
        _ => {
            // Derive from body if soft stubs omitted token (older packs)
            if let (Some(sa), Some(sb)) = (&sha_a, &sha_b) {
                if sa == sb && !sa.is_empty() {
                    // ok without explicit token when body matches and both iron ok
                } else {
                    errors.push("reuse_token_missing".into());
                }
            } else {
                errors.push("reuse_token_missing".into());
            }
        }
    }
    if !errors.is_empty() {
        return Err(errors);
    }
    Ok(json!({
        "schema": "iron_reuse_bar_v1",
        "ok": true,
        "body_sha256": sha_a,
        "reuse_token": tok_a.or_else(|| sha_a.as_ref().map(|s| reuse_token(s))),
        "honesty": {
            "not_measured": true,
            "not_product_ready": true,
            "sim_slice_reuse": true
        }
    }))
}

pub fn check_iron_at_root(
    root: &Path,
    explicit: Option<&Path>,
    require_iron: bool,
    reject_soft_stub: bool,
) -> IronCheckResult {
    let mut out = IronCheckResult::default();
    let path = match find_attestation_path(root, explicit) {
        Some(p) => p,
        None => {
            if require_iron {
                out.errors.push("missing_iron_attestation".into());
            }
            return out;
        }
    };
    out.present = true;
    out.path = Some(path.clone());
    let text = match fs::read_to_string(&path) {
        Ok(t) => t,
        Err(e) => {
            out.errors.push(format!("iron_attestation_read:{e}"));
            return out;
        }
    };
    let value: Value = match serde_json::from_str(&text) {
        Ok(v) => v,
        Err(e) => {
            out.errors.push(format!("iron_attestation_json:{e}"));
            return out;
        }
    };
    if let Err(e) = validate_iron_attestation_v1(&value) {
        out.errors.push(format!("iron_attestation:{e}"));
        return out;
    }
    let backend = value
        .get("backend")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    out.backend = Some(backend.clone());
    out.provider_id = value
        .get("provider_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    // Body bind coherence when both present
    let id_path = root.join("body").join("BODY_IDENTITY_v1.json");
    if id_path.is_file() {
        if let Ok(id) = serde_json::from_str::<Value>(&fs::read_to_string(&id_path).unwrap_or_default())
        {
            let want = id
                .get("body_sha256")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_ascii_lowercase();
            let got = value
                .get("body_sha256")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_ascii_lowercase();
            if !want.is_empty() && !got.is_empty() && want != got {
                out.errors.push("iron_attestation_body_mismatch".into());
            }
        }
    }

    if backend == "soft_stub" {
        if reject_soft_stub {
            out.errors.push("iron_soft_stub_rejected".into());
            return out;
        }
        if let Err(e) = verify_soft_stub(&value) {
            out.errors.push(e);
            return out;
        }
    } else if let Err(e) = verify_external_provider(&path) {
        out.errors.push(e);
        return out;
    } else {
        // External provider accepted — still refuse blown / closed gate fields
        if value.get("blown").and_then(|v| v.as_bool()).unwrap_or(true) {
            out.errors.push("iron_attestation_blown".into());
            return out;
        }
        if value.get("current_gate").and_then(|v| v.as_u64()).unwrap_or(0) != 1 {
            out.errors.push("iron_attestation_gate_closed".into());
            return out;
        }
    }

    out.ok = out.errors.is_empty();
    out
}
