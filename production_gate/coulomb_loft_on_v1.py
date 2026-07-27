"""Coulomb loft ON glue — Rust `ha-physics-gate coulomb-loft` oracle.

q=4πε0 r φ; E=|φ|/λ_D; loft_ratio=|q|E/(m g). Stubbs fountain teaching.
Not PIC. Not MEASURED.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "coulomb_loft_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_coulomb_loft"
SCHEMA = "ha_coulomb_loft_eval_v1"


def _exe_name() -> str:
    return _BIN_STEM + (".exe" if sys.platform == "win32" else "")


def find_ha_physics_gate_bin() -> Path:
    env = (os.environ.get("HA_PHYSICS_GATE_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(p)
        return p.resolve()
    name = _exe_name()
    for candidate in (
        _REPO / "target" / "release" / name,
        _REPO / "target" / "debug" / name,
    ):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("ha-physics-gate missing — cargo build -p ha_physics_gate --release")


def load_coulomb_loft_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def loft_from_catalog(
    *,
    phi_v: float,
    r_um: float | None = None,
    rho_kg_m3: float | None = None,
    lambda_d_m: float | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_coulomb_loft_catalog()
    c = data["constants"]
    d = data["defaults"]
    eps0 = float(c["epsilon0"])
    pi = float(c["pi"])
    g = float(c["g_moon_m_s2"])
    r_u = float(d["r_um"] if r_um is None else r_um)
    rho = float(d["rho_kg_m3"] if rho_kg_m3 is None else rho_kg_m3)
    lam = float(d["lambda_d_m"] if lambda_d_m is None else lambda_d_m)
    r_m = r_u * 1.0e-6
    q = 4.0 * pi * eps0 * r_m * float(phi_v)
    e_field = abs(float(phi_v)) / lam
    f_e = abs(q) * e_field
    mass = (4.0 / 3.0) * pi * (r_m**3) * rho
    f_g = mass * g
    ratio = f_e / f_g
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "phi_v": float(phi_v),
        "r_um": r_u,
        "r_m": r_m,
        "rho_kg_m3": rho,
        "lambda_d_m": lam,
        "g_m_s2": g,
        "q_c": q,
        "e_v_per_m": e_field,
        "f_e_n": f_e,
        "f_g_n": f_g,
        "loft_ratio": ratio,
        "lofts": ratio > 1.0,
        "honesty": {
            "catalog_mirror_hot_path": True,
            "rust_oracle_for_dual": True,
            "not_pic": True,
            "not_measured": True,
        },
    }


def evaluate_coulomb_loft(
    *,
    phi_v: float,
    r_um: float | None = None,
    rho_kg_m3: float | None = None,
    lambda_d_m: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    bin_path = find_ha_physics_gate_bin()
    cat = catalog or _CATALOG
    args = [str(bin_path), "coulomb-loft", f"--catalog={cat}", f"--phi-v={float(phi_v)}"]
    if r_um is not None:
        args.append(f"--r-um={float(r_um)}")
    if rho_kg_m3 is not None:
        args.append(f"--rho={float(rho_kg_m3)}")
    if lambda_d_m is not None:
        args.append(f"--lambda-d={float(lambda_d_m)}")
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    proc = subprocess.run(
        args,
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=60.0,
        check=False,
        **hidden_run_kwargs(),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-physics-gate coulomb-loft FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad coulomb-loft receipt")
    return doc


def assert_mirror_matches_rust(
    *,
    phi_v: float,
    r_um: float = 1.0,
    atol: float = 1e-6,
) -> dict[str, Any]:
    mirror = loft_from_catalog(phi_v=phi_v, r_um=r_um)
    rust = evaluate_coulomb_loft(phi_v=phi_v, r_um=r_um)
    err = abs(float(mirror["loft_ratio"]) - float(rust["loft_ratio"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "phi_v": phi_v, "r_um": r_um}
