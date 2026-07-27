"""PHYSICS OS KERNEL v0 — runtime contracts above the proof ladder.

Hierarchy: kernel PASS before CITED/ENVELOPE/SCARCE/STRANGER primary work.
Not a new language — the half-OS truth regime for physics in HA.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "ha_physics_os_kernel_v1"
PROOF_TIER = "PHYSICS_OS_KERNEL"
KERNEL_VERSION = "v0"

FORBIDDEN_SOFT_MINT = ("MEASURED", "OTP", "CREME", "product_ready", "HIL_IRON_PASS")


def kernel_meta() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "kernel_version": KERNEL_VERSION,
        "hierarchy": "TOP",
        "sot": "docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md",
        "who": "ty+ya",
        "honesty": {
            "not_measured": True,
            "not_new_language": True,
            "half_os_truth_regime": True,
        },
    }


def inspect_soft_mint_claims(doc: dict[str, Any] | None) -> list[str]:
    """Return forbidden soft-mint claim strings found in a receipt-like dict."""
    if not isinstance(doc, dict):
        return []
    hits: list[str] = []
    blob = str(doc).upper()
    honesty = doc.get("honesty") if isinstance(doc.get("honesty"), dict) else {}
    # Explicit false claims
    if honesty.get("measured") is True or honesty.get("field_measured") is True:
        hits.append("honesty.measured=true")
    if honesty.get("otp") is True or honesty.get("otp_silicon") is True:
        hits.append("honesty.otp=true")
    if honesty.get("creme_fem") is True:
        hits.append("honesty.creme_fem=true")
    # Tier upgrade without IRON
    tier = str(doc.get("proof_tier") or honesty.get("proof_tier") or "")
    if tier in ("IRON", "MEASURED", "OTP") and bool(honesty.get("not_measured", True)):
        # claiming IRON tier while still not_measured is soft-mint theater
        if "not_measured" in honesty and honesty.get("not_measured") is True:
            hits.append(f"proof_tier={tier}_with_not_measured")
    for bad in FORBIDDEN_SOFT_MINT:
        # verdict/label claiming PASS on forbidden without honesty path
        if f"{bad}_PASS" in blob and bad in ("MEASURED", "OTP", "CREME"):
            if honesty.get("not_measured") is not False and honesty.get(f"not_{bad.lower()}") is not False:
                # allow if explicit not_* honesty; block naked PASS strings in teaching docs
                if honesty.get("not_measured") is True or honesty.get("not_creme_fem") is True:
                    continue
                hits.append(bad)
    return hits


def check_k0_dual_burns(*, spent_safe: float, spent_hostile: float, gate_pass_safe: bool, gate_pass_hostile: bool) -> dict[str, Any]:
    spent_ok = float(spent_hostile) > float(spent_safe)
    gate_ok = bool(gate_pass_safe) and (not bool(gate_pass_hostile))
    ok = spent_ok or gate_ok
    return {
        "id": "K0",
        "ok": ok,
        "detail": {
            "spent_safe": spent_safe,
            "spent_hostile": spent_hostile,
            "gate_pass_safe": gate_pass_safe,
            "gate_pass_hostile": gate_pass_hostile,
            "spent_ok": spent_ok,
            "gate_ok": gate_ok,
        },
        "error": None if ok else "dual_does_not_burn",
    }


def check_k1_gate_coherence(gate: dict[str, Any] | None) -> dict[str, Any]:
    g = gate if isinstance(gate, dict) else {}
    digit = str(g.get("digit_advise") or "").upper()
    physics_pass = bool(g.get("physics_pass"))
    allowed = bool(g.get("current_allowed"))
    expect = (digit == "ALLOW") and physics_pass
    ok = allowed == expect
    return {
        "id": "K1",
        "ok": ok,
        "detail": {"digit": digit, "physics_pass": physics_pass, "current_allowed": allowed, "expect": expect},
        "error": None if ok else "gate_coherence_broken",
    }


def check_k2_failure_modes_wired(gate: dict[str, Any] | None) -> dict[str, Any]:
    g = gate if isinstance(gate, dict) else {}
    inputs = g.get("inputs") if isinstance(g.get("inputs"), dict) else {}
    ok = "failure_modes_clear" in inputs
    return {
        "id": "K2",
        "ok": ok,
        "detail": {"inputs": inputs, "failure_modes": g.get("failure_modes")},
        "error": None if ok else "failure_modes_clear_not_on_gate",
    }


def check_k3_soft_not_otp(*, gate: dict[str, Any] | None, fuse: dict[str, Any] | None) -> dict[str, Any]:
    g = gate if isinstance(gate, dict) else {}
    f = fuse if isinstance(fuse, dict) else {}
    gh = g.get("honesty") if isinstance(g.get("honesty"), dict) else {}
    fh = f.get("honesty") if isinstance(f.get("honesty"), dict) else {}
    ok = (
        bool(gh.get("not_measured", True))
        and bool(gh.get("not_silicon_fuse", True) or gh.get("sim_slice", True))
        and (fh.get("not_otp_silicon") is True or fh.get("silicon_fuse_backend") == "c_file_efuse" or not f)
    )
    # Explicit OTP claim = fail
    if gh.get("otp") is True or fh.get("otp") is True:
        ok = False
    return {
        "id": "K3",
        "ok": ok,
        "detail": {"gate_honesty": gh, "fuse_honesty": fh},
        "error": None if ok else "otp_claim_or_missing_soft_honesty",
    }


def check_k4_tier_epsilon(doc: dict[str, Any] | None) -> dict[str, Any]:
    d = doc if isinstance(doc, dict) else {}
    h = d.get("honesty") if isinstance(d.get("honesty"), dict) else {}
    eps = h.get("epsilon") or d.get("epsilon") or []
    if isinstance(eps, str):
        eps = [eps]
    ok = bool(h.get("not_measured", True)) and len(list(eps)) >= 1
    return {
        "id": "K4",
        "ok": ok,
        "detail": {"epsilon": eps, "not_measured": h.get("not_measured")},
        "error": None if ok else "missing_epsilon_or_not_measured",
    }


def check_k5_no_soft_mint(doc: dict[str, Any] | None) -> dict[str, Any]:
    hits = inspect_soft_mint_claims(doc)
    ok = len(hits) == 0
    return {
        "id": "K5",
        "ok": ok,
        "detail": {"hits": hits},
        "error": None if ok else "soft_mint_claims_present",
    }


def evaluate_kernel_from_dual_runs(
    *,
    run_safe: dict[str, Any],
    run_hostile: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate K0–K5 from a Safe/Hostile run_project pair."""
    ec_s = run_safe.get("energy_claim") or {}
    ec_h = run_hostile.get("energy_claim") or {}
    gate_s = run_safe.get("physics_gate") or {}
    gate_h = run_hostile.get("physics_gate") or {}
    fuse_s = run_safe.get("silicon_fuse") or {}

    spent_s = float(ec_s.get("spent_joules") or ec_s.get("spent_actuation_j") or 0.0)
    spent_h = float(ec_h.get("spent_joules") or ec_h.get("spent_actuation_j") or 0.0)
    # Prefer residual inverse if spent equalized
    if abs(spent_h - spent_s) < 1e-12:
        spent_s = -float(ec_s.get("residual_joules") or 0.0)
        spent_h = -float(ec_h.get("residual_joules") or 0.0)

    checks = [
        check_k0_dual_burns(
            spent_safe=spent_s,
            spent_hostile=spent_h,
            gate_pass_safe=bool(gate_s.get("physics_pass")),
            gate_pass_hostile=bool(gate_h.get("physics_pass")),
        ),
        check_k1_gate_coherence(gate_s),
        check_k1_gate_coherence(gate_h),
        check_k2_failure_modes_wired(gate_h),
        check_k3_soft_not_otp(gate=gate_h, fuse=fuse_s),
        check_k4_tier_epsilon(gate_h),
        check_k5_no_soft_mint(gate_h),
        check_k5_no_soft_mint(ec_h),
    ]
    # Collapse duplicate K1 into one ok
    k1_ok = all(c["ok"] for c in checks if c["id"] == "K1")
    ordered = []
    seen_k1 = False
    for c in checks:
        if c["id"] == "K1":
            if seen_k1:
                continue
            seen_k1 = True
            ordered.append(
                {
                    "id": "K1",
                    "ok": k1_ok,
                    "detail": {"safe": checks[1]["detail"], "hostile": checks[2]["detail"]},
                    "error": None if k1_ok else "gate_coherence_broken",
                }
            )
        else:
            ordered.append(c)

    ok = all(bool(c.get("ok")) for c in ordered)
    return {
        **kernel_meta(),
        "ok": ok,
        "verdict": f"{PROOF_TIER}_PASS" if ok else f"{PROOF_TIER}_FAIL",
        "checks": ordered,
        "honesty": {
            "not_measured": True,
            "proof_tier": PROOF_TIER,
            "hierarchy_top": True,
            "epsilon": ["ε_desk_not_world", "ε_soft_not_otp", "ε_mode_set_incomplete"],
            "ladder_blocked_until_pass": True,
        },
    }


