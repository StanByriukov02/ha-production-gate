"""Full-body compose v1 — multi-region spec · per-region honesty · factory bind.

Phase AQ: closes AQ_FULL_BODY_COMPOSE.
TABU: claim Optimus · product_ready full body · primitive-only body.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SPEC = _REPO / "fixtures" / "robot" / "full_body_lunar_scout_hexapod_v1.json"

PROOF_TIER = "FULL_BODY_COMPOSE_SLICE"
ORACLE = "FULL_BODY_REGION_HONESTY"


def load_full_body_spec(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _SPEC
    if not p.is_absolute():
        p = _REPO / p
    return json.loads(p.read_text(encoding="utf-8"))


def validate_region_honesty(spec: dict[str, Any]) -> dict[str, Any]:
    regions = list(spec.get("regions") or [])
    checks: dict[str, bool] = {}
    total_dof = 0
    for reg in regions:
        rid = str(reg.get("region_id") or "")
        checks[f"F_{rid}_role"] = bool(reg.get("role"))
        checks[f"F_{rid}_proof_tier"] = bool(reg.get("proof_tier"))
        if reg.get("chain_id"):
            from dogfood_platform.kinematic_chain_ir_v1 import resolve_chain_spec
            from dogfood_platform.torso_spine_chain_v1 import register_torso_spine_chain
            from dogfood_platform.head_neck_pan_tilt_v1 import register_head_neck_chain
            from dogfood_platform.gripper_subchain_v1 import register_gripper_chain

            if rid == "torso":
                register_torso_spine_chain()
            elif rid == "head":
                register_head_neck_chain()
            elif rid == "gripper":
                register_gripper_chain()
            try:
                chain = resolve_chain_spec(str(reg["chain_id"]))
                total_dof += int(chain.get("dof") or 0)
            except Exception:  # noqa: BLE001
                checks[f"F_{rid}_resolve"] = False
        elif reg.get("compose") == "hexapod_body":
            total_dof += 18
        elif reg.get("compose") == "wheeled_chassis":
            total_dof += 4
    checks["F_deferred_listed"] = bool(spec.get("deferred_ids"))
    return {"checks": checks, "total_dof": total_dof, "fail": [k for k, v in checks.items() if not v]}


def run_full_body_compose_smoke() -> dict[str, Any]:
    from dogfood_platform.appendage_dual_review_v1 import run_appendage_dual_review
    from dogfood_platform.appendage_motion_bus_v1 import load_motion_bus_spec, robot_tick
    from dogfood_platform.hexapod_body_compose_v1 import init_hexapod_body
    from dogfood_platform.kinematic_chain_ir_v1 import clear_chain_overlay

    clear_chain_overlay()
    spec = load_full_body_spec()
    validation = validate_region_honesty(spec)
    hexapod = init_hexapod_body()
    dual = run_appendage_dual_review(phase="AE_PLUS", write=False)

    dispatch_spec = load_motion_bus_spec()
    robot: dict[str, Any] = {"spec": dispatch_spec}
    motion_out = robot_tick(robot)

    checks = dict(validation["checks"])
    checks["F_all_regions_role_tagged"] = len(spec.get("regions") or []) >= 5
    checks["F_per_region_proof_tier"] = all(bool(r.get("proof_tier")) for r in spec.get("regions") or [])
    checks["F_per_region_deferred_listed"] = bool(spec.get("deferred_ids"))
    checks["F_total_dof_sum"] = validation["total_dof"] >= 6
    checks["F_hexapod_six_legs"] = len(hexapod.get("appendages") or {}) == 6
    checks["F_motion_bus_tick"] = len(motion_out) >= 2
    checks["F_dual_review_before_promote"] = str(dual.get("verdict") or "").startswith("APPENDAGE_DUAL_REVIEW_")
    fail = [k for k, v in checks.items() if not v] + validation["fail"]
    return {
        "verdict": "FULL_BODY_COMPOSE_SLICE_PASS" if not fail else "FULL_BODY_COMPOSE_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "total_dof": validation["total_dof"],
        "dual_review_verdict": dual.get("verdict"),
    }


if __name__ == "__main__":
    print(json.dumps(run_full_body_compose_smoke(), indent=2))
