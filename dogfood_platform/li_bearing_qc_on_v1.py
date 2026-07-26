"""Li q_c(h) ON glue — Rust `ha-physics-gate li-qc` oracle.

q_c = A*exp(-h/B)+C (teaching Li lunar-g fit). Adjunct to Bekker.
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
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "li_bearing_qc_on_v1.json"
_BIN_STEM = "ha-physics-gate"

ORACLE = "ha_physics_gate_li_qc"
SCHEMA = "ha_li_bearing_qc_eval_v1"


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


def load_li_qc_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or _CATALOG
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def qc_from_catalog(*, depth_mm: float, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_li_qc_catalog()
    c = data["coeffs"]
    a, b, cc = float(c["A"]), float(c["B_m"]), float(c["C"])
    h_m = depth_mm / 1000.0
    q = a * math.exp(-h_m / b) + cc
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "depth_mm": depth_mm,
        "depth_m": h_m,
        "q_c_kpa": q,
        "honesty": {
            "catalog_mirror_hot_path": True,
            "rust_oracle_for_dual": True,
            "adjunct_not_bekker_oracle": True,
            "not_measured": True,
        },
    }


def evaluate_li_qc(*, depth_mm: float, catalog: Path | None = None) -> dict[str, Any]:
    bin_path = find_ha_physics_gate_bin()
    cat = catalog or _CATALOG
    args = [str(bin_path), "li-qc", f"--catalog={cat}", f"--depth-mm={float(depth_mm)}"]
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
        raise RuntimeError(f"ha-physics-gate li-qc FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad li-qc receipt")
    return doc


def assert_mirror_matches_rust(*, depth_mm: float, atol: float = 1e-9) -> dict[str, Any]:
    mirror = qc_from_catalog(depth_mm=depth_mm)
    rust = evaluate_li_qc(depth_mm=depth_mm)
    err = abs(float(mirror["q_c_kpa"]) - float(rust["q_c_kpa"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "depth_mm": depth_mm}
