"""ISRU sinter Arrhenius ON glue — Rust `isru-sinter` oracle."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "isru_sinter_on_v1.json"
ORACLE = "ha_physics_gate_isru_sinter"
SCHEMA = "ha_isru_sinter_eval_v1"


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


def load_sinter_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def sinter_from_catalog(
    *,
    recipe_id: str,
    t_k: float | None = None,
    t_s: float | None = None,
    p_w: float | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_sinter_catalog()
    recipe = data["recipes"][recipe_id]
    d = data["defaults"]
    r = float(data["constants"]["R_j_mol_k"])
    tk = float(d["t_k"] if t_k is None else t_k)
    ts = float(d["t_s"] if t_s is None else t_s)
    pw = float(d["p_w"] if p_w is None else p_w)
    a, ea = float(recipe["A_per_s"]), float(recipe["Ea_j_mol"])
    rate = a * math.exp(-ea / (r * tk))
    progress = 1.0 - math.exp(-rate * ts)
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "recipe_id": recipe_id,
        "t_k": tk,
        "t_s": ts,
        "p_w": pw,
        "rate_per_s": rate,
        "progress": progress,
        "energy_j": pw * ts,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_isru_sinter(
    *,
    recipe_id: str,
    t_k: float | None = None,
    t_s: float | None = None,
    p_w: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "isru-sinter", f"--catalog={catalog or _CATALOG}", f"--recipe={recipe_id}"]
    if t_k is not None:
        args.append(f"--t-k={float(t_k)}")
    if t_s is not None:
        args.append(f"--t-s={float(t_s)}")
    if p_w is not None:
        args.append(f"--p-w={float(p_w)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad isru-sinter receipt")
    return doc


def assert_mirror_matches_rust(*, recipe_id: str, t_k: float = 1100.0, atol: float = 1e-9) -> dict[str, Any]:
    mirror = sinter_from_catalog(recipe_id=recipe_id, t_k=t_k)
    rust = evaluate_isru_sinter(recipe_id=recipe_id, t_k=t_k)
    err = abs(float(mirror["progress"]) - float(rust["progress"])) + abs(float(mirror["rate_per_s"]) - float(rust["rate_per_s"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "recipe_id": recipe_id}
