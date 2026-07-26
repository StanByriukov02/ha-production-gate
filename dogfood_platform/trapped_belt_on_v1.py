"""Trapped belt ON glue — Rust `trapped-belt`."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
from typing import Any
_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "trapped_belt_on_v1.json"
ORACLE = "ha_physics_gate_trapped_belt"
SCHEMA = "ha_trapped_belt_eval_v1"

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

def load_belt_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))

def belt_from_catalog(*, pack_id: str, t_h: float | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_belt_catalog()
    pack = data["packs"][pack_id]
    t = float(data["defaults"]["t_h"] if t_h is None else t_h)
    base, scale = float(pack["base_rate_gy_h"]), float(pack["belt_scale"])
    rate = base * scale
    return {"schema": SCHEMA, "oracle": ORACLE, "pack_id": pack_id, "base_rate_gy_h": base, "belt_scale": scale, "t_h": t,
            "dose_rate_gy_h": rate, "window_dose_gy": rate * t, "honesty": {"catalog_mirror_hot_path": True, "not_measured": True}}

def evaluate_trapped_belt(*, pack_id: str, t_h: float | None = None, catalog: Path | None = None) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs
    args = [str(find_ha_physics_gate_bin()), "trapped-belt", f"--catalog={catalog or _CATALOG}", f"--pack={pack_id}"]
    if t_h is not None:
        args.append(f"--t-h={float(t_h)}")
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad trapped-belt receipt")
    return doc

def assert_mirror_matches_rust(*, pack_id: str, t_h: float = 6.0, atol: float = 1e-12) -> dict[str, Any]:
    mirror = belt_from_catalog(pack_id=pack_id, t_h=t_h)
    rust = evaluate_trapped_belt(pack_id=pack_id, t_h=t_h)
    err = abs(float(mirror["window_dose_gy"]) - float(rust["window_dose_gy"]))
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "pack_id": pack_id}
