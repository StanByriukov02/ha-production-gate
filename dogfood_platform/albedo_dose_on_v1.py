"""Albedo dose ON glue — Rust `ha-physics-gate albedo-dose` oracle.

Law:
  f_alb = min(ceiling, f0*site*(1+(mf-1)*gauss(g)))
  total = anchor * (1+(mt-1)*gauss(g))
  albedo = total * f_alb; incident = total - albedo

- `evaluate_albedo_dose` → Rust Dual oracle
- `albedo_from_catalog` → same equation (hot-path mirror)

Not CREME FEM. Not MEASURED.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "albedo_dose_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_albedo_dose"
SCHEMA = "ha_albedo_dose_eval_v1"


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


def load_albedo_dose_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def _gauss(g: float, peak: float, sigma: float, peak_mult: float) -> float:
    bump = (peak_mult - 1.0) * math.exp(-0.5 * ((g - peak) / max(sigma, 1e-12)) ** 2)
    return 1.0 + bump


def albedo_from_catalog(
    *,
    site_class: str,
    shield_g_cm2: float,
    dose_anchor_gy: float,
    see_base: float | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_albedo_dose_catalog()
    f0 = float(data["f0"])
    ceiling = float(data["fraction_ceiling"])
    sites = data["site_class_modifiers"]
    if site_class not in sites:
        raise KeyError(f"unknown site_class={site_class}")
    site_scale = float(sites[site_class]["f_albedo_scale"])
    paradox = data["shield_paradox"]
    peak_g = float(paradox["peak_areal_g_cm2"])
    frac_peak = float(paradox["fraction_multiplier_at_peak"])
    tot_peak = float(paradox["total_dose_multiplier_at_peak"])
    sigma = float(paradox["sigma_g_cm2"])
    see = data["see_albedo_coupling"]
    see_b = float(see_base if see_base is not None else see["base_see_per_yr"])
    see_gain = float(see["albedo_neutron_gain"])
    f_base = f0 * site_scale
    frac_mult = _gauss(shield_g_cm2, peak_g, sigma, frac_peak)
    tot_mult = _gauss(shield_g_cm2, peak_g, sigma, tot_peak)
    f_eff = min(ceiling, f_base * frac_mult)
    total = dose_anchor_gy * tot_mult
    albedo = total * f_eff
    incident = total - albedo
    see_rate = see_b * (1.0 + see_gain * max(0.0, f_eff / max(f_base, 1e-12) - 1.0))
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "site_class": site_class,
        "shield_g_cm2": shield_g_cm2,
        "dose_anchor_gy": dose_anchor_gy,
        "albedo_fraction_base": f_base,
        "albedo_fraction": f_eff,
        "shield_paradox_multiplier": tot_mult,
        "fraction_paradox_multiplier": frac_mult,
        "total_dose_gy": total,
        "albedo_dose_gy": albedo,
        "incident_dose_gy": incident,
        "see_rate_per_year": see_rate,
        "honesty": {
            "catalog_mirror_hot_path": True,
            "rust_oracle_for_dual": True,
            "python_not_independent_oracle": True,
            "not_measured": True,
            "not_creme_fem": True,
        },
    }


def evaluate_albedo_dose(
    *,
    site_class: str,
    shield_g_cm2: float,
    dose_anchor_gy: float,
    see_base: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    bin_path = find_ha_physics_gate_bin()
    cat = catalog or _CATALOG
    args = [
        str(bin_path),
        "albedo-dose",
        f"--catalog={cat}",
        f"--site-class={site_class}",
        f"--shield-g-cm2={float(shield_g_cm2)}",
        f"--anchor-gy={float(dose_anchor_gy)}",
    ]
    if see_base is not None:
        args.append(f"--see-base={float(see_base)}")

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
        raise RuntimeError(f"ha-physics-gate albedo-dose FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad albedo-dose receipt from Rust")
    return doc


def assert_mirror_matches_rust(
    *,
    site_class: str,
    shield_g_cm2: float,
    dose_anchor_gy: float,
    atol: float = 1e-9,
) -> dict[str, Any]:
    mirror = albedo_from_catalog(
        site_class=site_class, shield_g_cm2=shield_g_cm2, dose_anchor_gy=dose_anchor_gy
    )
    rust = evaluate_albedo_dose(
        site_class=site_class, shield_g_cm2=shield_g_cm2, dose_anchor_gy=dose_anchor_gy
    )
    keys = ("total_dose_gy", "albedo_fraction", "incident_dose_gy", "albedo_dose_gy")
    errs = {k: abs(float(mirror[k]) - float(rust[k])) for k in keys}
    ok = all(v <= atol for v in errs.values())
    return {"ok": ok, "errs": errs, "oracle": ORACLE, "site_class": site_class, "shield_g_cm2": shield_g_cm2}
