"""Compose-tier hot-loop benchmark — python traverse vs cxx CGA32 vs iron model."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_COMPOSE_TIER_BENCHMARK_RECEIPT_v1.json"
_P65 = _CHIP / "CHIP_CLIFFORD_DEVICE_RUST_P6_5_RECEIPT_v1.json"

# v0 macro-cycle: 8 φ ticks @ 10 ns (clifford_alu_macro_cycle_v0.sdc)
_IRON_PHI_TICKS = 8
_IRON_CLOCK_NS = 10.0
_IRON_COMPOSE_NS = _IRON_PHI_TICKS * _IRON_CLOCK_NS
# T2.5 overlap steady: 2 φ ticks @ 10 ns (scheduler sim — not alu_top)
_IRON_OVERLAP_PHI_TICKS = 2
_IRON_OVERLAP_COMPOSE_NS = _IRON_OVERLAP_PHI_TICKS * _IRON_CLOCK_NS
_T25 = _CHIP / "CHIP_CLIFFORD_PHI_OVERLAP_T2_5_RECEIPT_v1.json"


def _lunar_compose_count(*, n_steps: int = 48) -> int:
    return n_steps


def _traverse_loop_compose_count(*, n_forward: int = 14) -> int:
    return (n_forward - 1) + (n_forward - 1)


def _bench_python_dq(n: int) -> dict[str, Any]:
    from scripts.chip.clifford_cga_lunar_tier_study_v1 import _deltas_lunar_slow_joint
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    deltas = _deltas_lunar_slow_joint(n)
    acc = DqMotor.identity()
    t0 = time.perf_counter()
    for d in deltas:
        acc = DqMotor.from_motor7(d).geo_prod(acc)
    us = (time.perf_counter() - t0) * 1e6
    return {
        "path": "python_dq_geo_prod",
        "composes": len(deltas),
        "total_us": round(us, 3),
        "us_per_compose": round(us / max(len(deltas), 1), 3),
        "final_motor128": acc.to_motor128_hex(),
    }


def _bench_python_cga32_embed(n: int) -> dict[str, Any]:
    from scripts.chip.clifford_cga32_oracle_v1 import Cga32Motor
    from scripts.chip.clifford_cga_lunar_tier_study_v1 import _deltas_lunar_slow_joint
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    deltas = _deltas_lunar_slow_joint(n)
    acc = Cga32Motor.from_dq_motor128(DqMotor.identity().to_motor128_hex())
    t0 = time.perf_counter()
    for d in deltas:
        step = Cga32Motor.from_dq_motor128(DqMotor.from_motor7(d).to_motor128_hex())
        acc = step.geo_prod(acc)
    us = (time.perf_counter() - t0) * 1e6
    return {
        "path": "python_cga32_embed_geo_prod",
        "composes": len(deltas),
        "total_us": round(us, 3),
        "us_per_compose": round(us / max(len(deltas), 1), 3),
        "final_motor512": acc.to_motor512_hex(),
    }


def _embed_delta_hex(d: Any) -> str:
    from scripts.chip.clifford_cga32_oracle_v1 import Cga32Motor
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor

    return Cga32Motor.from_dq_motor128(DqMotor.from_motor7(d).to_motor128_hex()).to_motor512_hex()


def _bench_cxx_cga32_chain(n: int) -> dict[str, Any]:
    from scripts.chip.clifford_cga32_oracle_v1 import Cga32Motor
    from scripts.chip.clifford_cga_lunar_tier_study_v1 import _deltas_lunar_slow_joint
    from scripts.chip.clifford_cga_motor_oracle_v1 import DqMotor
    from dogfood_platform._clifford_soft_gp_build_v1 import cmake_build_clifford_soft_gp, find_exe

    deltas = _deltas_lunar_slow_joint(n)
    build = cmake_build_clifford_soft_gp()
    exe = find_exe(build, "clifford_gp_cli")
    if not exe:
        return {"path": "cxx_cga32_chain", "error": "gp_cli missing"}

    acc = Cga32Motor.from_dq_motor128(DqMotor.identity().to_motor128_hex()).to_motor512_hex()
    t0 = time.perf_counter()
    for d in deltas:
        step = _embed_delta_hex(d)
        proc = subprocess.run(
            [str(exe)],
            input=f"cga32_geo_prod {step} {acc}\n",
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return {"path": "cxx_cga32_chain", "error": (proc.stderr or proc.stdout)[-200:]}
        acc = json.loads(proc.stdout.strip()).get("rd_hex", "")
    us = (time.perf_counter() - t0) * 1e6
    return {
        "path": "cxx_cga32_lunar_chain",
        "composes": len(deltas),
        "total_us": round(us, 3),
        "us_per_compose": round(us / max(len(deltas), 1), 3),
        "final_motor512": acc.lower(),
        "note": "per-compose gp_cli subprocess — includes IPC overhead",
    }


def _bench_cxx_cga32_throughput(n: int) -> dict[str, Any]:
    from dogfood_platform._clifford_soft_gp_build_v1 import cmake_build_clifford_soft_gp, find_exe

    build = cmake_build_clifford_soft_gp()
    exe = find_exe(build, "clifford_gp_cli")
    if not exe:
        return {"path": "cxx_cga32_bench", "error": "gp_cli missing"}

    proc = subprocess.run(
        [str(exe)],
        input=f"cga32_bench {n}\n",
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {"path": "cxx_cga32_bench", "error": (proc.stderr or proc.stdout)[-200:]}
    doc = json.loads(proc.stdout.strip())
    us = float(doc["us"])
    return {
        "path": "cxx_cga32_geo_prod_throughput",
        "composes": int(doc["n"]),
        "total_us": round(us, 3),
        "us_per_compose": round(us / max(int(doc["n"]), 1), 3),
        "final_motor512": doc.get("rd_hex", ""),
    }


def _iron_modeled(n: int) -> dict[str, Any]:
    total_ns = n * _IRON_COMPOSE_NS
    return {
        "path": "iron_mmio_op4_modeled",
        "composes": n,
        "total_ns": total_ns,
        "ns_per_compose": _IRON_COMPOSE_NS,
        "total_us": round(total_ns / 1000.0, 6),
        "us_per_compose": round(total_ns / 1000.0 / max(n, 1), 6),
        "honesty": "v0 unpipelined φ macro · not Verilator wall-clock per compose",
    }


def _iron_overlap_modeled(n: int) -> dict[str, Any]:
    total_ns = n * _IRON_OVERLAP_COMPOSE_NS
    return {
        "path": "iron_overlap_t2_5_modeled",
        "composes": n,
        "total_ns": total_ns,
        "ns_per_compose": _IRON_OVERLAP_COMPOSE_NS,
        "total_us": round(total_ns / 1000.0, 6),
        "us_per_compose": round(total_ns / 1000.0 / max(n, 1), 6),
        "honesty": "T2.5 scheduler sim steady 1 motor/2φ · not wired to alu_top",
    }


def run_compose_tier_benchmark(*, n_lunar: int = 48, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    p65_ok = _P65.is_file() and json.loads(_P65.read_text(encoding="utf-8")).get("verdict") == "RUST_DEVICE_P6_5_PASS"

    py_dq = _bench_python_dq(n_lunar)
    py_cga32 = _bench_python_cga32_embed(n_lunar)
    cxx_chain = _bench_cxx_cga32_chain(n_lunar)
    cxx_tp = _bench_cxx_cga32_throughput(n_lunar)
    iron = _iron_modeled(n_lunar)
    t25_ok = _T25.is_file() and json.loads(_T25.read_text(encoding="utf-8")).get("verdict") == "PHI_OVERLAP_T2_5_PASS"
    iron_overlap = _iron_overlap_modeled(n_lunar) if t25_ok else None

    n_traverse = _traverse_loop_compose_count()
    traverse_note = {
        "simulate_loop_traverse_ticks_composes": n_traverse,
        "lunar_slow_joint_composes": n_lunar,
    }

    parity_ok = (
        py_cga32.get("final_motor512", "").lower()
        == cxx_chain.get("final_motor512", "").lower()
        != ""
    )

    speedup_tp = None
    if py_cga32.get("us_per_compose") and cxx_tp.get("us_per_compose"):
        speedup_tp = round(py_cga32["us_per_compose"] / cxx_tp["us_per_compose"], 2)

    checks = [
        {"id": "p65_host_bridge", "pass": p65_ok},
        {"id": "cxx_cga32_chain_ran", "pass": "error" not in cxx_chain},
        {"id": "cga32_lunar_chain_parity", "pass": parity_ok},
        {"id": "cxx_throughput_faster_than_python", "pass": speedup_tp is not None and speedup_tp > 1.0},
    ]

    verdict = "COMPOSE_TIER_BENCHMARK_PASS" if all(c["pass"] for c in checks) else "COMPOSE_TIER_BENCHMARK_FAIL"
    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_COMPOSE_TIER_BENCHMARK_RECEIPT_v1",
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "traverse_note": traverse_note,
        "benchmarks": {
            "python_dq": py_dq,
            "python_cga32_embed": py_cga32,
            "cxx_cga32_lunar_chain": cxx_chain,
            "cxx_cga32_throughput": cxx_tp,
            "iron_modeled_op4": iron,
            **({"iron_modeled_overlap_t2_5": iron_overlap} if iron_overlap else {}),
        },
        "speedup": {
            "cxx_throughput_vs_python_cga32": speedup_tp,
            "python_cga32_vs_iron_modeled_us": round(
                py_cga32.get("us_per_compose", 0) / max(iron.get("us_per_compose", 1e-9), 1e-9), 1
            )
            if py_cga32.get("us_per_compose")
            else None,
            "cxx_throughput_vs_iron_modeled_us": round(
                cxx_tp.get("us_per_compose", 0) / max(iron.get("us_per_compose", 1e-9), 1e-9), 1
            )
            if cxx_tp.get("us_per_compose")
            else None,
        },
        "honesty": {
            "dataset": "lunar_slow_joint deltas (same as tier study)",
            "iron": f"modeled {_IRON_COMPOSE_NS} ns/compose unpipelined · overlap {_IRON_OVERLAP_COMPOSE_NS} ns if T2.5 PASS",
            "hot_loop_goal": "traverse compose_tier → host cga32 → future MMIO OP=4",
            "phi_overlap_t2_5": "PHI_OVERLAP_T2_5_PASS" if t25_ok else "OPEN",
        },
    }
    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(run_compose_tier_benchmark(), indent=2))
