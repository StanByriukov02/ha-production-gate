"""1D thermal column step ON glue — Rust `ha-physics-gate thermal-column-step`.

Law: rho*cp*dT/dt = d/dz(k dT/dz) + surface q_in; Picard on k(T) inside Rust.

Dual / embed path: ALWAYS `evaluate_column_step` → Rust oracle.
Python Picard (`universe_env_thermal_column_v1.step_column_implicit_1d`) is
mirror/falsifier only — never Dual thermometer.

Not MEASURED. 1D != 3D FEM.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "regolith_thermal_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_thermal_column"
SCHEMA = "ha_thermal_column_step_eval_v1"


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
        "ha-physics-gate binary missing — cargo build -p ha_physics_gate --release"
    )


def evaluate_column_step(
    *,
    t_k: Sequence[float],
    dt_h: float,
    dz_m: float,
    rho_cp: float,
    q_in_w_m2: float,
    material_id: str = "highland_regolith_loose",
    cryo: bool = False,
    picard: int = 2,
    t_lo: float = 40.0,
    t_hi: float = 400.0,
    catalog: Path | None = None,
) -> dict[str, Any]:
    """Rust thermal-column-step — Dual / depth surface. No Python Picard oracle."""
    bin_path = find_ha_physics_gate_bin()
    cat = catalog or _CATALOG
    temps = ",".join(str(float(t)) for t in t_k)
    args = [
        str(bin_path),
        "thermal-column-step",
        f"--catalog={cat}",
        f"--material-id={material_id}",
        f"--t-k={temps}",
        f"--dt-h={float(dt_h)}",
        f"--dz-m={float(dz_m)}",
        f"--rho-cp={float(rho_cp)}",
        f"--q-in={float(q_in_w_m2)}",
        f"--picard={int(picard)}",
        f"--t-lo={float(t_lo)}",
        f"--t-hi={float(t_hi)}",
    ]
    if cryo:
        args.append("--cryo")

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
        raise RuntimeError(f"ha-physics-gate thermal-column-step FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad thermal-column-step receipt from Rust")
    honesty = dict(doc.get("honesty") or {})
    honesty.update(
        {
            "rust_oracle_for_dual": True,
            "python_picard_not_oracle": True,
            "not_measured": True,
        }
    )
    doc["honesty"] = honesty
    return doc
