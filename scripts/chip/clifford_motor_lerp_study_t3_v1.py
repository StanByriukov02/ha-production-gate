"""T3 — Motor Lerp study receipt runner."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_RECEIPT = _CHIP / "CHIP_CLIFFORD_MOTOR_LERP_STUDY_RECEIPT_v1.json"
_BIND = _CHIP / "CHIP_CLIFFORD_MOTOR_LERP_STUDY_BIND_v1.json"
_T1 = _CHIP / "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1.json"
_T2 = _CHIP / "CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1.json"
_SCOPE_DOC = _REPO / "docs/agent_workflow/CLIFFORD_MOTOR_LERP_SCOPE_v1.md"
_FIX = _REPO / "fixtures" / "chip"

_CANON = (
    "docs/agent_workflow/CLIFFORD_DEPTH_PLAN_V1.md",
    "docs/agent_workflow/CLIFFORD_MOTOR_LERP_SCOPE_v1.md",
    "scripts/chip/clifford_motor_lerp_study_t3_v1.py",
)


def run_clifford_motor_lerp_study_t3(*, write: bool = True) -> dict[str, Any]:
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))

    from scripts.chip.clifford_motor_lerp_v1 import CANDIDATES, build_study_doc

    t1_ok = _T1.is_file() and json.loads(_T1.read_text(encoding="utf-8")).get("verdict") == "T1_PASS"
    t2_ok = _T2.is_file() and json.loads(_T2.read_text(encoding="utf-8")).get("verdict") == "OPT_BASELINE_PASS"

    study = build_study_doc()
    max_err = {
        cid: max(s["max_angular_err_rad"][cid] for s in study["scopes"].values())
        for cid in CANDIDATES
    }

    checks: list[dict[str, Any]] = []

    def chk(cid: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    chk("t1_t2_prerequisite", t1_ok and t2_ok)
    chk("scope_doc_present", _SCOPE_DOC.is_file())
    chk("three_candidates", len(CANDIDATES) == 3)
    chk("gold_reference_quat_slerp", study["gold_reference"] == "quat_slerp_trans")
    chk("four_scopes", len(study["scopes"]) >= 4)
    chk("bench_stress_scope", "bench_cross_axis_stress" in study["scopes"])

    coeff_max = max_err["coeff_lerp_norm"]
    screw_max = max_err["screw_linear_norm"]
    slerp_max = max_err["quat_slerp_trans"]
    stress_err = study["scopes"]["bench_cross_axis_stress"]["max_angular_err_rad"]["coeff_lerp_norm"]

    chk("slerp_self_gold_zero", slerp_max < 1e-6, detail=f"{slerp_max:.2e}")
    chk("coeff_not_gold_lc2", study["scopes"]["lc2_bench_hip"]["max_angular_err_rad"]["coeff_lerp_norm"] > 0.001)
    chk("coeff_stress_geodesic_fail", stress_err > 0.03, detail=f"{stress_err:.4f}")
    chk(
        "screw_same_as_coeff_on_rotor",
        abs(screw_max - coeff_max) < 1e-6,
        detail="even-lane nlerp ≡ coeff on pure rotor scopes",
    )

    scope_split = study["honesty"]["scope_split"]
    promote = study["verdict_hint"] == "PROMOTE_OPCODE"
    verdict = "T3_PASS" if all(c["pass"] for c in checks) else "T3_FAIL"
    isa_verdict = study["verdict_hint"] if verdict == "T3_PASS" else "BLOCKED"

    receipt: dict[str, Any] = {
        "receipt_id": "CHIP_CLIFFORD_MOTOR_LERP_STUDY_RECEIPT_v1",
        "bind_id": "CHIP_CLIFFORD_MOTOR_LERP_STUDY_BIND_v1",
        "verdict": verdict,
        "isa_verdict": isa_verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canon": list(_CANON),
        "sprint_track": "T3",
        "checks": checks,
        "study": study,
        "max_angular_err_rad": max_err,
        "t1_bind": "CHIP_CLIFFORD_CAYLEY_GOLD_T1_RECEIPT_v1",
        "t2_bind": "CHIP_CLIFFORD_RTL_OPTIMIZE_RECEIPT_v1",
        "dual_physics_pair": "pair_composer25_opus48",
        "agent_dirs": {
            "algebra": "agents/clifford-algebra-phys/instructions.md",
            "iron": "agents/clifford-iron-reliability/instructions.md",
        },
        "honesty": {
            "nl_geodesic": study["honesty"]["nl_geodesic"],
            "scope_split": scope_split,
            "falsifier": study["honesty"]["falsifier"],
            "timing_closure": False,
            "null_plane_pga": "PARK_P2.1",
            "triple_layer": study["triple_layer"],
            "promote_opcode": promote,
        },
    }

    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        _BIND.write_text(
            json.dumps(
                {
                    "bind_id": receipt["bind_id"],
                    "receipt_id": receipt["receipt_id"],
                    "verdict": verdict,
                    "isa_verdict": isa_verdict,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        fixture = _FIX / "clifford_motor_lerp_study_v1.json"
        fixture.write_text(json.dumps(study, indent=2), encoding="utf-8")

    return receipt


if __name__ == "__main__":
    print(json.dumps(run_clifford_motor_lerp_study_t3(write=True), indent=2))
