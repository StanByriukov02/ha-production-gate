"""Atm quadratic drag ON glue — Rust `atm-drag` oracle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "atm_drag_on_v1.json"
_BIN_STEM = "ha-physics-gate"
ORACLE = "ha_physics_gate_atm_drag"
SCHEMA = "ha_atm_drag_eval_v1"


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


def load_atm_drag_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def drag_from_catalog(
    *,
    body: str,
    v_m_s: float | None = None,
    cd: float | None = None,
    area_m2: float | None = None,
    mass_kg: float | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_atm_drag_catalog()
    brow = data["bodies"][body]
    d = data["defaults"]
    rho = float(brow["rho_kg_m3"])
    v = float(d["v_m_s"] if v_m_s is None else v_m_s)
    c = float(d["cd"] if cd is None else cd)
    a = float(d["area_m2"] if area_m2 is None else area_m2)
    m = float(d["mass_kg"] if mass_kg is None else mass_kg)
    f = 0.5 * rho * v * v * c * a
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "body": body,
        "rho_kg_m3": rho,
        "v_m_s": v,
        "cd": c,
        "area_m2": a,
        "mass_kg": m,
        "f_drag_n": f,
        "a_drag_m_s2": f / m,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_atm_drag(
    *,
    body: str,
    v_m_s: float | None = None,
    cd: float | None = None,
    area_m2: float | None = None,
    mass_kg: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "atm-drag", f"--catalog={catalog or _CATALOG}", f"--body={body}"]
    if v_m_s is not None:
        args.append(f"--v={float(v_m_s)}")
    if cd is not None:
        args.append(f"--cd={float(cd)}")
    if area_m2 is not None:
        args.append(f"--area={float(area_m2)}")
    if mass_kg is not None:
        args.append(f"--mass={float(mass_kg)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad atm-drag receipt")
    return doc


def assert_mirror_matches_rust(*, body: str, v_m_s: float = 20.0, atol: float = 1e-9) -> dict[str, Any]:
    mirror = drag_from_catalog(body=body, v_m_s=v_m_s)
    rust = evaluate_atm_drag(body=body, v_m_s=v_m_s)
    err = abs(float(mirror["f_drag_n"]) - float(rust["f_drag_n"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "body": body}
