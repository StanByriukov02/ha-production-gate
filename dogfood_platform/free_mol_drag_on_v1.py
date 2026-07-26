"""Free-mol drag ON glue — Rust `free-mol-drag`."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
from typing import Any
_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "free_mol_drag_on_v1.json"
ORACLE = "ha_physics_gate_free_mol_drag"
SCHEMA = "ha_free_mol_drag_eval_v1"

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

def load_fmd_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))

def fmd_from_catalog(*, pack_id: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    data = catalog or load_fmd_catalog()
    pack = data["packs"][pack_id]
    rho, v, cd, area = float(pack["rho_kg_m3"]), float(pack["v_m_s"]), float(pack["cd"]), float(pack["area_m2"])
    return {"schema": SCHEMA, "oracle": ORACLE, "pack_id": pack_id, "rho_kg_m3": rho, "v_m_s": v, "cd": cd, "area_m2": area,
            "f_fmd_n": rho * v * v * cd * area, "honesty": {"catalog_mirror_hot_path": True, "not_measured": True}}

def evaluate_free_mol_drag(*, pack_id: str, catalog: Path | None = None) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs
    args = [str(find_ha_physics_gate_bin()), "free-mol-drag", f"--catalog={catalog or _CATALOG}", f"--pack={pack_id}"]
    proc = subprocess.run(args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad free-mol-drag receipt")
    return doc

def assert_mirror_matches_rust(*, pack_id: str, atol: float = 1e-18) -> dict[str, Any]:
    mirror = fmd_from_catalog(pack_id=pack_id)
    rust = evaluate_free_mol_drag(pack_id=pack_id)
    err = abs(float(mirror["f_fmd_n"]) - float(rust["f_fmd_n"]))
    return {"ok": err <= max(atol, 1e-6 * abs(float(mirror["f_fmd_n"]))), "err": err, "oracle": ORACLE, "pack_id": pack_id}
