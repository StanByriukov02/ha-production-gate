"""Battery Peukert + OCV–SOC ON glue — Rust `battery-peukert` oracle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "battery_peukert_on_v1.json"
ORACLE = "ha_physics_gate_battery_peukert"
SCHEMA = "ha_battery_peukert_eval_v1"


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


def load_battery_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def battery_from_catalog(
    *, pack_id: str, i_a: float | None = None, soc: float | None = None, catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    data = catalog or load_battery_catalog()
    pack = data["packs"][pack_id]
    d = data["defaults"]
    i = float(d["i_a"] if i_a is None else i_a)
    s = float(d["soc"] if soc is None else soc)
    c_p, k = float(pack["c_p_ah_k"]), float(pack["k"])
    t_h = c_p / (i**k)
    ocv = float(pack["voc_full_v"]) - (float(pack["voc_full_v"]) - float(pack["voc_empty_v"])) * (1.0 - s)
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "pack_id": pack_id,
        "i_a": i,
        "soc": s,
        "k": k,
        "c_p": c_p,
        "t_discharge_h": t_h,
        "effective_ah": i * t_h,
        "ocv_v": ocv,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_battery_peukert(*, pack_id: str, i_a: float | None = None, soc: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [str(find_ha_physics_gate_bin()), "battery-peukert", f"--catalog={catalog or _CATALOG}", f"--pack={pack_id}"]
    if i_a is not None:
        args.append(f"--i-a={float(i_a)}")
    if soc is not None:
        args.append(f"--soc={float(soc)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad battery-peukert receipt")
    return doc


def assert_mirror_matches_rust(*, pack_id: str, i_a: float = 8.0, soc: float = 0.5, atol: float = 1e-9) -> dict[str, Any]:
    mirror = battery_from_catalog(pack_id=pack_id, i_a=i_a, soc=soc)
    rust = evaluate_battery_peukert(pack_id=pack_id, i_a=i_a, soc=soc)
    err = abs(float(mirror["t_discharge_h"]) - float(rust["t_discharge_h"])) + abs(float(mirror["ocv_v"]) - float(rust["ocv_v"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "pack_id": pack_id}
