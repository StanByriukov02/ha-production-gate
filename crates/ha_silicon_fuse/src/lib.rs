//! H6-iron silicon fuse — FFI to C eFUSE + JSON validate.
//! Oracle for blow/status/bind/current_gate is C.

use serde_json::Value;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::path::Path;

pub const SCHEMA: &str = "silicon_fuse_v1";

extern "C" {
    fn ha_fuse_ensure(path: *const c_char) -> i32;
    fn ha_fuse_status_json(path: *const c_char, out: *mut c_char, out_cap: usize) -> i32;
    fn ha_fuse_blow(path: *const c_char, lie_score: f64) -> i32;
    fn ha_fuse_bind_body(path: *const c_char, sha256_hex: *const c_char) -> i32;
    fn ha_fuse_current_gate(path: *const c_char) -> i32;
}

fn path_c(path: &Path) -> Result<CString, String> {
    let s = path
        .to_str()
        .ok_or_else(|| "fuse path must be UTF-8".to_string())?;
    CString::new(s).map_err(|_| "fuse path contains NUL".to_string())
}

fn map_c_err(code: i32) -> String {
    let abs = code.unsigned_abs();
    match abs {
        1 => "HA_FUSE_ERR_IO".into(),
        2 => "HA_FUSE_ERR_MAGIC".into(),
        3 => "HA_FUSE_ERR_ARG".into(),
        4 => "HA_FUSE_ERR_BUF".into(),
        5 => "HA_FUSE_ERR_TAMPER".into(),
        6 => "HA_FUSE_ERR_BOUND".into(),
        other => format!("HA_FUSE_ERR_{other}"),
    }
}

pub fn fuse_ensure(path: &Path) -> Result<(), String> {
    let c = path_c(path)?;
    let rc = unsafe { ha_fuse_ensure(c.as_ptr()) };
    if rc != 0 {
        return Err(map_c_err(rc));
    }
    Ok(())
}

pub fn fuse_status(path: &Path) -> Result<Value, String> {
    let c = path_c(path)?;
    let mut buf = vec![0u8; 4096];
    let rc = unsafe {
        ha_fuse_status_json(c.as_ptr(), buf.as_mut_ptr() as *mut c_char, buf.len())
    };
    if rc != 0 {
        return Err(map_c_err(rc));
    }
    let text = unsafe { CStr::from_ptr(buf.as_ptr() as *const c_char) }
        .to_str()
        .map_err(|_| "status json not utf-8".to_string())?;
    let value: Value =
        serde_json::from_str(text).map_err(|e| format!("status json parse: {e}"))?;
    validate_silicon_fuse_v1(&value)?;
    Ok(value)
}

pub fn fuse_blow(path: &Path, lie_score: f64) -> Result<Value, String> {
    let c = path_c(path)?;
    let rc = unsafe { ha_fuse_blow(c.as_ptr(), lie_score) };
    if rc != 0 {
        return Err(map_c_err(rc));
    }
    fuse_status(path)
}

pub fn fuse_bind_body(path: &Path, sha256_hex: &str) -> Result<Value, String> {
    let c = path_c(path)?;
    let hex = CString::new(sha256_hex.trim().to_ascii_lowercase())
        .map_err(|_| "sha256 contains NUL".to_string())?;
    let rc = unsafe { ha_fuse_bind_body(c.as_ptr(), hex.as_ptr()) };
    if rc != 0 {
        return Err(map_c_err(rc));
    }
    fuse_status(path)
}

/// true if current may flow (fuse not blown).
pub fn fuse_current_allowed(path: &Path) -> Result<bool, String> {
    let c = path_c(path)?;
    let rc = unsafe { ha_fuse_current_gate(c.as_ptr()) };
    if rc < 0 {
        return Err(map_c_err(rc));
    }
    Ok(rc == 1)
}

