"""Joint Coulomb friction ON glue — Rust `joint-friction` oracle."""
from __future__ import annotations

import json, os, subprocess, sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "joint_friction_on_v1.json"
ORACLE = "ha_physics_gate_joint_friction"
SCHEMA = "ha_joint_friction_eval_v1"


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


def load_joint_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def joint_from_catalog(*, pack_id: str, n_n: float | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_joint_catalog()
    pack = data["packs"][pack_id]
    d = data["defaults"]
    n = float(d["n_n"] if n_n is None else n_n)
    mu, r = float(pack["mu"]), float(pack["r_eff_m"])
    f = mu * n
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "pack_id": pack_id,
        "mu": mu,
        "n_n": n,
        "r_eff_m": r,
        "f_friction_n": f,
        "tau_friction_nm": f * r,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_joint_friction(*, pack_id: str, n_n: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "joint-friction", f"--catalog={catalog or _CATALOG}", f"--pack={pack_id}"]
    if n_n is not None:
        args.append(f"--n-n={float(n_n)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad joint-friction receipt")
    return doc


def assert_mirror_matches_rust(*, pack_id: str, n_n: float = 500.0, atol: float = 1e-9) -> dict[str, Any]:
    mirror = joint_from_catalog(pack_id=pack_id, n_n=n_n)
    rust = evaluate_joint_friction(pack_id=pack_id, n_n=n_n)
    err = abs(float(mirror["f_friction_n"]) - float(rust["f_friction_n"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "pack_id": pack_id}
