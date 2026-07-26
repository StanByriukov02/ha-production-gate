"""W₀ corpus-grounded physics stages — formulas before numbers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dogfood_platform.corpus_params import (
    AF_FORMULA,
    DVTH_NMP,
    GAMMA,
    GUARDBAND_REF_CLASS_MV,
    GUARDBAND_REF_MV,
    G_HCI_QUAL,
    N_EXP,
    NBTI_POWER_LAW_GAMMA,
    NBTI_POWER_LAW_N,
    SP_FORMULA,
    T_NOMINAL_K,
    W0_NOMINAL_T_K,
    W0_GUARDBAND_OP,
    W0_GUARDBAND_OP_MV,
)
from dogfood_platform.bti_calibration import compute_delta_vth_cited_anchor
from dogfood_platform.nmp_kinetics import integrate_nmp, integrate_nmp_v2_operating, load_traps
from dogfood_platform.fidelity import RegionTag
from dogfood_platform.scheduler import StageSpec

_REPO = Path(__file__).resolve().parents[1]
_BASELINE_WORKLOAD = _REPO / "results" / "platform_bpass" / "w0_workload_baseline_v1.json"
_SCENARIO_WORKLOAD = (
    _REPO / "results" / "platform_bpass" / "w0_workload_scenario_structure_demo_v1.json"
)
_BOUND_TRACE_WORKLOAD = (
    _REPO / "results" / "platform_bpass" / "w0_workload_lc2_trace_sim_v1.json"
)
_BOUND_WORKLOAD = (
    _REPO / "results" / "platform_bpass" / "w0_workload_lc2_foc_bound_v1.json"
)


def _missing(*keys: str) -> dict[str, Any]:
    return {"missing": list(keys)}


def _cite_bundle(*refs) -> list[dict[str, str]]:
    return [
        {"slug": r.slug, "formula_id": r.formula_id, "oracle": r.oracle, "claim": r.claim}
        for r in refs
    ]


def compute_sp_af(workload: dict[str, Any]) -> dict[str, Any]:
    """mod04 E1–E2: SP from duty-on; AF from transitions / (2·f·τ)."""
    duty_on = workload.get("duty_on")
    n_cycles = workload.get("n_cycles")
    f_clock_hz = workload.get("f_clock_hz")
    transitions_per_cycle = workload.get("transitions_per_cycle")
    v_gs_on_v = workload.get("v_gs_on_v")
    v_th_v = workload.get("v_th_v")

    out: dict[str, Any] = {
        "stage": "SP_AF_symbolic",
        "cites": _cite_bundle(SP_FORMULA, AF_FORMULA),
        "formulas": {
            "SP_i": "lim (1/τ)∫ Θ(V_i(t)-V_th) dt → duty_on when V_gs_on > V_th",
            "AF_i": "N_transitions / (2·f_clock·τ)",
        },
    }

    missing: list[str] = []
    if duty_on is None:
        missing.append("duty_on")
    if n_cycles is None:
        missing.append("n_cycles")
    if f_clock_hz is None:
        missing.append("f_clock_hz")
    if transitions_per_cycle is None:
        missing.append("transitions_per_cycle")
    if v_gs_on_v is None:
        missing.append("v_gs_on_v")
    if v_th_v is None:
        missing.append("v_th_v")

    if missing:
        out.update(_missing(*missing))
        out["oracle"] = "INPUT_MISSING"
        out["sp_i"] = None
        out["af_i"] = None
        return out

    duty = float(duty_on)
    vgs = float(v_gs_on_v)
    vth = float(v_th_v)
    n = float(n_cycles)
    f_hz = float(f_clock_hz)
    n_trans_per = float(transitions_per_cycle)

    if f_hz <= 0 or n <= 0:
        out["oracle"] = "INPUT_INVALID"
        out["error"] = "f_clock_hz and n_cycles must be > 0"
        return out

    # Constant V_gs above V_th during ON fraction → SP ≈ duty_on (mod04 L0 Stage 1)
    sp_i = duty if vgs > vth else 0.0
    tau_s = n / f_hz
    n_transitions = n * n_trans_per
    af_i = n_transitions / (2.0 * f_hz * tau_s)

    out.update(
        {
            "oracle": workload.get("oracle", "PROXY_STRUCTURE"),
            "sp_i": round(sp_i, 6),
            "af_i": round(af_i, 6),
            "tau_s": tau_s,
            "n_transitions": n_transitions,
            "trace_slice": workload.get("trace_slice"),
        }
    )
    return out


def compute_bti_structure(workload: dict[str, Any], spaf: dict[str, Any]) -> dict[str, Any]:
    """D4 N_G structure + mod04 E3 path — no ΔVth mV without Grasser cal."""
    v_gs_v = workload.get("v_gs_on_v")
    n_cycles = workload.get("n_cycles")
    f_clock_hz = workload.get("f_clock_hz")
    temperature_k = workload.get("temperature_k", T_NOMINAL_K)
    guardband_mv = workload.get("guardband_delta_vth_mv")
    guardband_regime = workload.get("guardband_regime", "G_W0_op")

    out: dict[str, Any] = {
        "stage": "NMP_BTI_model",
        "cites": _cite_bundle(NBTI_POWER_LAW_N, NBTI_POWER_LAW_GAMMA, DVTH_NMP, W0_NOMINAL_T_K),
        "formulas": {
            "N_G": "A·V_G^γ·exp(-E_a/k_BT)·t^n",
            "n": N_EXP,
            "gamma": GAMMA,
            "delta_vth_full": "ΔV_th = ΔV_0 Σ P_occ,j(t) — NMP (PARK numeric)",
        },
        "missing_calibration": ["A", "E_a", "N_G_to_delta_vth_mv"],
    }

    if spaf.get("oracle") == "INPUT_MISSING":
        out["oracle"] = "BLOCKED_UPSTREAM"
        out["delta_vth_mv"] = None
        out["pass"] = None
        out["pass_status"] = "UNDETERMINED"
        return out

    missing: list[str] = []
    if v_gs_v is None:
        missing.append("v_gs_on_v")
    if n_cycles is None:
        missing.append("n_cycles")
    if f_clock_hz is None:
        missing.append("f_clock_hz")
    if missing:
        out.update(_missing(*missing))
        out["oracle"] = "INPUT_MISSING"
        out["delta_vth_mv"] = None
        out["pass"] = None
        out["pass_status"] = "UNDETERMINED"
        return out

    t_s = float(n_cycles) / float(f_clock_hz)
    v_g = float(v_gs_v)
    # Dimensionless stress index from cited exponents only — not ΔVth mV
    stress_index = (v_g**GAMMA) * (t_s**N_EXP)

    out.update(
        {
            "oracle": "PROXY_STRUCTURE",
            "stress_index_NG_structure": stress_index,
            "t_stress_s": t_s,
            "temperature_k": float(temperature_k),
            "delta_vth_mv": None,
            "guardband_delta_vth_mv": guardband_mv,
            "guardband_regime": guardband_regime,
            "guardband_ref_hci_mv": workload.get("guardband_ref_hci_mv", GUARDBAND_REF_MV),
            "guardband_ref_hci_cite": _cite_bundle(G_HCI_QUAL),
            "guardband_ref_class_mv": GUARDBAND_REF_MV,
            "guardband_ref_cite": _cite_bundle(GUARDBAND_REF_CLASS_MV),
            "guardband_ref_note": (
                "G_W0_op bound T4 — primary operating line; G_HCI 50 mV = qual ref class only"
            ),
        }
    )

    sp_i = spaf.get("sp_i")
    cal_id = workload.get("calibration_id")
    if cal_id == "hci_d4_power_scale_v1":
        cal = compute_delta_vth_cited_anchor(
            v_gs_v=v_g,
            t_stress_s=t_s,
            sp_i=sp_i,
            workload=workload,
        )
        out["calibration"] = cal
        if cal.get("delta_vth_mv") is not None:
            out["delta_vth_mv"] = cal["delta_vth_mv"]
            out["oracle"] = cal.get("oracle", "CITED_ANCHOR_SCALE")
    elif cal_id in ("nmp_ode_ladder_v1", "nmp_ode_ladder_v2"):
        try:
            from dogfood_platform.nmp_kinetics import _PARAMS_PATH, _PARAMS_PATH_V2

            params = _PARAMS_PATH_V2 if cal_id == "nmp_ode_ladder_v2" else _PARAMS_PATH
            traps = load_traps(params)
            if cal_id == "nmp_ode_ladder_v2":
                nmp = integrate_nmp_v2_operating(t_stress_s=t_s, v_gs_v=v_g, sp_i=sp_i, traps=traps)
            else:
                nmp = integrate_nmp(t_stress_s=t_s, v_gs_v=v_g, sp_i=sp_i, traps=traps)
            out["nmp"] = nmp
            if nmp.get("delta_vth_mv") is not None:
                out["delta_vth_mv"] = nmp["delta_vth_mv"]
                out["oracle"] = nmp.get("oracle", "NMP_ODE_LADDER")
        except FileNotFoundError:
            out["nmp"] = {
                "oracle": "BLOCKED",
                "reason": f"{cal_id} params missing — run mod04_nmp_run_v1.py init-v2",
            }

    if guardband_mv is not None and out["delta_vth_mv"] is not None:
        out["pass"] = out["delta_vth_mv"] < float(guardband_mv)
        out["pass_status"] = "PASS" if out["pass"] else "FAIL"
    else:
        out["pass"] = None
        out["pass_status"] = "UNDETERMINED"

    return out


def stage_workload_to_spaf(inputs: dict[str, Any]) -> dict[str, Any]:
    """Stage A: workload → SP/AF (statistical region)."""
    merged = {**inputs}
    spaf = compute_sp_af(merged)
    return {**merged, **spaf}


def stage_spaf_to_bti(inputs: dict[str, Any]) -> dict[str, Any]:
    """Stage B: SP/AF → BTI structure (semiclassical region)."""
    spaf_keys = ("sp_i", "af_i", "stage", "cites", "formulas", "oracle", "tau_s")
    spaf = {k: inputs[k] for k in spaf_keys if k in inputs}
    bti = compute_bti_structure(inputs, spaf)
    return {**inputs, **bti}


def w0_corpus_stage_specs() -> list[StageSpec]:
    return [
        StageSpec(
            stage_id="w0-stage-a-workload-spaf",
            hop_id="w0-h1-workload-to-stress",
            from_stage="riscv_block_workload",
            to_stage="SP_AF_symbolic",
            region_tag=RegionTag.STATISTICAL,
            run=stage_workload_to_spaf,
        ),
        StageSpec(
            stage_id="w0-stage-b-spaf-bti",
            hop_id="w0-h2-stress-to-bti",
            from_stage="SP_AF_symbolic",
            to_stage="NMP_BTI_model",
            region_tag=RegionTag.SEMICLASSICAL,
            run=stage_spaf_to_bti,
        ),
    ]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def w0_default_workload(
    *, scenario: bool = False, bound: bool = False, trace: bool = False
) -> dict[str, Any]:
    """Baseline — null physics inputs until trace/STA binds (mod04 Q1)."""
    if trace and _BOUND_TRACE_WORKLOAD.is_file():
        path = _BOUND_TRACE_WORKLOAD
    elif bound and _BOUND_WORKLOAD.is_file():
        path = _BOUND_WORKLOAD
    elif scenario:
        path = _SCENARIO_WORKLOAD
    else:
        path = _BASELINE_WORKLOAD
    if path.is_file():
        data = _load_json(path)
        data["_loaded_from"] = str(path.relative_to(_REPO)).replace("\\", "/")
        return data
    return {
        "workload_id": "hot_block_riscv_nominal",
        "oracle": "INPUT_MISSING",
        "cite": "MD2_MATH_KERNEL_MOD04_WEAR_L0_V1 Q1 — one RISC-V block trace slice",
    }


# Back-compat aliases for CLI imports
w0_mock_stage_specs = w0_corpus_stage_specs
