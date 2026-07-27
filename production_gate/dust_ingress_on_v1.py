"""Dust ingress ON glue — Rust `ha-physics-gate dust-ingress` oracle.

rate = base*seal*gap*ES*(1-mit); acc=min(sat, prev+rate*n)
Hot path = catalog mirror; Dual = Rust.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "dust_ingress_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_dust_ingress"
SCHEMA = "ha_dust_ingress_eval_v1"


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


def load_dust_ingress_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def dust_from_catalog(
    *,
    zone: str,
    seal: str,
    n_sols: float = 1.0,
    mitigation_duty: float = 0.0,
    joint_gap_mm: float = 0.5,
    prev_g_m2: float = 0.0,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_dust_ingress_catalog()
    z = data["zones"][zone]
    s = data["seal_classes"][seal]
    mit = data["mitigation"]
    wear = data["wear_coupling"]
    thr = data["hazard_thresholds_g_m2_per_sol"]
    base = float(z["base_rate_g_m2_per_sol"])
    es = float(z["electrostatic_index"])
    seal_scale = float(s["ingress_scale"])
    max_red = float(mit["wiper_magnet_max_reduction"])
    mit_red = max(0.0, min(max_red, mitigation_duty * max_red))
    gap_scale = 1.0 + min(0.5, joint_gap_mm / 2.0)
    rate = base * seal_scale * gap_scale * es * (1.0 - mit_red)
    sat = float(wear["accumulation_saturation_g_m2"])
    acc = min(sat, prev_g_m2 + rate * n_sols)
    stress = min(float(wear["max_stress_mult"]), 1.0 + float(wear["abrasion_coeff_per_g_m2"]) * acc)
    haz = "LOW"
    if rate >= float(thr["MEDIUM"]):
        haz = "MEDIUM"
    if rate >= float(thr["HIGH"]):
        haz = "HIGH"
    if rate >= float(thr["SEVERE"]):
        haz = "SEVERE"
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "zone": zone,
        "seal_class": seal,
        "base_rate_g_m2_per_sol": base,
        "effective_rate_g_m2_per_sol": rate,
        "ingress_hazard_class": haz,
        "electrostatic_index": es,
        "n_sols": n_sols,
        "accumulation_g_m2": acc,
        "saturated": acc >= sat - 1e-12,
        "stress_index_multiplier": stress,
        "honesty": {
            "catalog_mirror_hot_path": True,
            "rust_oracle_for_dual": True,
            "not_measured": True,
        },
    }


def evaluate_dust_ingress(
    *,
    zone: str,
    seal: str,
    n_sols: float = 1.0,
    mitigation_duty: float = 0.0,
    joint_gap_mm: float = 0.5,
    prev_g_m2: float = 0.0,
    catalog: Path | None = None,
) -> dict[str, Any]:
    bin_path = find_ha_physics_gate_bin()
    cat = catalog or _CATALOG
    args = [
        str(bin_path),
        "dust-ingress",
        f"--catalog={cat}",
        f"--zone={zone}",
        f"--seal={seal}",
        f"--n-sols={float(n_sols)}",
        f"--mit={float(mitigation_duty)}",
        f"--gap-mm={float(joint_gap_mm)}",
        f"--prev={float(prev_g_m2)}",
    ]
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
        raise RuntimeError(f"ha-physics-gate dust-ingress FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad dust-ingress receipt")
    return doc


def assert_mirror_matches_rust(**kwargs: Any) -> dict[str, Any]:
    mirror = dust_from_catalog(**kwargs)
    rust = evaluate_dust_ingress(**kwargs)
    keys = ("effective_rate_g_m2_per_sol", "accumulation_g_m2", "stress_index_multiplier")
    errs = {k: abs(float(mirror[k]) - float(rust[k])) for k in keys}
    return {"ok": all(v <= 1e-9 for v in errs.values()), "errs": errs, "oracle": ORACLE}
