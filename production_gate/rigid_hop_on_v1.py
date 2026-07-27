"""Rigid ballistic hop ON glue — Rust `rigid-hop` oracle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "rigid_hop_on_v1.json"
_BIN_STEM = "ha-physics-gate"
ORACLE = "ha_physics_gate_rigid_hop"
SCHEMA = "ha_rigid_hop_eval_v1"


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


def load_rigid_hop_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def hop_from_catalog(
    *,
    v_up: float | None = None,
    v_h: float | None = None,
    body: str | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_rigid_hop_catalog()
    body_s = body or str(data["defaults"]["body"])
    g = float(data["g_m_s2"][body_s])
    vu = float(data["defaults"]["v_up_m_s"] if v_up is None else v_up)
    vh = float(data["defaults"]["v_h_m_s"] if v_h is None else v_h)
    apex = (vu * vu) / (2.0 * g)
    tof = 0.0 if vu == 0.0 else 2.0 * vu / g
    rng = vh * tof
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "body": body_s,
        "g_m_s2": g,
        "v_up_m_s": vu,
        "v_h_m_s": vh,
        "apex_m": apex,
        "tof_s": tof,
        "range_m": rng,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_rigid_hop(
    *,
    v_up: float | None = None,
    v_h: float | None = None,
    body: str | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "rigid-hop", f"--catalog={catalog or _CATALOG}"]
    if v_up is not None:
        args.append(f"--v-up={float(v_up)}")
    if v_h is not None:
        args.append(f"--v-h={float(v_h)}")
    if body is not None:
        args.append(f"--body={body}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad rigid-hop receipt")
    return doc


def assert_mirror_matches_rust(*, body: str = "moon", v_up: float = 2.0, v_h: float = 1.0, atol: float = 1e-9) -> dict[str, Any]:
    mirror = hop_from_catalog(body=body, v_up=v_up, v_h=v_h)
    rust = evaluate_rigid_hop(body=body, v_up=v_up, v_h=v_h)
    err = abs(float(mirror["apex_m"]) - float(rust["apex_m"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "body": body}
