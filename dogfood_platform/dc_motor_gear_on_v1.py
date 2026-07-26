"""DC motor linear τ–ω + gear η ON glue — Rust `dc-motor-gear` oracle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "fixtures" / "open_registry" / "env" / "dc_motor_gear_on_v1.json"
ORACLE = "ha_physics_gate_dc_motor_gear"
SCHEMA = "ha_dc_motor_gear_eval_v1"


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


def load_dc_motor_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def motor_from_catalog(
    *, pack_id: str, omega_rad_s: float | None = None, catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    data = catalog or load_dc_motor_catalog()
    pack = data["packs"][pack_id]
    d = data["defaults"]
    omega = float(d["omega_rad_s"] if omega_rad_s is None else omega_rad_s)
    tau_stall = float(pack["tau_stall_nm"])
    omega_nl = float(pack["omega_nl_rad_s"])
    n = float(pack["gear_ratio"])
    eta = float(pack["eta"])
    if omega > omega_nl:
        raise ValueError("omega exceeds omega_nl")
    tau_m = tau_stall * (1.0 - omega / omega_nl)
    tau_out = tau_m * n * eta
    omega_out = omega / n
    return {
        "schema": SCHEMA,
        "oracle": ORACLE,
        "pack_id": pack_id,
        "omega_rad_s": omega,
        "tau_stall_nm": tau_stall,
        "omega_nl_rad_s": omega_nl,
        "gear_ratio": n,
        "eta": eta,
        "tau_motor_nm": tau_m,
        "tau_out_nm": tau_out,
        "omega_out_rad_s": omega_out,
        "p_motor_w": tau_m * omega,
        "p_out_w": tau_out * omega_out,
        "honesty": {"catalog_mirror_hot_path": True, "rust_oracle_for_dual": True, "not_measured": True},
    }


def evaluate_dc_motor_gear(
    *, pack_id: str, omega_rad_s: float | None = None, catalog: Path | None = None
) -> dict[str, Any]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    args = [
        str(find_ha_physics_gate_bin()),
        "dc-motor-gear",
        f"--catalog={catalog or _CATALOG}",
        f"--pack={pack_id}",
    ]
    if omega_rad_s is not None:
        args.append(f"--omega-rad-s={float(omega_rad_s)}")
    proc = subprocess.run(
        args, cwd=str(_REPO), capture_output=True, text=True, timeout=60.0, check=False, **hidden_run_kwargs()
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != SCHEMA or doc.get("oracle") != ORACLE:
        raise RuntimeError("bad dc-motor-gear receipt")
    return doc


def assert_mirror_matches_rust(*, pack_id: str, omega_rad_s: float = 150.0, atol: float = 1e-9) -> dict[str, Any]:
    mirror = motor_from_catalog(pack_id=pack_id, omega_rad_s=omega_rad_s)
    rust = evaluate_dc_motor_gear(pack_id=pack_id, omega_rad_s=omega_rad_s)
    err = abs(float(mirror["tau_out_nm"]) - float(rust["tau_out_nm"])) + abs(
        float(mirror["omega_out_rad_s"]) - float(rust["omega_out_rad_s"])
    )
    return {"ok": err <= atol, "err": err, "oracle": ORACLE, "pack_id": pack_id}