def seal_kernel_on_run(run_doc: dict[str, Any]) -> dict[str, Any]:
    """Seal Physics OS kernel onto a Dual run receipt — HA runtime, not Cursor.

    Every `run_project` must carry this. Single-run checks K1–K5.
    K0 Dual burn attaches when peer condition run is available on the project.
    """
    out = dict(run_doc)
    gate = out.get("physics_gate") if isinstance(out.get("physics_gate"), dict) else {}
    fuse = out.get("silicon_fuse") if isinstance(out.get("silicon_fuse"), dict) else {}
    energy = out.get("energy_claim") if isinstance(out.get("energy_claim"), dict) else {}
    closed = out.get("closed_loop_v1") if isinstance(out.get("closed_loop_v1"), dict) else {}

    checks = [
        check_k1_gate_coherence(gate),
        check_k2_failure_modes_wired(gate),
        check_k3_soft_not_otp(gate=gate, fuse=fuse),
        check_k4_tier_epsilon(gate),
        check_k5_no_soft_mint(gate),
        check_k5_no_soft_mint(energy),
        check_k5_no_soft_mint(out.get("honesty") if isinstance(out.get("honesty"), dict) else {}),
    ]
    # collapse duplicate K5
    k5_ok = all(c["ok"] for c in checks if c["id"] == "K5")
    ordered: list[dict[str, Any]] = []
    seen_k5 = False
    for c in checks:
        if c["id"] == "K5":
            if seen_k5:
                continue
            seen_k5 = True
            ordered.append(
                {
                    "id": "K5",
                    "ok": k5_ok,
                    "detail": {"note": "gate+energy+run honesty"},
                    "error": None if k5_ok else "soft_mint_claims_present",
                }
            )
        else:
            ordered.append(c)

    k0 = _try_k0_from_peer(out)
    if k0 is not None:
        ordered.insert(0, k0)

    ok = all(bool(c.get("ok")) for c in ordered)
    seal = {
        **kernel_meta(),
        "ok": ok,
        "verdict": f"{PROOF_TIER}_PASS" if ok else f"{PROOF_TIER}_FAIL",
        "checks": ordered,
        "sealed_in_ha_runtime": True,
        "not_cursor_enforcement": True,
        "condition": out.get("condition"),
        "honesty": {
            "not_measured": True,
            "proof_tier": PROOF_TIER,
            "hierarchy_top": True,
            "enforcement": "ha_runtime_run_project",
            "epsilon": ["ε_desk_not_world", "ε_soft_not_otp", "ε_mode_set_incomplete"],
        },
    }
    out["physics_os_kernel"] = seal

    # Surface on closed_loop thermometer (physics world, not IDE).
    cl = dict(closed)
    kpi = dict(cl.get("kpi") or {})
    honesty = dict(cl.get("honesty") or {})
    kpi["physics_os_kernel_ok"] = ok
    kpi["physics_os_kernel_version"] = KERNEL_VERSION
    honesty["physics_os_kernel_ok"] = ok
    honesty["physics_os_sealed_in_ha_runtime"] = True
    honesty["not_cursor_enforcement"] = True
    cl["kpi"] = kpi
    cl["honesty"] = honesty
    out["closed_loop_v1"] = cl

    rh = dict(out.get("honesty") or {})
    rh["physics_os_kernel_ok"] = ok
    rh["physics_os_sealed_in_ha_runtime"] = True
    out["honesty"] = rh

    # OS refuse bit: kernel FAIL means this run must not be treated as arm-ok.
    if not ok:
        gate2 = dict(gate)
        gate2["physics_os_kernel_refuse"] = True
        gate2["current_allowed_before_kernel"] = gate2.get("current_allowed")
        gate2["current_allowed"] = False
        out["physics_gate"] = gate2
        seal["os_refuse_current"] = True
        out["physics_os_kernel"] = seal
    return out