pub fn validate_silicon_fuse_v1(value: &Value) -> Result<(), String> {
    let obj = value
        .as_object()
        .ok_or_else(|| "root must be object".to_string())?;
    match obj.get("schema").and_then(|v| v.as_str()) {
        Some(s) if s == SCHEMA => {}
        _ => return Err(format!("schema must be \"{SCHEMA}\"")),
    }
    match obj.get("blown") {
        Some(Value::Bool(_)) => {}
        _ => return Err("blown must be bool".into()),
    }
    match obj.get("irreversible") {
        Some(Value::Bool(true)) => {}
        _ => return Err("irreversible must be true".into()),
    }
    match obj.get("backend").and_then(|v| v.as_str()) {
        Some("c_file_efuse") => {}
        _ => return Err("backend must be c_file_efuse".into()),
    }
    if let Some(mmio) = obj.get("mmio") {
        let m = mmio
            .as_object()
            .ok_or_else(|| "mmio must be object".to_string())?;
        if !m.contains_key("APOPTOSIS_FUSE") || !m.contains_key("CURRENT_GATE") {
            return Err("mmio requires APOPTOSIS_FUSE and CURRENT_GATE".into());
        }
        let blown = obj.get("blown").and_then(|v| v.as_bool()).unwrap_or(false);
        let apo = m
            .get("APOPTOSIS_FUSE")
            .and_then(|v| v.as_u64())
            .unwrap_or(999);
        let gate = m
            .get("CURRENT_GATE")
            .and_then(|v| v.as_u64())
            .unwrap_or(999);
        let expect_apo = if blown { 1 } else { 0 };
        let expect_gate = if blown { 0 } else { 1 };
        if apo != expect_apo || gate != expect_gate {
            return Err("mmio incoherent with blown".into());
        }
    }
    if obj.get("body_bound").and_then(|v| v.as_bool()).unwrap_or(false) {
        match obj.get("body_sha256").and_then(|v| v.as_str()) {
            Some(h) if h.len() == 64 && h.chars().all(|c| c.is_ascii_hexdigit()) => {}
            _ => return Err("body_bound requires body_sha256 64-hex".into()),
        }
    }
    Ok(())
}

pub fn validate_silicon_fuse_json(text: &str) -> Result<(), Vec<String>> {
    let value: Value = match serde_json::from_str(text) {
        Ok(v) => v,
        Err(e) => return Err(vec![format!("invalid JSON: {e}")]),
    };
    match validate_silicon_fuse_v1(&value) {
        Ok(()) => Ok(()),
        Err(e) => Err(vec![e]),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    #[test]
    fn ensure_blow_bind_current_gate() {
        let dir = env::temp_dir().join(format!("ha_fuse_test_{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let path = dir.join("SE_FUSE.bin");
        let _ = std::fs::remove_file(&path);
        fuse_ensure(&path).expect("ensure");
        assert!(fuse_current_allowed(&path).unwrap());
        let empty =
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
        let st = fuse_bind_body(&path, empty).expect("bind");
        assert_eq!(st["body_bound"], true);
        assert_eq!(st["body_sha256"], empty);
        assert_eq!(st["mmio"]["CURRENT_GATE"], 1);
        fuse_blow(&path, 3.5).expect("blow");
        assert!(!fuse_current_allowed(&path).unwrap());
        let st2 = fuse_status(&path).unwrap();
        assert_eq!(st2["mmio"]["CURRENT_GATE"], 0);
        assert_eq!(st2["mmio"]["APOPTOSIS_FUSE"], 1);
        assert_eq!(st2["body_bound"], true); // bind survives blow
        // Hand-clear blown with blow_count>0 must be TAMPER, not healed by ensure
        let mut raw = std::fs::read(&path).expect("read fuse");
        assert!(raw.len() >= 13);
        raw[12] = 0;
        std::fs::write(&path, &raw).expect("write tamper");
        let err = fuse_status(&path).expect_err("tamper must fail");
        assert!(err.contains("TAMPER"), "got {err}");
        let _ = std::fs::remove_file(&path);
        let _ = std::fs::remove_dir(&dir);
    }
}
