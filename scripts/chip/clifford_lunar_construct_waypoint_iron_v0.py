"""Lunar construct inter-zone waypoint — iron RTL + CXX motion rail parity."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_VEC_JSON = _REPO / "fixtures" / "chip" / "lunar_construct_waypoint_vectors_v1.json"
_VEC_BIN = _REPO / "fixtures" / "chip" / "lunar_construct_waypoint_vectors_v1.bin"
_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_LUNAR_CONSTRUCT_WAYPOINT_IRON_RECEIPT_v1.json"
_MAPPED_RECEIPT = _REPO / "results" / "platform_bpass" / "chip" / "CHIP_LUNAR_CONSTRUCT_WAYPOINT_MAPPED_STRUCTURAL_RECEIPT_v1.json"
_IRON_PARITY_TOL_M = 0.006
_MAPPED_PARITY_TOL_M = 0.012


def mint_vectors() -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.gen_lunar_construct_waypoint_vectors_v1 import (
        mint_lunar_construct_waypoint_vectors,
        write_lunar_construct_waypoint_mapped_slice_rtl_tb,
        write_lunar_construct_waypoint_rtl_tb,
        write_lunar_construct_waypoint_structural_rtl_tb,
    )

    doc = mint_lunar_construct_waypoint_vectors()
    write_lunar_construct_waypoint_rtl_tb(doc)
    return doc


def regenerate_waypoint_structural_tbs() -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.gen_lunar_construct_waypoint_vectors_v1 import (
        mint_lunar_construct_waypoint_vectors,
        write_lunar_construct_waypoint_mapped_slice_rtl_tb,
        write_lunar_construct_waypoint_structural_rtl_tb,
    )

    vectors = mint_lunar_construct_waypoint_vectors()
    write_lunar_construct_waypoint_structural_rtl_tb(vectors)
    write_lunar_construct_waypoint_mapped_slice_rtl_tb(vectors)
    return vectors


def run_cxx_motion_rail() -> dict[str, Any]:
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
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_iron_mmio_driver_v0 import _mmio_iron_rtl_closure, _parse_rtl_world_pose, _run_rtl_tb

    rtl_srcs = _mmio_iron_rtl_closure("clifford_lunar_construct_waypoint_rtl_tb_v0.v")
    mint_vectors()
    backend = backend or os.environ.get("CLIFFORD_IRON_BACKEND", "auto")
    if backend == "auto":
        for try_backend in ("iverilog", "verilator"):
            sim = _run_rtl_tb(
                rtl_srcs=rtl_srcs,
                top_module="clifford_lunar_construct_waypoint_rtl_tb_v0",
                pass_token="TB_PASS rtl_lunar_construct_waypoint",
                tmp_prefix="clifford_lunar_wp_iron_",
                backend=try_backend,
            )
            ticks = _parse_rtl_world_pose(sim["stdout"])
            if sim.get("status") == "PASS" and ticks:
                return {"backend": sim["backend"], "status": "PASS", "ticks": ticks}
        return {"backend": sim.get("backend"), "status": "FAIL", "ticks": ticks}
    sim = _run_rtl_tb(
        rtl_srcs=rtl_srcs,
        top_module="clifford_lunar_construct_waypoint_rtl_tb_v0",
        pass_token="TB_PASS rtl_lunar_construct_waypoint",
        tmp_prefix="clifford_lunar_wp_iron_",
        backend=backend,
    )
    ticks = _parse_rtl_world_pose(sim["stdout"])
    return {"backend": sim["backend"], "status": sim["status"], "ticks": ticks}


def _rmse(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> float:
    if len(a) != len(b) or not a:
        return float("inf")
    err = 0.0
    for pa, pb in zip(a, b):
        err += (pa["x_m"] - pb["x_m"]) ** 2 + (pa["y_m"] - pb["y_m"]) ** 2 + (pa["z_m"] - pb["z_m"]) ** 2
    return math.sqrt(err / len(a))


    return {"backend": sim["backend"], "status": sim["status"], "ticks": ticks}


def run_iron_structural_sim(*, backend: str | None = None) -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_iron_mmio_driver_v0 import _mmio_iron_rtl_closure, _parse_rtl_world_pose, _run_rtl_tb

    regenerate_waypoint_structural_tbs()
    rtl_srcs = _mmio_iron_rtl_closure("clifford_lunar_construct_waypoint_structural_rtl_tb_v0.v")
    backend = backend or os.environ.get("CLIFFORD_IRON_BACKEND", "auto")
    sim = _run_rtl_tb(
        rtl_srcs=rtl_srcs,
        top_module="clifford_lunar_construct_waypoint_structural_rtl_tb_v0",
        pass_token="TB_PASS rtl_lunar_construct_waypoint_structural",
        tmp_prefix="clifford_lunar_wp_struct_",
        backend=backend,
    )
    ticks = _parse_rtl_world_pose(sim["stdout"])
    return {
        "backend": sim["backend"],
        "status": sim["status"],
        "ticks": ticks,
        "sim_layer": "structural_synth_mmio",
    }


def run_iron_synth_slice_sim(*, backend: str = "auto") -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_iron_mmio_driver_v0 import _parse_rtl_mapped_pose, _run_rtl_tb

    regenerate_waypoint_structural_tbs()
    synth_srcs = [
        "sta/clifford_sta_sim_blackbox_v0.v",
        "clifford_f32_synth_v0.v",
        "clifford_geo_prod_synth_v0.v",
        "clifford_geo_prod_synth_low_blades_v0.v",
        "clifford_geo_prod_synth_low_lo_blades_v0.v",
        "clifford_geo_prod_synth_low_hi_blades_v0.v",
        "clifford_geo_prod_synth_high_blades_v0.v",
        "clifford_geo_prod_synth_high_lo_blades_v0.v",
        "clifford_geo_prod_synth_high_hi_blades_v0.v",
        "clifford_geo_prod_ex_pipe_v0.v",
        "sta/clifford_sta_geo_prod_slice_top_v0.v",
        "sta/clifford_lunar_construct_waypoint_mapped_slice_rtl_tb_v0.v",
    ]
    sim = _run_rtl_tb(
        rtl_srcs=tuple(synth_srcs),
        top_module="clifford_lunar_construct_waypoint_mapped_slice_rtl_tb_v0",
        pass_token="TB_PASS rtl_lunar_construct_waypoint_mapped_slice",
        tmp_prefix="clifford_lunar_wp_synth_",
        backend=backend,
        iverilog_defines=("-DCLIFFORD_GP_DATAPATH_SYNTH_ONLY",),
    )
    ticks = _parse_rtl_mapped_pose(sim["stdout"])
    return {
        "backend": sim["backend"],
        "status": sim["status"],
        "ticks": ticks,
        "sim_layer": "rtl_synth_slice_pipeline",
    }


def _ticks_sane(ticks: list[dict[str, Any]]) -> bool:
    if not ticks:
        return False
    for t in ticks:
        for key in ("x_m", "y_m", "z_m"):
            v = float(t[key])
            if not math.isfinite(v) or abs(v) > 500.0:
                return False
    return True


def build_lunar_construct_waypoint_mapped_structural_parity(*, write_receipt: bool = True) -> dict[str, Any]:
    vectors = mint_vectors()
    n = int(vectors.get("tick_count") or 0)
    backend = os.environ.get("CLIFFORD_IRON_BACKEND", "auto")

    behavioral = run_iron_sim(backend=backend)
    structural = run_iron_structural_sim(backend=backend)
    synth_slice = run_iron_synth_slice_sim(backend=backend)

    b_ticks = [
        {
            "tick": int(t["tick"]),
            "x_m": float(t["x_m"]),
            "y_m": float(t["y_m"]),
            "z_m": float(t["z_m"]),
        }
        for t in behavioral.get("ticks") or []
    ]
    s_ticks = [
        {
            "tick": int(t["tick"]),
            "x_m": float(t["x_m"]),
            "y_m": float(t["y_m"]),
            "z_m": float(t["z_m"]),
        }
        for t in structural.get("ticks") or []
    ]
    ss_ticks = list(synth_slice.get("ticks") or [])

    behavioral_ok = behavioral.get("status") == "PASS" and len(b_ticks) == n
    struct_rmse = _rmse(b_ticks, s_ticks) if behavioral_ok and structural.get("status") == "PASS" else float("inf")
    synth_rmse = _rmse(b_ticks, ss_ticks) if behavioral_ok and _ticks_sane(ss_ticks) else float("inf")

    struct_ok = (
        structural.get("status") == "PASS"
        and behavioral_ok
        and math.isfinite(struct_rmse)
        and struct_rmse < _MAPPED_PARITY_TOL_M
    )
    synth_ok = (
        synth_slice.get("status") == "PASS"
        and _ticks_sane(ss_ticks)
        and behavioral_ok
        and math.isfinite(synth_rmse)
        and synth_rmse < _MAPPED_PARITY_TOL_M
    )

    verdict = "PASS" if struct_ok and synth_ok else ("DEGRADED" if struct_ok else "FAIL")
    doc = {
        "receipt_id": "CHIP_LUNAR_CONSTRUCT_WAYPOINT_MAPPED_STRUCTURAL_RECEIPT_v1",
        "verdict": "LUNAR_CONSTRUCT_WAYPOINT_MAPPED_STRUCTURAL_PASS" if verdict == "PASS" else "LUNAR_CONSTRUCT_WAYPOINT_MAPPED_STRUCTURAL_FAIL",
        "profile_id": vectors.get("profile_id"),
        "tick_count": n,
        "segment_count": vectors.get("segment_count"),
        "behavioral_mmio": {
            "status": behavioral.get("status"),
            "backend": behavioral.get("backend"),
            "ticks": len(b_ticks),
        },
        "structural_synth_mmio": {
            "status": structural.get("status"),
            "backend": structural.get("backend"),
            "ticks": len(s_ticks),
            "rmse_vs_behavioral_m": round(struct_rmse, 6) if math.isfinite(struct_rmse) else None,
            "parity_ok": struct_ok,
        },
        "rtl_synth_slice_pipeline": {
            "status": synth_slice.get("status"),
            "backend": synth_slice.get("backend"),
            "ticks": len(ss_ticks),
            "rmse_vs_behavioral_m": round(synth_rmse, 6) if math.isfinite(synth_rmse) else None,
            "parity_ok": synth_ok,
        },
        "mapped_structural_ok": struct_ok and synth_ok,
        "parity_tol_m": _MAPPED_PARITY_TOL_M,
        "product_ready": False,
    }

    if write_receipt:
        _MAPPED_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _MAPPED_RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def build_lunar_construct_waypoint_iron_rail(*, write_receipt: bool = True) -> dict[str, Any]:
    vectors = mint_vectors()
    iron = run_iron_sim()
    cxx = run_cxx_motion_rail()

    iron_ticks = [
        {
            "tick": int(t["tick"]),
            "path_s": float(t["meters"]),
            "x_m": round(float(t["x_m"]), 6),
            "y_m": round(float(t["y_m"]), 6),
            "z_m": round(float(t["z_m"]), 6),
            "backend": "iron_rtl_mmio",
        }
        for t in iron.get("ticks") or []
    ]
    cxx_ticks = list(cxx.get("ticks") or [])
    n = int(vectors.get("tick_count") or 0)
    iron_ok = iron.get("status") == "PASS" and len(iron_ticks) == n
    cxx_ok = cxx.get("status") == "PASS" and len(cxx_ticks) == n
    rmse = _rmse(iron_ticks, cxx_ticks) if iron_ok and cxx_ok else float("inf")
    parity_ok = iron_ok and cxx_ok and rmse < _IRON_PARITY_TOL_M

    oracle_rmse = float("inf")
    if iron_ok:
        oracle_ticks = [
            {"x_m": float(t["oracle_x_m"]), "y_m": float(t["oracle_y_m"]), "z_m": float(t["oracle_z_m"])}
            for t in vectors.get("ticks") or []
        ]
        oracle_rmse = _rmse(iron_ticks, oracle_ticks)

    rail = {
        "verdict": "PASS" if parity_ok and oracle_rmse < _IRON_PARITY_TOL_M else ("DEGRADED" if iron_ok else "FAIL"),
        "profile_id": vectors.get("profile_id"),
        "primary_backend": "iron_rtl_mmio" if iron_ok else "none",
        "iron_sim_backend": iron.get("backend"),
        "iron_cxx_rmse_m": round(rmse, 6) if math.isfinite(rmse) else None,
        "iron_oracle_rmse_m": round(oracle_rmse, 6) if math.isfinite(oracle_rmse) else None,
        "iron_cxx_parity_ok": parity_ok,
        "iron_oracle_parity_ok": iron_ok and oracle_rmse < _IRON_PARITY_TOL_M,
        "segment_count": vectors.get("segment_count"),
        "tick_count": n,
        "iron": {"status": iron.get("status"), "ticks": len(iron_ticks)},
        "cxx": {"status": cxx.get("status"), "ticks": len(cxx_ticks)},
    }

    if write_receipt:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(
            json.dumps(
                {
                    "receipt_id": "CHIP_LUNAR_CONSTRUCT_WAYPOINT_IRON_RECEIPT_v1",
                    "verdict": "LUNAR_CONSTRUCT_WAYPOINT_IRON_PASS" if rail["verdict"] == "PASS" else "LUNAR_CONSTRUCT_WAYPOINT_IRON_FAIL",
                    "iron_sim_backend": rail["iron_sim_backend"],
                    "iron_cxx_rmse_m": rail["iron_cxx_rmse_m"],
                    "iron_oracle_rmse_m": rail["iron_oracle_rmse_m"],
                    "iron_cxx_parity_ok": parity_ok,
                    "ticks": n,
                    "segment_count": vectors.get("segment_count"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return rail


if __name__ == "__main__":
    r = build_lunar_construct_waypoint_iron_rail()
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["verdict"] == "PASS" else 1)
