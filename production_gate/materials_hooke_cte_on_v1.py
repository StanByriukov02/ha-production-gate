"""Materials Hooke+CTE ON glue — Rust `materials-hooke` oracle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "materials_hooke_cte_on_v1.json"
ORACLE = "ha_physics_gate_materials_hooke"
SCHEMA = "ha_materials_hooke_cte_eval_v1"


def find_ha_physics_gate_bin() -> Path:
    env = (os.environ.get("HA_PHYSICS_GATE_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(p)
        return p.resolve()
    name = "ha-physics-gate" + (".exe" if sys.platform == "win32" else "")
    for candidate in (_REPO / "target" / "release" / name, _REPO / "target" / "debug" / name):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("ha-physics-gate missing")


def load_materials_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def materials_from_catalog(
    *,
    mat_id: str,
    eps: float | None = None,
    dt_k: float | None = None,
    l_m: float | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_materials_catalog()
    mat = data["materials"][mat_id]
    d = data["defaults"]
    e = float(d["eps"] if eps is None else eps)
    dt = float(d["dt_k"] if dt_k is None else dt_k)
    l = float(d["l_m"] if l_m is None else l_m)
    ee, alpha = float(mat["E_pa"]), float(mat["alpha_per_k"])
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "mat_id": mat_id,
        "E_pa": ee,
        "alpha_per_k": alpha,
        "eps": e,
        "dt_k": dt,
        "l_m": l,
        "sigma_pa": ee * e,
        "delta_mech_m": e * l,
        "delta_thermal_m": alpha * l * dt,
        "sigma_thermal_constrained_pa": ee * alpha * dt,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_materials_hooke(
    *,
    mat_id: str,
    eps: float | None = None,
    dt_k: float | None = None,
    l_m: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "materials-hooke", f"--catalog={catalog or _CATALOG}", f"--mat={mat_id}"]
    if eps is not None:
        args.append(f"--eps={float(eps)}")
    if dt_k is not None:
        args.append(f"--dt-k={float(dt_k)}")
    if l_m is not None:
        args.append(f"--l-m={float(l_m)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad materials-hooke receipt")
    return doc


def assert_mirror_matches_rust(*, mat_id: str, dt_k: float = 100.0, atol: float = 1e-6) -> dict[str, Any]:
    mirror = materials_from_catalog(mat_id=mat_id, dt_k=dt_k)
    rust = evaluate_materials_hooke(mat_id=mat_id, dt_k=dt_k)
    err = abs(float(mirror["delta_thermal_m"]) - float(rust["delta_thermal_m"])) + abs(
        float(mirror["sigma_pa"]) - float(rust["sigma_pa"])
    )
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "mat_id": mat_id}
