//! H7 Energy Ledger — claim without converging balance = NULL.
//! Kinetic tax: thought burns joules ∝ proposed action magnitude (soft ε).

use serde_json::{json, Value};

pub const SCHEMA: &str = "energy_claim_v1";
pub const DEFAULT_ABS_TOL: f64 = 1e-9;
pub const DEFAULT_TAX_BASE_J: f64 = 0.001;
pub const DEFAULT_TAX_ALPHA: f64 = 0.01;

/// Soft kinetic tax: base + alpha * |magnitude|.
pub fn kinetic_tax_joules(magnitude: f64, base_j: f64, alpha: f64) -> f64 {
    let m = magnitude.abs();
    if !m.is_finite() || !base_j.is_finite() || !alpha.is_finite() {
        return f64::NAN;
    }
    base_j.max(0.0) + alpha.max(0.0) * m
}

/// Compaction work proxy: W ≈ |Rc| · |distance| (N·m = J).
/// Teaching Dual consequence from Wong Rc — not MEASURED calorimeter.
pub fn compaction_work_joules(rc_n: f64, distance_m: f64) -> f64 {
    if !(rc_n.is_finite() && distance_m.is_finite()) {
        return f64::NAN;
    }
    rc_n.abs() * distance_m.abs()
}

/// Sum of `lines[].joules` (finite only).
pub fn sum_line_joules(lines: &[Value]) -> Result<f64, String> {
    let mut sum = 0.0_f64;
    for (i, line) in lines.iter().enumerate() {
        let j = line
            .get("joules")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| format!("lines[{i}].joules must be a finite number"))?;
        if !j.is_finite() {
            return Err(format!("lines[{i}].joules must be finite"));
        }
        sum += j;
    }
    Ok(sum)
}

/// Validate energy_claim_v1 JSON text. Balance must be within abs_tol of zero.
pub fn validate_energy_claim_v1(json: &str, abs_tol: f64) -> Result<(), Vec<String>> {
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

    match obj.get("unit") {
        Some(Value::String(s)) if s == "J" => {}
        _ => errors.push("unit must be \"J\"".into()),
    }

    let lines = match obj.get("lines").and_then(|v| v.as_array()) {
        Some(a) if !a.is_empty() => a,
        _ => {
            errors.push("lines must be a non-empty array".into());
            return Err(errors);
        }
    };

    for (i, line) in lines.iter().enumerate() {
        let Some(o) = line.as_object() else {
            errors.push(format!("lines[{i}] must be an object"));
            continue;
        };
        match o.get("role").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => {}
            _ => errors.push(format!("lines[{i}].role must be a non-empty string")),
        }
        match o.get("joules").and_then(|v| v.as_f64()) {
            Some(j) if j.is_finite() => {}
            _ => errors.push(format!("lines[{i}].joules must be a finite number")),
        }
    }

    if !errors.is_empty() {
        return Err(errors);
    }

    let sum = match sum_line_joules(lines) {
        Ok(s) => s,
        Err(e) => {
            errors.push(e);
            return Err(errors);
        }
    };
    if sum.abs() > abs_tol {
        errors.push(format!(
            "energy_claim_unbalanced: sum_joules={sum} abs_tol={abs_tol}"
        ));
    }

    if let Some(bal) = obj.get("balance_joules").and_then(|v| v.as_f64()) {
        if !bal.is_finite() {
            errors.push("balance_joules must be finite".into());
        } else if (bal - sum).abs() > abs_tol {
            errors.push(format!(
                "balance_joules_mismatch: field={bal} sum={sum}"
            ));
        }
    }

    let tax = obj
        .get("kinetic_tax_joules")
        .and_then(|v| v.as_f64());
    match tax {
        Some(t) if t.is_finite() && t >= 0.0 => {
            let spent_tax = lines.iter().find_map(|line| {
                let role = line.get("role")?.as_str()?;
                if role == "spent_thought_tax" {
                    line.get("joules")?.as_f64()
                } else {
                    None
                }
            });
            match spent_tax {
                Some(j) if (j + t).abs() <= abs_tol => {}
                Some(j) => errors.push(format!(
                    "kinetic_tax_line_mismatch: kinetic_tax_joules={t} spent_thought_tax={j}"
                )),
                None => errors.push("missing_line:spent_thought_tax".into()),
            }
        }
        Some(_) => errors.push("kinetic_tax_joules must be finite and >= 0".into()),
        None => errors.push("kinetic_tax_joules required".into()),
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

/// Emit a balanced energy_claim_v1.
/// Convention: budget (+) · spent_actuation (−) · spent_thought_tax (−) · residual (± to close).
pub fn emit_energy_claim_v1(
    budget_j: f64,
    spent_actuation_j: f64,
    kinetic_tax_j: f64,
    claim_id: &str,
) -> Result<Value, String> {
    if !(budget_j.is_finite() && spent_actuation_j.is_finite() && kinetic_tax_j.is_finite()) {
        return Err("all joules must be finite".into());
    }
    if budget_j < 0.0 {
        return Err("budget_j must be >= 0".into());
    }
    if spent_actuation_j < 0.0 {
        return Err("spent_actuation_j must be >= 0 (magnitude; sign applied in lines)".into());
    }
    if kinetic_tax_j < 0.0 {
        return Err("kinetic_tax_j must be >= 0".into());
    }
    let residual = budget_j - spent_actuation_j - kinetic_tax_j;
    let lines = vec![
        json!({"role": "budget", "joules": budget_j}),
        json!({"role": "spent_actuation", "joules": -spent_actuation_j}),
        json!({"role": "spent_thought_tax", "joules": -kinetic_tax_j}),
        json!({"role": "residual", "joules": -residual}),
    ];
    let sum = sum_line_joules(&lines)?;
    Ok(json!({
        "schema": SCHEMA,
        "claim_id": claim_id,
        "unit": "J",
        "lines": lines,
        "balance_joules": sum,
        "kinetic_tax_joules": kinetic_tax_j,
        "budget_joules": budget_j,
        "spent_actuation_joules": spent_actuation_j,
        "residual_joules": residual,
        "honesty": {
            "not_measured": true,
            "sim_slice": true,
            "epsilon": ["ε_sim_slice_joules", "ε_soft_kinetic_tax", "ε_soft_not_iron", "ε_compaction_work_from_rc"]
        }
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tax_scales_with_magnitude() {
        let a = kinetic_tax_joules(0.0, 0.001, 0.01);
        let b = kinetic_tax_joules(2.0, 0.001, 0.01);
        assert!((a - 0.001).abs() < 1e-12);
        assert!((b - 0.021).abs() < 1e-12);
    }

    #[test]
    fn emit_balances() {
        let v = emit_energy_claim_v1(1.0, 0.4, 0.021, "c1").unwrap();
        let text = serde_json::to_string(&v).unwrap();
        validate_energy_claim_v1(&text, DEFAULT_ABS_TOL).expect("balanced");
    }

    #[test]
    fn unbalanced_fails() {
        let bad = r#"{
            "schema": "energy_claim_v1",
            "unit": "J",
            "kinetic_tax_joules": 0.1,
            "lines": [
                {"role": "budget", "joules": 1.0},
                {"role": "spent_thought_tax", "joules": -0.1}
            ]
        }"#;
        let err = validate_energy_claim_v1(bad, DEFAULT_ABS_TOL).unwrap_err();
        assert!(err.iter().any(|e| e.contains("unbalanced")));
    }

    #[test]
    fn compaction_work_scales() {
        let w = compaction_work_joules(10.0, 0.5);
        assert!((w - 5.0).abs() < 1e-12);
    }
}
