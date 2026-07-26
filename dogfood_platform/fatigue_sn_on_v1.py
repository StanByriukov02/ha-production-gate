"""Fatigue Basquin S–N ON glue — Rust `fatigue-sn` oracle."""
from __future__ import annotations

import json, os, subprocess, sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "fatigue_sn_on_v1.json"
ORACLE = "ha_physics_gate_fatigue_sn"
SCHEMA = "ha_fatigue_sn_eval_v1"


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


def load_fatigue_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def fatigue_from_catalog(*, mat_id: str, sigma_a_mpa: float | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_fatigue_catalog()
    mat = data["mats"][mat_id]
    d = data["defaults"]
    sigma_a = float(d["sigma_a_mpa"] if sigma_a_mpa is None else sigma_a_mpa)
    sigma_f = float(mat["sigma_f_prime_mpa"])
    b = float(mat["b"])
    n_f = 0.5 * (sigma_a / sigma_f) ** (1.0 / b)
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "mat_id": mat_id,
        "sigma_a_mpa": sigma_a,
        "sigma_f_prime_mpa": sigma_f,
        "b": b,
        "n_f_cycles": n_f,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_fatigue_sn(*, mat_id: str, sigma_a_mpa: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "fatigue-sn", f"--catalog={catalog or _CATALOG}", f"--mat={mat_id}"]
    if sigma_a_mpa is not None:
        args.append(f"--sigma-a-mpa={float(sigma_a_mpa)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad fatigue-sn receipt")
    return doc


def assert_mirror_matches_rust(*, mat_id: str, sigma_a_mpa: float = 150.0, atol: float = 1e-4) -> dict[str, Any]:
    mirror = fatigue_from_catalog(mat_id=mat_id, sigma_a_mpa=sigma_a_mpa)
    rust = evaluate_fatigue_sn(mat_id=mat_id, sigma_a_mpa=sigma_a_mpa)
    err = abs(float(mirror["n_f_cycles"]) - float(rust["n_f_cycles"])) / max(float(mirror["n_f_cycles"]), 1.0)
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "mat_id": mat_id}
