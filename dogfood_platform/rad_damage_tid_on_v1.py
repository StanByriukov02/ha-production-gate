"""TID damage ON glue — Rust `rad-damage-tid`."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
from typing import Any
_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "rad_damage_tid_on_v1.json"
ORACLE = "ha_physics_gate_rad_damage_tid"
SCHEMA = "ha_rad_damage_tid_eval_v1"

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

def load_tid_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))

def tid_from_catalog(*, pack_id: str, t_h: float | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_tid_catalog()
    pack = data["packs"][pack_id]
    t = float(data["defaults"]["t_h"] if t_h is None else t_h)
    rate, d_fail = float(pack["dose_rate_gy_h"]), float(pack["d_fail_gy"])
    d = rate * t
    return {"schema": SCHEMA, "oracle": ORACLE, "pack_id": pack_id, "dose_rate_gy_h": rate, "t_h": t, "d_fail_gy": d_fail,
            "d_tid_gy": d, "damage_proxy": d / d_fail, "honesty": {"catalog_mirror_hot_path": True, "not_measured": True}}

def evaluate_rad_damage_tid(*, pack_id: str, t_h: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs
    args = [str(find_ha_physics_gate_bin()), "rad-damage-tid", f"--catalog={catalog or _CATALOG}", f"--pack={pack_id}"]
    if t_h is not None:
        args.append(f"--t-h={float(t_h)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad rad-damage-tid receipt")
    return doc

def assert_mirror_matches_rust(*, pack_id: str, t_h: float = 48.0, atol: float = 1e-12) -> dict[str, Any]:
    mirror = tid_from_catalog(pack_id=pack_id, t_h=t_h)
    rust = evaluate_rad_damage_tid(pack_id=pack_id, t_h=t_h)
    err = abs(float(mirror["d_tid_gy"]) - float(rust["d_tid_gy"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "pack_id": pack_id}
