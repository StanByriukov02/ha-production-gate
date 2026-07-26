"""Orbital vis-viva ON glue — Rust `orbital-visviva` oracle."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "orbital_visviva_on_v1.json"
ORACLE = "ha_physics_gate_orbital_visviva"
SCHEMA = "ha_orbital_visviva_eval_v1"


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


def load_orbital_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def orbital_from_catalog(
    *, body: str, r_km: float | None = None, a_km: float | None = None, catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    data = catalog or load_orbital_catalog()
    brow = data["bodies"][body]
    d = data["defaults"]
    r = float(d["r_km"] if r_km is None else r_km) * 1000.0
    a = float(d["a_km"] if a_km is None else a_km) * 1000.0
    mu = float(brow["mu_m3_s2"])
    v = math.sqrt(mu * (2.0 / r - 1.0 / a))
    t = 2.0 * math.pi * math.sqrt(a**3 / mu)
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "body": body,
        "mu_m3_s2": mu,
        "r_m": r,
        "a_m": a,
        "r_km": r / 1000.0,
        "a_km": a / 1000.0,
        "v_m_s": v,
        "period_s": t,
        "period_h": t / 3600.0,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_orbital_visviva(
    *, body: str, r_km: float | None = None, a_km: float | None = None, catalog: Path | None = None
) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "orbital-visviva", f"--catalog={catalog or _CATALOG}", f"--body={body}"]
    if r_km is not None:
        args.append(f"--r-km={float(r_km)}")
    if a_km is not None:
        args.append(f"--a-km={float(a_km)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad orbital-visviva receipt")
    return doc


def assert_mirror_matches_rust(*, body: str = "earth", r_km: float = 6778.0, atol: float = 1e-3) -> dict[str, Any]:
    mirror = orbital_from_catalog(body=body, r_km=r_km, a_km=r_km)
    rust = evaluate_orbital_visviva(body=body, r_km=r_km, a_km=r_km)
    err = abs(float(mirror["v_m_s"]) - float(rust["v_m_s"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "body": body, "r_km": r_km}
