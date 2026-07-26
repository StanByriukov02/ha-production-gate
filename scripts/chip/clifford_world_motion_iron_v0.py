"""World combat motion — iron verilator/iverilog + cxx (chip track, not dogfood theater)."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_VEC_JSON = _REPO / "fixtures" / "chip" / "clifford_world_motion_vectors_v1.json"
_VEC_BIN = _REPO / "fixtures" / "chip" / "clifford_world_motion_vectors_v1.bin"
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_CLIFFORD_WORLD_MOTION_IRON_RECEIPT_v1.json"
_IRON_PARITY_TOL_M = 0.006


def mint_vectors() -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.gen_clifford_world_motion_iron_v0 import mint_world_motion_vectors, write_world_motion_rtl_tb

    doc = mint_world_motion_vectors()
    write_world_motion_rtl_tb(doc)
    return doc


def run_cxx_rail() -> dict[str, Any]:
    import subprocess

    from dogfood_platform._clifford_soft_gp_build_v1 import cmake_build_clifford_soft_gp, find_exe

    build = cmake_build_clifford_soft_gp()
    exe = find_exe(build, "clifford_world_motion_rail")
    if not exe or not _VEC_BIN.is_file():
        return {"status": "FAIL", "backend": "cxx", "ticks": []}
    proc = subprocess.run([str(exe), str(_VEC_BIN)], capture_output=True, text=True, check=False, timeout=120)
    if proc.returncode != 0:
        return {"status": "FAIL", "backend": "cxx", "ticks": [], "stderr": (proc.stderr or "")[-400:]}
    ticks = list(json.loads(proc.stdout.strip()).get("ticks") or [])
    return {"status": "PASS" if ticks else "FAIL", "backend": "cxx", "ticks": ticks}


def run_iron_sim(*, backend: str | None = None) -> dict[str, Any]:
    import os

    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_iron_mmio_driver_v0 import run_iron_world_motion_sim

    backend = backend or os.environ.get("CLIFFORD_IRON_BACKEND", "auto")
    if backend == "auto":
        v = run_iron_world_motion_sim(backend="verilator")
        if v.get("status") == "PASS":
            return v
        return run_iron_world_motion_sim(backend="iverilog")
    return run_iron_world_motion_sim(backend=backend)


def _rmse(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> float:
    if len(a) != len(b) or not a:
        return float("inf")
    err = 0.0
    for pa, pb in zip(a, b):
        err += (pa["x_m"] - pb["x_m"]) ** 2 + (pa["y_m"] - pb["y_m"]) ** 2 + (pa["z_m"] - pb["z_m"]) ** 2
    return math.sqrt(err / len(a))


def _iron_clock() -> dict[str, Any]:
    p = _REPO / "fixtures" / "twin" / "dogfood_twin_iron_clock_feed_v1.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def build_world_motion_rail(*, write_receipt: bool = True) -> dict[str, Any]:
    vectors = mint_vectors()
    iron = run_iron_sim()
    cxx = run_cxx_rail()
    clock = _iron_clock()

    iron_ticks = [
        {
            "tick": int(t["tick"]),
            "meters": float(t["meters"]),
            "x_m": round(float(t["x_m"]), 6),
            "y_m": round(float(t["y_m"]), 6),
            "z_m": round(float(t["z_m"]), 6),
            "backend": "iron_rtl_mmio",
            "pose_engine": "clifford_alu_mmio_v0_2x_geo_prod",
            "iron_sim_backend": iron.get("backend"),
            "transform": "gp(gp(R,p),reverse(R))",
        }
        for t in iron.get("ticks") or []
    ]
    cxx_ticks = list(cxx.get("ticks") or [])
    n = int(vectors.get("tick_count") or 0)
    iron_ok = iron.get("status") == "PASS" and len(iron_ticks) == n
    cxx_ok = cxx.get("status") == "PASS" and len(cxx_ticks) == n
    rmse = _rmse(iron_ticks, cxx_ticks) if iron_ok and cxx_ok else float("inf")
    parity_ok = iron_ok and cxx_ok and rmse < _IRON_PARITY_TOL_M

    points: list[dict[str, Any]] = []
    if iron_ok:
        points = iron_ticks
        for p, cx in zip(points, cxx_ticks):
            p["rotor_hex"] = cx.get("rotor_hex")
            p["pose_hex"] = cx.get("pose_hex")
    elif cxx_ok:
        points = [
            {**t, "backend": "cxx", "pose_engine": "clifford_soft_gp_geo_prod", "transform": "gp(gp(R,p),reverse(R))"}
            for t in cxx_ticks
        ]

    vec_by_tick = {int(t["tick"]): t for t in vectors.get("ticks") or []}
    macro_ns = float(clock.get("macro_compose_ns") or 290.909)
    macro_ticks = int(clock.get("macro_phi_ticks") or 8)
    for p in points:
        ti = int(p["tick"])
        src = vec_by_tick.get(ti, {})
        p["theta_rad"] = round(float(src.get("theta_rad", 0.0)), 9)
        p["phi_macro_tick"] = ti % macro_ticks
        p["iron_time_us"] = round(ti * macro_ns / 1000.0, 3)
        p["iron_binding"] = clock.get("binding")
        p["sta_wns_ns"] = clock.get("wns_ns")

    rail = {
        "verdict": "PASS" if parity_ok else ("DEGRADED" if points else "FAIL"),
        "primary_backend": "iron_rtl_mmio" if iron_ok else ("cxx" if cxx_ok else "none"),
        "iron_sim_backend": iron.get("backend"),
        "iron": {"status": iron.get("status"), "ticks": len(iron_ticks)},
        "cxx": {"status": cxx.get("status"), "ticks": len(cxx_ticks)},
        "iron_cxx_rmse_m": round(rmse, 6) if math.isfinite(rmse) else None,
        "iron_cxx_parity_ok": parity_ok,
        "sta_binding": clock.get("binding"),
        "sta_wns_ns": clock.get("wns_ns"),
        "points": points,
        "tick_count": len(points),
    }

    sta_bind: dict[str, Any] | None = None
    if write_receipt:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(
            json.dumps(
                {
                    "receipt_id": "CHIP_CLIFFORD_WORLD_MOTION_IRON_RECEIPT_v1",
                    "verdict": rail["verdict"],
                    "iron_sim_backend": rail["iron_sim_backend"],
                    "iron_cxx_rmse_m": rail["iron_cxx_rmse_m"],
                    "iron_cxx_parity_ok": parity_ok,
                    "sta_binding": rail["sta_binding"],
                    "sta_wns_ns": rail["sta_wns_ns"],
                    "ticks": rail["tick_count"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if parity_ok or points:
            from scripts.chip.clifford_world_motion_sta_bind_v0 import build_world_motion_sta_bind

            sta_bind = build_world_motion_sta_bind(write=True)
            rail["sta_bind_verdict"] = sta_bind.get("verdict")
        try:
            from scripts.chip.clifford_world_motion_mapped_mmio_v0 import build_mapped_mmio_parity

            mapped = build_mapped_mmio_parity(write=True)
            rail["mapped_mmio_verdict"] = mapped.get("verdict")
            rail["structural_synth_parity_ok"] = (mapped.get("structural_synth_mmio") or {}).get("parity_ok")
            rail["mapped_slice_parity_ok"] = (mapped.get("mapped_netlist_slice") or {}).get("parity_ok")
        except Exception as exc:
            rail["mapped_mmio_verdict"] = "FAIL"
            rail["mapped_mmio_error"] = str(exc)[:200]
    return rail


if __name__ == "__main__":
    r = build_world_motion_rail()
    print(json.dumps({k: v for k, v in r.items() if k != "points"}, indent=2))
    raise SystemExit(0 if r["verdict"] == "PASS" else 1)
