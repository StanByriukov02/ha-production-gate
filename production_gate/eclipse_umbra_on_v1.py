"""Eclipse umbra ON glue — Rust `eclipse-umbra` oracle."""
from __future__ import annotations

import json, math, os, subprocess, sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "eclipse_umbra_on_v1.json"
ORACLE = "ha_physics_gate_eclipse_umbra"
SCHEMA = "ha_eclipse_umbra_eval_v1"


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


def load_eclipse_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def eclipse_from_catalog(*, orbit_id: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_eclipse_catalog()
    orb = data["orbits"][orbit_id]
    r, R, period = float(orb["r_km"]), float(orb["R_earth_km"]), float(orb["period_s"])
    f = math.acos(math.sqrt(r * r - R * R) / r) / math.pi
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "orbit_id": orbit_id,
        "r_km": r,
        "R_earth_km": R,
        "period_s": period,
        "f_eclipse": f,
        "t_eclipse_s": f * period,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_eclipse_umbra(*, orbit_id: str, catalog: Path | None = None) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "eclipse-umbra", f"--catalog={catalog or _CATALOG}", f"--orbit={orbit_id}"]
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad eclipse-umbra receipt")
    return doc


def assert_mirror_matches_rust(*, orbit_id: str, atol: float = 1e-9) -> dict[str, Any]:
    mirror = eclipse_from_catalog(orbit_id=orbit_id)
    rust = evaluate_eclipse_umbra(orbit_id=orbit_id)
    err = abs(float(mirror["f_eclipse"]) - float(rust["f_eclipse"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "orbit_id": orbit_id}
