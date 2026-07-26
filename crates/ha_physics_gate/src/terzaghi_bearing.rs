//! Terzaghi ultimate bearing teaching.

use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub const TERZ_SCHEMA: &str = "ha_terzaghi_bearing_eval_v1";
pub const TERZ_ORACLE: &str = "ha_physics_gate_terzaghi_bearing";

pub fn terzaghi_q_ult(
    c: f64,
    gamma: f64,
    df: f64,
    b: f64,
    nc: f64,
    nq: f64,
    ng: f64,
) -> Result<f64, String> {
    for (name, v) in [
        ("c", c),
        ("gamma", gamma),
        ("df", df),
        ("b", b),
        ("nc", nc),
        ("nq", nq),
        ("ngamma", ng),
    ] {
        if !v.is_finite() || v < 0.0 {
            return Err(format!("{name} must be finite >= 0"));
        }
    }
    if b <= 0.0 {
        return Err("b must be > 0".into());
    }
    Ok(c * nc + gamma * df * nq + 0.5 * gamma * b * ng)
}

pub fn evaluate_terzaghi_bearing(
    pack_id: &str,
    c: f64,
    gamma: f64,
    df: f64,
    b: f64,
    nc: f64,
    nq: f64,
    ng: f64,
) -> Result<Value, String> {
    let q = terzaghi_q_ult(c, gamma, df, b, nc, nq, ng)?;
    Ok(json!({
        "schema": TERZ_SCHEMA,
        "oracle": TERZ_ORACLE,
        "pack_id": pack_id,
        "c_kpa": c,
        "gamma_kn_m3": gamma,
        "df_m": df,
        "b_m": b,
        "nc": nc,
        "nq": nq,
        "ngamma": ng,
        "q_ult_kpa": (q * 1e9).round() / 1e9,
        "equation": "q_ult=c*Nc+gamma*Df*Nq+0.5*gamma*B*Ngamma",
        "honesty": {
            "not_measured": true,
            "python_not_oracle": true,
            "not_fem": true,
            "teaching_terzaghi": true
        }
    }))
}

fn f64_req(obj: &serde_json::Map<String, Value>, key: &str) -> Result<f64, String> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{key} required"))
}

pub fn evaluate_terzaghi_bearing_from_catalog(
    catalog_json: &str,
    pack_id: &str,
) -> Result<Value, String> {
    let root: Value = serde_json::from_str(catalog_json).map_err(|e| format!("catalog JSON: {e}"))?;
    let packs = root
        .get("packs")
        .and_then(|x| x.as_object())
        .ok_or_else(|| "catalog.packs required".to_string())?;
    let pack = packs
        .get(pack_id)
        .and_then(|x| x.as_object())
        .ok_or_else(|| format!("unknown pack={pack_id}"))?;
    let mut doc = evaluate_terzaghi_bearing(
        pack_id,
        f64_req(pack, "c_kpa")?,
        f64_req(pack, "gamma_kn_m3")?,
        f64_req(pack, "df_m")?,
        f64_req(pack, "b_m")?,
        f64_req(pack, "nc")?,
        f64_req(pack, "nq")?,
        f64_req(pack, "ngamma")?,
    )?;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "on_sources".into(),
            root.get("on_sources").cloned().unwrap_or(json!([])),
        );
    }
    Ok(doc)
}

pub fn evaluate_terzaghi_bearing_file(catalog_path: &Path, pack_id: &str) -> Result<Value, String> {
    let text = fs::read_to_string(catalog_path)
        .map_err(|e| format!("read catalog {}: {e}", catalog_path.display()))?;
    evaluate_terzaghi_bearing_from_catalog(&text, pack_id)
}
