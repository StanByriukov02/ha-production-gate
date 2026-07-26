//! Small dense linear algebra (no external dep) for spike sizes n <= 64.

pub fn mat_vec_mul(m: &[Vec<f64>], x: &[f64]) -> Vec<f64> {
    m.iter()
        .map(|row| row.iter().zip(x.iter()).map(|(a, b)| a * b).sum())
        .collect()
}

pub fn mat_mul(a: &[Vec<f64>], b: &[Vec<f64>]) -> Vec<Vec<f64>> {
    let rows = a.len();
    let cols = b[0].len();
    let inner = b.len();
    let mut out = vec![vec![0.0; cols]; rows];
    for i in 0..rows {
        for k in 0..inner {
            for j in 0..cols {
                out[i][j] += a[i][k] * b[k][j];
            }
        }
    }
    out
}

pub fn transpose(m: &[Vec<f64>]) -> Vec<Vec<f64>> {
    if m.is_empty() {
        return vec![];
    }
    let rows = m.len();
    let cols = m[0].len();
    let mut t = vec![vec![0.0; rows]; cols];
    for i in 0..rows {
        for j in 0..cols {
            t[j][i] = m[i][j];
        }
    }
    t
}

/// Solve A x = b by Gaussian elimination with partial pivot (n small).
pub fn solve_symmetric_positive_definite(a: &[Vec<f64>], b: &[f64]) -> Result<Vec<f64>, String> {
    let n = b.len();
    if n == 0 {
        return Ok(vec![]);
    }
    let mut m: Vec<Vec<f64>> = a.iter().map(|row| row.clone()).collect();
    let mut rhs = b.to_vec();

    for col in 0..n {
        // pivot
        let mut piv = col;
        let mut best = m[col][col].abs();
        for r in (col + 1)..n {
            let v = m[r][col].abs();
            if v > best {
                best = v;
                piv = r;
            }
        }
        if best < 1e-14 {
            return Err(format!("singular matrix at col {col}"));
        }
        if piv != col {
            m.swap(col, piv);
            rhs.swap(col, piv);
        }
        let diag = m[col][col];
        for j in col..n {
            m[col][j] /= diag;
        }
        rhs[col] /= diag;
        for r in 0..n {
            if r == col {
                continue;
            }
            let factor = m[r][col];
            if factor.abs() < 1e-15 {
                continue;
            }
            for j in col..n {
                m[r][j] -= factor * m[col][j];
            }
            rhs[r] -= factor * rhs[col];
        }
    }
    Ok(rhs)
}

pub fn l2_norm(v: &[f64]) -> f64 {
    v.iter().map(|x| x * x).sum::<f64>().sqrt()
}

pub fn vec_sub(a: &[f64], b: &[f64]) -> Vec<f64> {
    a.iter().zip(b.iter()).map(|(x, y)| x - y).collect()
}

pub fn max_abs_diff(a: &[f64], b: &[f64]) -> f64 {
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y).abs())
        .fold(0.0_f64, f64::max)
}
