"""Surface charging ON glue — Rust `ha-physics-gate surface-charging` oracle.

Piecewise Zheng/Stubbs anchors: illum/SEP/magnetotail → class + φ_s.
Not CCMC live. Not MEASURED.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "surface_charging_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_surface_charging"
SCHEMA = "ha_surface_charging_eval_v1"


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


def load_surface_charging_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def charging_from_catalog(
    *,
    illum_frac: float,
    sep_active: bool = False,
    in_magnetotail: bool = False,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_surface_charging_catalog()
    thr = data["thresholds"]
    phi = data["phi_v"]
    d_min = float(thr["dayside_illum_min"])
    t_min = float(thr["terminator_illum_min"])
    if illum_frac >= d_min:
        cls, v = "DAYSIDE_LOW_POS", float(phi["dayside_v"])
    elif illum_frac >= t_min:
        cls, v = "TERMINATOR_SHADOW", float(phi["shadow_v"])
    elif sep_active or in_magnetotail:
        cls, v = "NIGHTSIDE_EXTREME_NEG", float(phi["nightside_extreme_v"])
    else:
        cls, v = "NIGHTSIDE_HIGH_NEG", float(phi["nightside_floor_v"])
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "illum_frac": float(illum_frac),
        "sep_active": bool(sep_active),
        "in_magnetotail": bool(in_magnetotail),
        "charging_class": cls,
        "surface_potential_v": v,
        "honesty": {
            "catalog_mirror_hot_path": True,
            "rust_oracle_for_dual": True,
            "not_ccmc_live_solver": True,
            "not_measured": True,
        },
    }


def evaluate_surface_charging(
    *,
    illum_frac: float,
    sep_active: bool = False,
    in_magnetotail: bool = False,
    catalog: Path | None = None,
) -> dict[str, Any]:
    bin_path = find_ha_physics_gate_bin()
    cat = catalog or _CATALOG
    args = [
        str(bin_path),
        "surface-charging",
        f"--catalog={cat}",
        f"--illum={float(illum_frac)}",
    ]
    if sep_active:
        args.append("--sep")
    if in_magnetotail:
        args.append("--magnetotail")
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
        raise RuntimeError(f"ha-physics-gate surface-charging FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad surface-charging receipt")
    return doc


def assert_mirror_matches_rust(
    *,
    illum_frac: float,
    sep_active: bool = False,
    in_magnetotail: bool = False,
    atol: float = 1e-9,
) -> dict[str, Any]:
    mirror = charging_from_catalog(
        illum_frac=illum_frac, sep_active=sep_active, in_magnetotail=in_magnetotail
    )
    rust = evaluate_surface_charging(
        illum_frac=illum_frac, sep_active=sep_active, in_magnetotail=in_magnetotail
    )
    err = abs(float(mirror["surface_potential_v"]) - float(rust["surface_potential_v"]))
    cls_ok = mirror["charging_class"] == rust["charging_class"]
    return {
        "ok": err <= atol and cls_ok,
        "err": err,
        "cls_ok": cls_ok,
        "oracle": ORACLE,
        "illum_frac": illum_frac,
    }
