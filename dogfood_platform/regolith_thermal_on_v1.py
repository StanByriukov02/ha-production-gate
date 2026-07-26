"""Regolith thermal k(T) ON glue — Rust `ha-physics-gate thermal-k` oracle.

Law:
  k = k_solid + b_rad * T^3
  if cryo and T < t_cryo: k *= cryo_scale

- `evaluate_thermal_k` → Rust oracle (Dual / depth falsifiers)
- `k_from_catalog` → same equation from ON JSON (integrator hot path mirror)

Not Apollo site MEASURED.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "regolith_thermal_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_thermal_k"
SCHEMA = "ha_regolith_thermal_k_eval_v1"


def _exe_name() -> str:
    return _BIN_STEM + (".exe" if sys.platform == "win32" else "")


def find_ha_physics_gate_bin() -> Path:
    env = (os.environ.get("HA_PHYSICS_GATE_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(f"HA_PHYSICS_GATE_BIN set but not a file: {p}")
        return p.resolve()
    name = _exe_name()
    for candidate in (
        _REPO / "target" / "release" / name,
        _REPO / "target" / "debug" / name,
    ):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "ha-physics-gate binary missing — set HA_PHYSICS_GATE_BIN or "
        "cargo build -p ha_physics_gate --release "
        "(no pure-Python thermal-k oracle)"
    )


def load_regolith_thermal_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def k_from_catalog(
    *,
    material_id: str,
    t_k: float,
    cryo: bool = False,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """ON-catalog equation mirror for integrator hot path — Dual must match Rust."""
    data = catalog or load_regolith_thermal_catalog()
    mats = data.get("materials") or {}
    if material_id not in mats:
        raise KeyError(f"unknown material_id={material_id}")
    mat = mats[material_id]
    k_solid = float(mat["k_solid_w_mk"])
    b_rad = float(mat["b_rad"])
    if not (t_k > 0.0):
        raise ValueError("t_k must be > 0")
    k_base = k_solid + b_rad * (t_k**3)
    cryo_leg = data.get("cryo_leg") or {}
    t_cryo = float(cryo_leg["t_cryo_k"])
    scale = float(cryo_leg["k_scale_below_t_cryo"])
    applied = 1.0
    k_out = k_base
    if cryo and t_k < t_cryo:
        k_out = k_base * scale
        applied = scale
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "material_id": material_id,
        "t_k": t_k,
        "k_solid_w_mk": k_solid,
        "b_rad": b_rad,
        "k_base_w_mk": k_base,
        "k_w_mk": k_out,
        "cryo_applied": cryo and applied < 1.0,
        "cryo_scale_applied": applied,
        "t_cryo_k": t_cryo,
        "cite": list(mat.get("cite") or []),
        "heiken_band_w_mk": list(mat.get("heiken_band_w_mk") or []),
        "honesty": {
            "catalog_mirror_hot_path": True,
            "rust_oracle_for_dual": True,
            "python_not_independent_oracle": True,
            "not_measured": True,
        },
    }


def evaluate_thermal_k(
    *,
    material_id: str,
    t_k: float,
    cryo: bool = False,
    catalog: Path | None = None,
) -> dict[str, Any]:
    """Rust k(T) eval — Dual / depth falsifier surface."""
    bin_path = find_ha_physics_gate_bin()
    cat = catalog or _CATALOG
    args = [
        str(bin_path),
        "thermal-k",
        f"--catalog={cat}",
        f"--material-id={material_id}",
        f"--t-k={float(t_k)}",
    ]
    if cryo:
        args.append("--cryo")

    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

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
        raise RuntimeError(f"ha-physics-gate thermal-k FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA:
        raise RuntimeError("bad thermal-k schema from Rust oracle")
    if doc.get("oracle") != ORACLE:
        raise RuntimeError("thermal-k missing Rust oracle id")
    return doc


def assert_mirror_matches_rust(
    *,
    material_id: str,
    t_k: float,
    cryo: bool = False,
    atol: float = 1e-9,
) -> dict[str, Any]:
    mirror = k_from_catalog(material_id=material_id, t_k=t_k, cryo=cryo)
    rust = evaluate_thermal_k(material_id=material_id, t_k=t_k, cryo=cryo)
    err = abs(float(mirror["k_w_mk"]) - float(rust["k_w_mk"]))
    return {
        "ok": err <= atol,
        "material_id": material_id,
        "t_k": t_k,
        "cryo": cryo,
        "k_mirror": mirror["k_w_mk"],
        "k_rust": rust["k_w_mk"],
        "abs_err": err,
        "atol": atol,
        "oracle": ORACLE,
    }
