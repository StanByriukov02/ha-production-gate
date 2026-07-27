"""Fourier flux ON glue — Rust `fourier-flux`."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
from typing import Any
_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "fourier_flux_on_v1.json"
ORACLE = "ha_physics_gate_fourier_flux"
SCHEMA = "ha_fourier_flux_eval_v1"

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

def load_fourier_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))

def fourier_from_catalog(*, pack_id: str, dt_k: float | None = None, dx_m: float | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_fourier_catalog()
    pack = data["packs"][pack_id]
    d = data["defaults"]
    dt = float(d["dt_k"] if dt_k is None else dt_k)
    dx = float(d["dx_m"] if dx_m is None else dx_m)
    k = float(pack["k_w_mk"])
    return {"schema": SCHEMA, "oracle": ORACLE, "pack_id": pack_id, "k_w_mk": k, "dt_k": dt, "dx_m": dx,
            "q_flux_w_m2": k * dt / dx, "honesty": {"catalog_mirror_hot_path": True, "not_measured": True}}

def evaluate_fourier_flux(*, pack_id: str, dt_k: float | None = None, dx_m: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs
    args = [str(find_ha_physics_gate_bin()), "fourier-flux", f"--catalog={catalog or _CATALOG}", f"--pack={pack_id}"]
    if dt_k is not None:
        args.append(f"--dt-k={float(dt_k)}")
    if dx_m is not None:
        args.append(f"--dx-m={float(dx_m)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad fourier-flux receipt")
    return doc

def assert_mirror_matches_rust(*, pack_id: str, dt_k: float = 40.0, dx_m: float = 0.005, atol: float = 1e-9) -> dict[str, Any]:
    mirror = fourier_from_catalog(pack_id=pack_id, dt_k=dt_k, dx_m=dx_m)
    rust = evaluate_fourier_flux(pack_id=pack_id, dt_k=dt_k, dx_m=dx_m)
    err = abs(float(mirror["q_flux_w_m2"]) - float(rust["q_flux_w_m2"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "pack_id": pack_id}
