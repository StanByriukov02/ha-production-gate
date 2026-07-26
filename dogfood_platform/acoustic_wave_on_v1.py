"""Acoustic wave ON glue — Rust `acoustic-wave` oracle."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "acoustic_wave_on_v1.json"
ORACLE = "ha_physics_gate_acoustic_wave"
SCHEMA = "ha_acoustic_wave_eval_v1"


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


def load_acoustic_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def acoustic_from_catalog(*, medium_id: str, path_m: float | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_acoustic_catalog()
    m = data["media"][medium_id]
    path = float(data["defaults"]["path_m"] if path_m is None else path_m)
    k, g, rho = float(m["K_pa"]), float(m["G_pa"]), float(m["rho_kg_m3"])
    alpha = float(m["alpha_per_m"])
    vp = math.sqrt((k + 4.0 / 3.0 * g) / rho)
    vs = math.sqrt(g / rho)
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "medium_id": medium_id,
        "vp_m_s": vp,
        "vs_m_s": vs,
        "alpha_per_m": alpha,
        "path_m": path,
        "transmittance": math.exp(-alpha * path),
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_acoustic_wave(*, medium_id: str, path_m: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "acoustic-wave", f"--catalog={catalog or _CATALOG}", f"--medium={medium_id}"]
    if path_m is not None:
        args.append(f"--path-m={float(path_m)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad acoustic-wave receipt")
    return doc


def assert_mirror_matches_rust(*, medium_id: str, path_m: float = 10.0, atol: float = 1e-6) -> dict[str, Any]:
    mirror = acoustic_from_catalog(medium_id=medium_id, path_m=path_m)
    rust = evaluate_acoustic_wave(medium_id=medium_id, path_m=path_m)
    err = abs(float(mirror["vp_m_s"]) - float(rust["vp_m_s"])) + abs(float(mirror["transmittance"]) - float(rust["transmittance"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "medium_id": medium_id}
