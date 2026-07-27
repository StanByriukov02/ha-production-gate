"""Radiation dose-rate ON glue — Rust `ha-physics-gate radiation-rate` oracle.

Law:
  dD = (D_annual / H_year) * dt_h * clamp(flare, lo, hi)

Python is glue only. Catalog: fixtures/open_registry/env/radiation_rate_on_v1.json
Not CREME FEM. Not MEASURED.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "radiation_rate_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_radiation_rate"
SCHEMA = "ha_radiation_rate_eval_v1"


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
        "(no pure-Python radiation-rate oracle)"
    )


def evaluate_radiation_rate(
    *,
    dt_h: float,
    flare_scale: float = 1.0,
    site_id: str = "polar_surface",
    catalog: Path | None = None,
    annual_dose_gy: float | None = None,
    annual_see_per_year: float | None = None,
    flare_lo: float = 1.0,
    flare_hi: float = 12.0,
) -> dict[str, Any]:
    """Rust radiation window eval — catalog site or explicit annual class."""
    bin_path = find_ha_physics_gate_bin()
    args = [str(bin_path), "radiation-rate", f"--dt-h={float(dt_h)}", f"--flare-scale={float(flare_scale)}"]
    if annual_dose_gy is not None:
        args.append(f"--annual-gy={float(annual_dose_gy)}")
        if annual_see_per_year is not None:
            args.append(f"--annual-see={float(annual_see_per_year)}")
        args.append(f"--flare-lo={float(flare_lo)}")
        args.append(f"--flare-hi={float(flare_hi)}")
        if site_id:
            args.append(f"--site-id={site_id}")
    else:
        cat = catalog or _CATALOG
        args.append(f"--catalog={cat}")
        args.append(f"--site-id={site_id}")

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
        raise RuntimeError(f"ha-physics-gate radiation-rate FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA:
        raise RuntimeError("bad radiation-rate schema from Rust oracle")
    if doc.get("oracle") != ORACLE:
        raise RuntimeError("radiation-rate missing Rust oracle id")
    return doc


def load_radiation_rate_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    return json.loads(p.read_text(encoding="utf-8"))