def _try_k0_from_peer(run_doc: dict[str, Any]) -> dict[str, Any] | None:
    """If peer Safe/Hostile run exists on project, attach K0 Dual burn check."""
    project_id = str(run_doc.get("project_id") or "")
    condition = str(run_doc.get("condition") or "")
    if not project_id or condition not in ("safe", "hostile"):
        return None
    peer_cond = "hostile" if condition == "safe" else "safe"
    try:
        from production_gate.robot_project_desk_v1 import get_project, project_dir
    except Exception:
        return None
    try:
        proj = get_project(project_id)
    except Exception:
        return None
    last = proj.get("last_run") if isinstance(proj.get("last_run"), dict) else {}
    # Prefer scanning runs dir for latest peer
    peer_doc = None
    try:
        runs = project_dir(project_id) / "runs"
        if runs.is_dir():
            cands = sorted(runs.glob("run-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for p in cands[:12]:
                import json

                d = json.loads(p.read_text(encoding="utf-8"))
                if str(d.get("condition") or "") == peer_cond:
                    peer_doc = d
                    break
    except Exception:
        peer_doc = None
    if peer_doc is None and str(last.get("condition") or "") == peer_cond:
        peer_doc = last
    if peer_doc is None:
        return {
            "id": "K0",
            "ok": True,
            "detail": {"peer": "pending", "note": "single-condition run; Dual burn when peer exists"},
            "error": None,
        }

    def _spent(doc: dict[str, Any]) -> float:
        ec = doc.get("energy_claim") if isinstance(doc.get("energy_claim"), dict) else {}
        for k in ("spent_joules", "spent_actuation_j", "spent_actuation_joules"):
            if ec.get(k) is not None:
                return float(ec[k])
        return -float(ec.get("residual_joules") or 0.0)

    if condition == "safe":
        spent_s, spent_h = _spent(run_doc), _spent(peer_doc)
        gate_s = (run_doc.get("physics_gate") or {}).get("physics_pass")
        gate_h = (peer_doc.get("physics_gate") or {}).get("physics_pass")
    else:
        spent_s, spent_h = _spent(peer_doc), _spent(run_doc)
        gate_s = (peer_doc.get("physics_gate") or {}).get("physics_pass")
        gate_h = (run_doc.get("physics_gate") or {}).get("physics_pass")
    return check_k0_dual_burns(
        spent_safe=spent_s,
        spent_hostile=spent_h,
        gate_pass_safe=bool(gate_s),
        gate_pass_hostile=bool(gate_h),
    )
