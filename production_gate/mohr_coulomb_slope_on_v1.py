"""Mohr-Coulomb infinite slope ON glue — Rust `mohr-slope` oracle."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "mohr_coulomb_slope_on_v1.json"
_BIN_STEM = "ha-physics-gate"
ORACLE = "ha_physics_gate_mohr_slope"
SCHEMA = "ha_mohr_coulomb_slope_eval_v1"


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


def load_mohr_slope_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    return json.loads(p.read_text(encoding="utf-8"))


def slope_from_catalog(*, theta_deg: float, z_m: float | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_mohr_slope_catalog()
    soil = data["soil"]
    z = float(data["defaults"]["z_m"] if z_m is None else z_m)
    c_kpa = float(soil["c_kpa"])
    phi = math.radians(float(soil["phi_deg"]))
    th = math.radians(float(theta_deg))
    gamma = float(soil["gamma_kn_m3"])
    fs = c_kpa / (gamma * z * math.sin(th) * math.cos(th)) + math.tan(phi) / math.tan(th)
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "theta_deg": float(theta_deg),
        "z_m": z,
        "c_kpa": c_kpa,
        "phi_deg": float(soil["phi_deg"]),
        "gamma_kn_m3": gamma,
        "fs": fs,
        "stable": fs >= 1.0,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_mohr_slope(*, theta_deg: float, z_m: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "mohr-slope", f"--catalog={catalog or _CATALOG}", f"--theta-deg={float(theta_deg)}"]
    if z_m is not None:
        args.append(f"--z-m={float(z_m)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad mohr-slope receipt")
    return doc


def assert_mirror_matches_rust(*, theta_deg: float, z_m: float | None = None, atol: float = 1e-9) -> dict[str, Any]:
    mirror = slope_from_catalog(theta_deg=theta_deg, z_m=z_m)
    rust = evaluate_mohr_slope(theta_deg=theta_deg, z_m=z_m)
    err = abs(float(mirror["fs"]) - float(rust["fs"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "theta_deg": theta_deg}
