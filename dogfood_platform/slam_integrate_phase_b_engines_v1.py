"""Phase B — integrate L0–L5 dataset-bound engines with strict wiring proofs."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from dogfood_platform.slam_integrate_l0_l5_v1 import (
    E2E_ROT_ERR_MAX_DEG,
    E2E_TRANS_ERR_MAX_M,
    L1_MIN_EVENTS,
    R1_RMSE_CEILING_M,
    _motor_from_dict,
    _quat_angle_deg,
    _trans_err_m,
)
from dogfood_platform.slam_l1_event_engine_v1 import collect_event_point_indices, run_l1_event_engine
from dogfood_platform.slam_l2_odom_engine_v1 import run_l2_odom_engine
from dogfood_platform.slam_l3_pose_engine_v1 import run_l3_pose_engine
from dogfood_platform.slam_l4_map_engine_v1 import run_l4_map_engine
from dogfood_platform.slam_l5_loop_engine_v1 import run_l5_loop_engine
from dogfood_platform.slam_reform_resample_v1 import load_or_build_dataset
from dogfood_platform.slam_se3_motor_v1 import Motor, motor_from_axis_angle, rmse_m

R1_RMSE_REF_PATH = "results/platform_bpass/chip/CHIP_IFT3_SLAM_REFORM_R1_RECEIPT_v1.json"


@dataclass
class PhaseBIntegratedStack:
    l0: dict[str, Any]
    l1: dict[str, Any]
    l2: dict[str, Any]
    l3: dict[str, Any]
    l4: dict[str, Any]
    l5: dict[str, Any]
    wiring: dict[str, bool]
    metrics: dict[str, Any]
    checks: list[dict[str, Any]] = field(default_factory=list)
    verdict: str = "DEGRADED"
    skip_l3: bool = False


def _stack_replay_hash(layers: dict[str, str]) -> str:
    payload = json.dumps(layers, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _l0_engine(data: dict[str, Any]) -> dict[str, Any]:
    bind = f"{data['dataset_id']}:{data['seed']}:{data['noise_sigma_m']}"
    replay = hashlib.sha256(bind.encode()).hexdigest()[:16]
    return {
        "engine_id": "slam_l0_dataset_bind_v1",
        "execution_phase": "B",
        "dataset_id": data["dataset_id"],
        "dataset_seed": data["seed"],
        "noise_sigma_m": float(data["noise_sigma_m"]),
        "n_points": len(data["src_points"]),
        "true_motor": data["true_motor"],
        "deterministic_replay_hash": replay,
        "oracle": "DATASET_ENGINE_SIM",
    }


def _motor_from_l3(engine: dict[str, Any]) -> Motor:
    reg = engine["registration"]["motor"]
    return Motor(
        qw=float(reg["qw"]),
        qx=float(reg["qx"]),
        qy=float(reg["qy"]),
        qz=float(reg["qz"]),
        tx=float(reg["tx"]),
        ty=float(reg["ty"]),
        tz=float(reg["tz"]),
    )


def run_integrated_phase_b_engines(
    *,
    skip_l3: bool = False,
    r1_rmse_ref: float | None = None,
) -> PhaseBIntegratedStack:
    data = load_or_build_dataset()
    l0 = _l0_engine(data)
    l1 = run_l1_event_engine()
    l2 = run_l2_odom_engine(l1=l1)
    l3 = run_l3_pose_engine(l2=l2)

    if skip_l3:
        identity = motor_from_axis_angle((0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))
        l3 = {
            **l3,
            "registration": {
                **l3["registration"],
                "motor": {
                    "qw": identity.qw,
                    "qx": identity.qx,
                    "qy": identity.qy,
                    "qz": identity.qz,
                    "tx": identity.tx,
                    "ty": identity.ty,
                    "tz": identity.tz,
                },
                "rmse_m": 999.0,
            },
            "falsifiers": {**l3.get("falsifiers", {}), "reform_rmse_under_8cm": False},
        }

    l4 = run_l4_map_engine(l1=l1, l3=l3)
    l5 = run_l5_loop_engine(l2=l2, l4=l4)

    true_motor = _motor_from_dict(data["true_motor"])
    est_motor = _motor_from_l3(l3)
    src_points = [tuple(p) for p in data["src_points"]]
    dst_points = [tuple(p) for p in data["dst_points"]]

    event_indices = collect_event_point_indices(
        n_ticks=int(l1["parameters"]["n_ticks"]),
        step_m=float(l1["parameters"]["step_m"]),
    )
    trans_err = _trans_err_m(est_motor, true_motor)
    rot_err = _quat_angle_deg(est_motor, true_motor)
    dst_fit = rmse_m([est_motor.apply(p) for p in src_points], dst_points)
    l3_rmse = float(l3["registration"]["rmse_m"])

    wiring = {
        "L0_dataset_bound": l0["dataset_id"] == "cave_corridor_dataset_v1",
        "L1_to_L2_tick_lock": l2["falsifiers"]["l1_l2_tick_lock"],
        "L1_frame_poses_match_L2": l2["n_poses"] == int(l1["n_ticks"]) + 1,
        "L1_events_to_L4": l4["compose"]["map_point_count"] == len(event_indices),
        "L3_motor_to_L4": l4["compose"]["tile_count"] > 0,
        "L2_hash_bound_in_L5": l5["l2_odom_replay_hash"] == l2["deterministic_replay_hash"],
        "L4_hash_bound_in_L5": l5["l4_map_replay_hash"] == l4["deterministic_replay_hash"],
        "L2_encoder_physics_in_L5": l5["loop_closure"]["odom_rng_seed"] == l2["odom_rng_seed"],
        "skip_l3": skip_l3,
    }

    metrics = {
        "l1_event_count": l1["event_count"],
        "l1_event_indices": len(event_indices),
        "l2_odom_poses": l2["n_poses"],
        "l3_rmse_m": round(l3_rmse, 5),
        "l4_tile_count": l4["compose"]["tile_count"],
        "l4_map_points": l4["compose"]["map_point_count"],
        "l5_loop_gap_after_m": l5["loop_closure"]["loop_gap_after_m"],
        "l5_loop_poses": l5["loop_closure"]["traverse"]["n_poses"],
        "e2e_trans_err_m": round(trans_err, 4),
        "e2e_rot_err_deg": round(rot_err, 4),
        "e2e_dst_fit_rmse_m": round(dst_fit, 5),
        "stack_replay_hash": _stack_replay_hash(
            {
                "L0": l0["deterministic_replay_hash"],
                "L1": l1["deterministic_replay_hash"],
                "L2": l2["deterministic_replay_hash"],
                "L3": l3["deterministic_replay_hash"],
                "L4": l4["deterministic_replay_hash"],
                "L5": l5["deterministic_replay_hash"],
            }
        ),
        "layer_replay_hashes": {
            "L0": l0["deterministic_replay_hash"],
            "L1": l1["deterministic_replay_hash"],
            "L2": l2["deterministic_replay_hash"],
            "L3": l3["deterministic_replay_hash"],
            "L4": l4["deterministic_replay_hash"],
            "L5": l5["deterministic_replay_hash"],
        },
    }

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("l1_events_min", l1["event_count"] >= L1_MIN_EVENTS, str(l1["event_count"]))
    chk("l1_l2_tick_lock", wiring["L1_to_L2_tick_lock"])
    chk("l1_to_l4_wiring", wiring["L1_events_to_L4"], str(l4["compose"]["map_point_count"]))
    chk("l3_rmse_under_ceiling", l3_rmse < R1_RMSE_CEILING_M, f"{l3_rmse:.5f}")
    if r1_rmse_ref is not None and not skip_l3:
        chk(
            "l3_matches_r1_standalone",
            l3_rmse <= r1_rmse_ref * 1.02,
            f"l3={l3_rmse:.5f} r1={r1_rmse_ref:.5f}",
        )
    chk("l4_tiles_created", l4["compose"]["tile_count"] > 0)
    chk("l5_loop_detected", l5["loop_closure"]["loop_detected"])
    chk(
        "l5_gap_closed",
        l5["loop_closure"]["loop_gap_after_m"] < 0.05,
        str(l5["loop_closure"]["loop_gap_after_m"]),
    )
    chk("l2_l5_hash_bind", wiring["L2_hash_bound_in_L5"])
    chk("l4_l5_hash_bind", wiring["L4_hash_bound_in_L5"])
    chk("e2e_trans_err", trans_err < E2E_TRANS_ERR_MAX_M, f"{trans_err:.4f}")
    chk("e2e_rot_err", rot_err < E2E_ROT_ERR_MAX_DEG, f"{rot_err:.4f}")
    chk("e2e_dst_fit", dst_fit < R1_RMSE_CEILING_M, f"{dst_fit:.5f}")
    if skip_l3:
        chk(
            "skip_l3_must_fail_e2e",
            trans_err > 0.5 or dst_fit > 0.5,
            f"trans={trans_err:.4f} dst={dst_fit:.5f}",
        )
    else:
        chk("skip_l3_must_fail_e2e", True, "n/a")

    verdict = "PASS" if all(c["pass"] for c in checks) else "DEGRADED"

    return PhaseBIntegratedStack(
        l0=l0,
        l1=l1,
        l2=l2,
        l3=l3,
        l4=l4,
        l5=l5,
        wiring=wiring,
        metrics=metrics,
        checks=checks,
        verdict=verdict,
        skip_l3=skip_l3,
    )


def stack_to_dict(stack: PhaseBIntegratedStack) -> dict[str, Any]:
    return {
        "verdict": stack.verdict,
        "skip_l3": stack.skip_l3,
        "wiring": stack.wiring,
        "metrics": stack.metrics,
        "checks": stack.checks,
        "layers": {
            "L0": {"n_points": stack.l0["n_points"], "noise_sigma_m": stack.l0["noise_sigma_m"]},
            "L1": {
                "n_ticks": stack.l1["n_ticks"],
                "event_count": stack.l1["event_count"],
                "replay_hash": stack.l1["deterministic_replay_hash"],
            },
            "L2": {"n_poses": stack.l2["n_poses"], "replay_hash": stack.l2["deterministic_replay_hash"]},
            "L3": {"rmse_m": stack.l3["registration"]["rmse_m"], "replay_hash": stack.l3["deterministic_replay_hash"]},
            "L4": {
                "tile_count": stack.l4["compose"]["tile_count"],
                "replay_hash": stack.l4["deterministic_replay_hash"],
            },
            "L5": {
                "loop_gap_after_m": stack.l5["loop_closure"]["loop_gap_after_m"],
                "replay_hash": stack.l5["deterministic_replay_hash"],
            },
        },
    }
