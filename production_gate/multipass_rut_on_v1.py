"""Multi-pass rut ON glue — Rust `multipass-rut` oracle.

z1=Bekker; z_N=z1·N^α; Rc(z_N). Teaching. Not densification FEM.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "terramech" / "multipass_rut_on_v1.json"
_BIN_STEM = "ha-physics-gate"
ORACLE = "ha_physics_gate_multipass_rut"
SCHEMA = "ha_multipass_rut_eval_v1"


def find_ha_physics_gate_bin() -> Path:
    env = (os.environ.get("HA_PHYSICS_GATE_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(p)
        return p.resolve()
    name = _BIN_STEM + (".exe" if sys.platform == "win32" else "")
    for candidate in (_REPO / "target" / "release" / name, _REPO / "target" / "debug" / name):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("ha-physics-gate missing — cargo build -p ha_physics_gate --release")


def load_multipass_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def multipass_from_catalog(
    *,
    soil_id: str,
    n_passes: float | None = None,
    p_kpa: float | None = None,
    b_m: float | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_multipass_catalog()
    soil = data["soils"][soil_id]
    d = data["defaults"]
    np = float(d["n_passes"] if n_passes is None else n_passes)
    p = float(d["p_kpa"] if p_kpa is None else p_kpa)
    b = float(d["b_m"] if b_m is None else b_m)
    n = float(soil["n"])
    kc = float(soil["kc"])
    k_phi = float(soil["k_phi"])
    alpha = float(soil["alpha"])
    modulus = kc / b + k_phi
    z1 = 0.0 if p == 0.0 else (p / modulus) ** (1.0 / n)
    z_n = z1 * (np**alpha)
    rc_1 = (b / (n + 1.0)) * modulus * (z1 ** (n + 1.0)) * 1000.0
    rc_n = (b / (n + 1.0)) * modulus * (z_n ** (n + 1.0)) * 1000.0
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "soil_id": soil_id,
        "n_passes": np,
        "alpha": alpha,
        "p_kpa": p,
        "b_m": b,
        "z1_m": z1,
        "z_n_m": z_n,
        "rc_1_n": rc_1,
        "rc_n_n": rc_n,
        "rut_growth_ratio": (z_n / z1) if z1 > 0.0 else 1.0,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_multipass_rut(
    *,
    soil_id: str,
    n_passes: float | None = None,
    p_kpa: float | None = None,
    b_m: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "multipass-rut", f"--catalog={catalog or _CATALOG}", f"--soil-id={soil_id}"]
    if n_passes is not None:
        args.append(f"--n-passes={float(n_passes)}")
    if p_kpa is not None:
        args.append(f"--p-kpa={float(p_kpa)}")
    if b_m is not None:
        args.append(f"--b-m={float(b_m)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad multipass-rut receipt")
    return doc


def assert_mirror_matches_rust(*, soil_id: str, n_passes: float = 10.0, atol: float = 1e-9) -> dict[str, Any]:
    mirror = multipass_from_catalog(soil_id=soil_id, n_passes=n_passes)
    rust = evaluate_multipass_rut(soil_id=soil_id, n_passes=n_passes)
    err = abs(float(mirror["z_n_m"]) - float(rust["z_n_m"])) + abs(float(mirror["rc_n_n"]) - float(rust["rc_n_n"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "soil_id": soil_id, "n_passes": n_passes}
