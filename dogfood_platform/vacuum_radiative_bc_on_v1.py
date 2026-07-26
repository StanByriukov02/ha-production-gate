"""Vacuum radiative BC ON glue — Rust `ha-physics-gate radiative-bc` oracle.

Law:
  q_rad   = eps * sigma * (T^4 - T_sky^4)
  q_solar = (1 - A) * S * illum
  q_net   = q_rad - q_solar

- `evaluate_radiative_bc` → Rust oracle (Dual falsifiers)
- `flux_from_catalog` → same equation from ON JSON (hot path mirror)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "vacuum_radiative_bc_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_radiative_bc"
SCHEMA = "ha_vacuum_radiative_bc_eval_v1"


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
        "(no pure-Python radiative-bc oracle)"
    )


def load_radiative_bc_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def flux_from_catalog(
    *,
    zone: str,
    t_k: float,
    illum: float | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_radiative_bc_catalog()
    constants = data["constants"]
    sky = data["sky_temperature_k"]
    zones = data["zones"]
    if zone not in zones:
        raise KeyError(f"unknown zone={zone}")
    zrow = zones[zone]
    sigma = float(constants["stefan_boltzmann_w_m2_k4"])
    eps = float(constants["surface_emissivity_regolith"])
    solar = float(constants["solar_constant_w_m2"])
    albedo = float(constants["albedo_highland"])
    t_sky_rad = float(sky["deep_space"])
    ambient_key = str(zrow["sky_ambient_from"])
    t_sky_ambient = float(sky[ambient_key])
    if illum is not None:
        illum_v = float(illum)
    elif "default_illum" in zrow:
        illum_v = float(zrow["default_illum"])
    else:
        illum_v = float(constants[str(zrow["default_illum_from"])])
    q_rad = eps * sigma * (t_k**4 - t_sky_rad**4)
    q_solar = (1.0 - albedo) * solar * illum_v
    q_net = q_rad - q_solar
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "zone": zone,
        "t_surf_k": t_k,
        "t_sky_rad_k": t_sky_rad,
        "t_sky_ambient_k": t_sky_ambient,
        "q_rad_w_m2": q_rad,
        "q_solar_w_m2": q_solar,
        "q_net_w_m2": q_net,
        "q_in_surface_w_m2": -q_net,
        "illum_frac": illum_v,
        "emissivity": eps,
        "albedo": albedo,
        "solar_constant_w_m2": solar,
        "honesty": {
            "catalog_mirror_hot_path": True,
            "rust_oracle_for_dual": True,
            "python_not_independent_oracle": True,
            "not_measured": True,
        },
    }


def evaluate_radiative_bc(
    *,
    zone: str,
    t_k: float,
    illum: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    bin_path = find_ha_physics_gate_bin()
    cat = catalog or _CATALOG
    args = [
        str(bin_path),
        "radiative-bc",
        f"--catalog={cat}",
        f"--zone={zone}",
        f"--t-k={float(t_k)}",
    ]
    if illum is not None:
        args.append(f"--illum={float(illum)}")

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
        raise RuntimeError(f"ha-physics-gate radiative-bc FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA:
        raise RuntimeError("bad radiative-bc schema from Rust oracle")
    if doc.get("oracle") != ORACLE:
        raise RuntimeError("radiative-bc missing Rust oracle id")
    return doc


def assert_mirror_matches_rust(
    *,
    zone: str,
    t_k: float,
    illum: float | None = None,
    atol: float = 1e-4,
) -> dict[str, Any]:
    mirror = flux_from_catalog(zone=zone, t_k=t_k, illum=illum)
    rust = evaluate_radiative_bc(zone=zone, t_k=t_k, illum=illum)
    err = abs(float(mirror["q_net_w_m2"]) - float(rust["q_net_w_m2"]))
    return {
        "ok": err <= atol,
        "zone": zone,
        "t_k": t_k,
        "q_net_mirror": mirror["q_net_w_m2"],
        "q_net_rust": rust["q_net_w_m2"],
        "abs_err": err,
        "atol": atol,
        "oracle": ORACLE,
    }
