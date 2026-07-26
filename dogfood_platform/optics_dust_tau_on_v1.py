"""Beer-Lambert optics dust tau ON glue — Rust `optics-tau` oracle."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "optics_dust_tau_on_v1.json"
_BIN_STEM = "ha-physics-gate"
ORACLE = "ha_physics_gate_optics_tau"
SCHEMA = "ha_optics_dust_tau_eval_v1"


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


def load_optics_tau_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def optics_from_catalog(*, mass_g_m2: float, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_optics_tau_catalog()
    kappa = float(data["coeffs"]["kappa_m2_per_g"])
    tau = kappa * float(mass_g_m2)
    t = math.exp(-tau)
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "mass_g_m2": float(mass_g_m2),
        "kappa_m2_per_g": kappa,
        "tau": tau,
        "transmittance": t,
        "absorptance": 1.0 - t,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_optics_tau(*, mass_g_m2: float, catalog: Path | None = None) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "optics-tau", f"--catalog={catalog or _CATALOG}", f"--mass-g-m2={float(mass_g_m2)}"]
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad optics-tau receipt")
    return doc


def assert_mirror_matches_rust(*, mass_g_m2: float, atol: float = 1e-9) -> dict[str, Any]:
    mirror = optics_from_catalog(mass_g_m2=mass_g_m2)
    rust = evaluate_optics_tau(mass_g_m2=mass_g_m2)
    err = abs(float(mirror["tau"]) - float(rust["tau"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "mass_g_m2": mass_g_m2}
