"""Janosi–Hanamoto τ(j) curve ON glue — Rust `janosi-curve` oracle."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "terramech" / "janosi_shear_curve_on_v1.json"
_BIN_STEM = "ha-physics-gate"
ORACLE = "ha_physics_gate_janosi_curve"
SCHEMA = "ha_janosi_shear_curve_eval_v1"


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


def load_janosi_curve_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def _tau(c: float, phi_deg: float, k: float, p: float, j: float) -> float:
    tau_max = c + p * math.tan(math.radians(phi_deg))
    return tau_max * (1.0 - math.exp(-j / k))


def curve_from_catalog(
    *,
    soil_id: str,
    p_kpa: float | None = None,
    j_max_m: float | None = None,
    n_points: int | None = None,
    area_m2: float | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_janosi_curve_catalog()
    soil = data["soils"][soil_id]
    d = data["defaults"]
    p = float(d["p_kpa"] if p_kpa is None else p_kpa)
    jmax = float(d["j_max_m"] if j_max_m is None else j_max_m)
    np = int(d["n_points"] if n_points is None else n_points)
    area = float(d["contact_area_m2"] if area_m2 is None else area_m2)
    c = float(soil["c_kpa"])
    phi = float(soil["phi_deg"])
    k = float(soil["K_m"])
    tau_inf = _tau(c, phi, k, p, k * 50.0)
    curve = []
    for i in range(np):
        j = jmax * (i / (np - 1))
        tau = _tau(c, phi, k, p, j)
        curve.append({"j_m": j, "tau_kpa": tau, "drawbar_n": tau * area * 1000.0})
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "soil_id": soil_id,
        "c_kpa": c,
        "phi_deg": phi,
        "K_m": k,
        "p_kpa": p,
        "contact_area_m2": area,
        "j_max_m": jmax,
        "n_points": np,
        "tau_inf_kpa": tau_inf,
        "tau_at_0_kpa": curve[0]["tau_kpa"],
        "tau_at_jmax_kpa": curve[-1]["tau_kpa"],
        "curve": curve,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_janosi_curve(
    *,
    soil_id: str,
    p_kpa: float | None = None,
    j_max_m: float | None = None,
    n_points: int | None = None,
    area_m2: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "janosi-curve", f"--catalog={catalog or _CATALOG}", f"--soil-id={soil_id}"]
    if p_kpa is not None:
        args.append(f"--p-kpa={float(p_kpa)}")
    if j_max_m is not None:
        args.append(f"--j-max={float(j_max_m)}")
    if n_points is not None:
        args.append(f"--n-points={int(n_points)}")
    if area_m2 is not None:
        args.append(f"--area={float(area_m2)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad janosi-curve receipt")
    return doc


def assert_mirror_matches_rust(*, soil_id: str, atol: float = 1e-6) -> dict[str, Any]:
    mirror = curve_from_catalog(soil_id=soil_id)
    rust = evaluate_janosi_curve(soil_id=soil_id)
    err = abs(float(mirror["tau_at_jmax_kpa"]) - float(rust["tau_at_jmax_kpa"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "soil_id": soil_id}
