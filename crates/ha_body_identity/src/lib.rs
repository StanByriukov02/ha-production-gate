use sha2::{Digest, Sha256};
use serde_json::Value;
use std::fs;
use std::io;
use std::path::Path;

pub const SCHEMA: &str = "body_identity_v1";

/// Lowercase hex SHA-256 of `data`.
pub fn hash_bytes(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    format!("{:x}", hasher.finalize())
}

/// SHA-256 hex digest of file contents.
pub fn hash_file(path: &Path) -> io::Result<String> {
    let data = fs::read(path)?;
    Ok(hash_bytes(&data))
}

fn is_lower_hex64(s: &str) -> bool {
    s.len() == 64 && s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn non_empty_str(v: &Value) -> Option<&str> {
    v.as_str().filter(|s| !s.is_empty())
}

/// Validate a `body_identity_v1` JSON document (string or object value).
pub fn validate_body_identity_v1(json: &str) -> Result<(), Vec<String>> {
    let root: Value = match serde_json::from_str(json) {
        Ok(v) => v,
        Err(e) => return Err(vec![format!("invalid JSON: {e}")]),
    };

    let obj = match root.as_object() {
        Some(o) => o,
        None => return Err(vec!["root must be a JSON object".into()]),
    };

    let mut errors = Vec::new();

    match obj.get("schema") {
        Some(Value::String(s)) if s == SCHEMA => {}
        _ => errors.push(format!("schema must be \"{SCHEMA}\"")),
    }

    match obj.get("body_sha256") {
        Some(Value::String(s)) if is_lower_hex64(s) => {}
        _ => errors.push("body_sha256 must be 64 lowercase hex characters".into()),
    }

    match obj.get("kind") {
        Some(v) if non_empty_str(v).is_some() => {}
        _ => errors.push("kind must be a non-empty string".into()),
    }

    match obj.get("source_name") {
        Some(v) if non_empty_str(v).is_some() => {}
        _ => errors.push("source_name must be a non-empty string".into()),
    }

    if let Some(v) = obj.get("bytes_len") {
        match v.as_u64() {
            Some(_) => {}
            None => errors.push("bytes_len must be a non-negative integer (u64)".into()),
        }
    }

    for key in ["chain_id", "root_link", "ee_link"] {
        if let Some(v) = obj.get(key) {
            if !v.is_string() {
                errors.push(format!("{key} must be a string when present"));
            }
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

/// Build a `body_identity_v1` JSON value from file bytes and metadata.
pub fn emit_body_identity_v1(
    body_sha256: &str,
    bytes_len: u64,
    kind: &str,
    source_name: &str,
    chain_id: Option<&str>,
) -> Value {
    let mut obj = serde_json::Map::new();
    obj.insert(
        "schema".into(),
        Value::String(SCHEMA.into()),
    );
    obj.insert(
        "body_sha256".into(),
        Value::String(body_sha256.into()),
    );
    obj.insert("kind".into(), Value::String(kind.into()));
    obj.insert(
        "source_name".into(),
        Value::String(source_name.into()),
    );
    obj.insert(
        "bytes_len".into(),
        Value::Number(bytes_len.into()),
    );
    if let Some(id) = chain_id {
        obj.insert("chain_id".into(), Value::String(id.into()));
    }
    Value::Object(obj)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_empty_vector() {
        assert_eq!(
            hash_bytes(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    #[test]
    fn validate_rejects_missing_required_fields() {
        let err = validate_body_identity_v1("{}").unwrap_err();
        assert!(err.iter().any(|e| e.contains("schema")));
        assert!(err.iter().any(|e| e.contains("body_sha256")));
        assert!(err.iter().any(|e| e.contains("kind")));
        assert!(err.iter().any(|e| e.contains("source_name")));
    }

    #[test]
    fn validate_accepts_minimal_valid() {
        let json = r#"{
            "schema": "body_identity_v1",
            "body_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "kind": "preset",
            "source_name": "empty.bin"
        }"#;
        validate_body_identity_v1(json).expect("valid");
    }
}