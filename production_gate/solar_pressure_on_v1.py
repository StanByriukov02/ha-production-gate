"""Solar radiation pressure ON glue — Rust `solar-pressure` oracle."""
from __future__ import annotations

import json, math, os, subprocess, sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "solar_pressure_on_v1.json"
ORACLE = "ha_physics_gate_solar_pressure"
SCHEMA = "ha_solar_pressure_eval_v1"


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


def load_srp_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def srp_from_catalog(*, pack_id: str, i_rad: float | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_srp_catalog()
    pack = data["packs"][pack_id]
    c = float(data["constants"]["c_m_s"])
    s, area, cr = float(pack["s_w_m2"]), float(pack["area_m2"]), float(pack["cr"])
    i = float(pack["i_rad"] if i_rad is None else i_rad)
    p = s / c
    cos_i = max(math.cos(i), 0.0)
    f = p * area * cr * cos_i * cos_i
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "pack_id": pack_id,
        "s_w_m2": s,
        "c_m_s": c,
        "area_m2": area,
        "cr": cr,
        "i_rad": i,
        "p_pa": p,
        "f_srp_n": f,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_solar_pressure(*, pack_id: str, i_rad: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "solar-pressure", f"--catalog={catalog or _CATALOG}", f"--pack={pack_id}"]
    if i_rad is not None:
        args.append(f"--i-rad={float(i_rad)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad solar-pressure receipt")
    return doc


def assert_mirror_matches_rust(*, pack_id: str, i_rad: float | None = None, atol: float = 1e-12) -> dict[str, Any]:
    mirror = srp_from_catalog(pack_id=pack_id, i_rad=i_rad)
    rust = evaluate_solar_pressure(pack_id=pack_id, i_rad=i_rad)
    err = abs(float(mirror["f_srp_n"]) - float(rust["f_srp_n"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "pack_id": pack_id}
