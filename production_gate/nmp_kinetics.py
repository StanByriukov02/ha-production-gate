"""NMP BTI kinetics — ODE structure (mod04 E3–E4).

Full Grasser CET map: PARK until PDF ingest.
This module: log-spaced trap ladder + rate equations, calibrated to HCI anchor.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from production_gate.corpus_params import (
    DVTH_NMP,
    GOES_LOGNORMAL_TAU,
    GOES_NMP_SUPERPOSITION,
    GOES_TDDS_TAU_RANGE,
    GOES_FOX_STRESS_SCALE,
    GOES_STRESS_N,
    GOES_STRESS_POWER_N,
    GOES_STRESS_TS0_S,
    GOES_TRAP_DEPTH_DVTH,
    HCI_ANCHOR_DVTH_MV,
    HCI_ANCHOR_T_S,
    HCI_ANCHOR_VGS_V,
    HCI_DVTH_ANCHOR,
)

_REPO = Path(__file__).resolve().parents[1]
_PARAMS_PATH = _REPO / "results" / "platform_bpass" / "nmp_trap_ladder_v1.json"
_PARAMS_PATH_V2 = _REPO / "results" / "platform_bpass" / "nmp_trap_ladder_v2.json"
_PARAMS_PATH_V3 = _REPO / "results" / "platform_bpass" / "nmp_trap_ladder_v3_fab_bind.json"

# PROXY: fab interface disorder scales shallow NMP traps more (Goes shallow-trap class)
_FAB_DISORDER_K = 0.15
_TRAP_SCALE_MIN = 0.25
_TRAP_SCALE_MAX = 2.5

# TDDS Fig 1.1 emission map span (Goes 2011) — extended to 1e4 s for mission-class stress
_TDDS_TAU_MIN_S = 1e-5
_TDDS_TAU_MAX_S = 1e4
# Log-normal g(τ) discretization (eq 4.5) — μ at 1 s, σ≈2 decades (defect dispersion class)
_LN_MU = 0.0
_LN_SIGMA = 2.0
# NMP stress capture-dominated: τcap ≪ τem (Goes §4.1) — emission 100× slower at reference
_TAU_EM_RATIO = 100.0


@dataclass(frozen=True)
class TrapState:
    trap_id: int
    tau_c_s: float
    tau_e_s: float
    delta_v0_mv: float


def _g_lognormal_tau(tau_s: float, *, mu: float = _LN_MU, sigma: float = _LN_SIGMA) -> float:
    """Discrete bin weight from Goes eq. 4.5 log-normal g(τ)."""
    if tau_s <= 0 or sigma <= 0:
        return 0.0
    x = math.log(tau_s)
    return (1.0 / (tau_s * sigma * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def tdds_trap_ladder_v2(*, n_traps: int = 12) -> list[TrapState]:
    """TDDS-grounded ladder: g(τ) weights + trap-depth ΔV0 taper (Goes eq. 4.3–4.5, 3.25)."""
    if n_traps < 3:
        n_traps = 3
    log_min, log_max = math.log10(_TDDS_TAU_MIN_S), math.log10(_TDDS_TAU_MAX_S)
    d_log = (log_max - log_min) / (n_traps - 1)
    raw_weights: list[float] = []
    traps: list[TrapState] = []
    for i in range(n_traps):
        frac = i / (n_traps - 1)
        tau_c = 10 ** (log_min + frac * (log_max - log_min))
        tau_e = tau_c * _TAU_EM_RATIO
        # bin integral of g(τ) over Δlog10(τ)
        w = _g_lognormal_tau(tau_c) * d_log * math.log(10.0)
        # shallow / fast traps → larger per-trap ΔVth step (WKB / eq 3.25 class)
        depth_scale = (_TDDS_TAU_MIN_S / tau_c) ** 0.25
        raw_weights.append(max(w * depth_scale, 1e-30))
        traps.append(TrapState(trap_id=i, tau_c_s=tau_c, tau_e_s=tau_e, delta_v0_mv=0.0))
    w_sum = sum(raw_weights)
    return [
        TrapState(tr.trap_id, tr.tau_c_s, tr.tau_e_s, round(rw / w_sum, 6))
        for tr, rw in zip(traps, raw_weights)
    ]


def default_trap_ladder(*, n_traps: int = 8) -> list[TrapState]:
    """Log-spaced τ_c ladder — structure from Grasser MSM / TDMR log distribution class."""
    tau_min, tau_max = 1e-3, 1e4
    if n_traps < 2:
        n_traps = 2
    log_min, log_max = math.log10(tau_min), math.log10(tau_max)
    traps: list[TrapState] = []
    for i in range(n_traps):
        frac = i / (n_traps - 1)
        tau_c = 10 ** (log_min + frac * (log_max - log_min))
        tau_e = tau_c * 10.0  # emission slower — illustrative ratio; PARK full TDDS map
        traps.append(TrapState(trap_id=i, tau_c_s=tau_c, tau_e_s=tau_e, delta_v0_mv=0.0))
    return traps


def _p_occ(t_s: float, tau_c: float, tau_e: float) -> float:
    kc, ke = 1.0 / tau_c, 1.0 / tau_e
    k = kc + ke
    if k <= 0 or t_s <= 0:
        return 0.0
    return (kc / k) * (1.0 - math.exp(-k * t_s))


def integrate_nmp(
    *,
    t_stress_s: float,
    v_gs_v: float,
    sp_i: float | None,
    traps: list[TrapState],
    calibration_id: str = "nmp_ode_ladder_v1",
) -> dict[str, Any]:
    """Sum ΔV0_j P_j(t) — mod04 E3."""
    if t_stress_s <= 0:
        return {"oracle": "INPUT_INVALID", "delta_vth_mv": None}

    # Bias scales capture: higher Vgs → faster capture (ADAPT from md2: τ_c(V_gs))
    v_scale = (v_gs_v / HCI_ANCHOR_VGS_V) ** 2.0 if HCI_ANCHOR_VGS_V > 0 else 1.0
    sp = float(sp_i) if sp_i is not None else 1.0
    t_eff = t_stress_s * sp

    per_trap: list[dict[str, Any]] = []
    total_mv = 0.0
    for tr in traps:
        tau_c = tr.tau_c_s / max(v_scale, 1e-9)
        p = _p_occ(t_eff, tau_c, tr.tau_e_s)
        dv = tr.delta_v0_mv * p
        total_mv += dv
        per_trap.append(
            {
                "trap_id": tr.trap_id,
                "tau_c_s": tau_c,
                "tau_e_s": tr.tau_e_s,
                "delta_v0_mv": tr.delta_v0_mv,
                "p_occ": round(p, 6),
                "delta_vth_contrib_mv": round(dv, 6),
            }
        )

    cites: list[dict[str, str]] = [
        {"source_slug": DVTH_NMP.slug, "formula_id": DVTH_NMP.formula_id, "oracle": DVTH_NMP.oracle},
        {"source_slug": HCI_DVTH_ANCHOR.slug, "formula_id": HCI_DVTH_ANCHOR.formula_id, "oracle": "CALIBRATION_ANCHOR"},
    ]
    if calibration_id.endswith("v2"):
        cites.extend(
            [
                {"source_slug": GOES_NMP_SUPERPOSITION.slug, "formula_id": GOES_NMP_SUPERPOSITION.formula_id, "oracle": GOES_NMP_SUPERPOSITION.oracle},
                {"source_slug": GOES_LOGNORMAL_TAU.slug, "formula_id": GOES_LOGNORMAL_TAU.formula_id, "oracle": GOES_LOGNORMAL_TAU.oracle},
                {"source_slug": GOES_TDDS_TAU_RANGE.slug, "formula_id": GOES_TDDS_TAU_RANGE.formula_id, "oracle": GOES_TDDS_TAU_RANGE.oracle},
                {"source_slug": GOES_TRAP_DEPTH_DVTH.slug, "formula_id": GOES_TRAP_DEPTH_DVTH.formula_id, "oracle": GOES_TRAP_DEPTH_DVTH.oracle},
            ]
        )

    return {
        "oracle": "NMP_ODE_LADDER",
        "calibration_id": calibration_id,
        "formula": "ΔVth = Σ_j ΔV0_j P_j(t); dP/dt = (1-P)/τ_c − P/τ_e",
        "cites": cites,
        "t_stress_s": t_stress_s,
        "t_eff_s": t_eff,
        "v_gs_v": v_gs_v,
        "sp_i": sp_i,
        "delta_vth_mv": round(total_mv, 4),
        "traps": per_trap,
        "full_grasser_park": None if calibration_id.endswith("v2") else "CET/TDDS defect map — ingest Grasser/Goes PDF for trap energies",
    }


def goes_fox_scale_vgs(v_gs_v: float, *, v_anchor_v: float = HCI_ANCHOR_VGS_V) -> float:
    """Goes eq 1.4 class: s proportional to Fox^2; Fox ~ Vgs (Fig 4.11 linear phi_s)."""
    if v_anchor_v <= 0:
        return 1.0
    return (v_gs_v / v_anchor_v) ** 2.0


def goes_time_stress_factor(t_stress_s: float, *, t_anchor_s: float = HCI_ANCHOR_T_S) -> float:
    """Goes eq 1.7 long-stress power n~0.11 (relative to anchor mission time)."""
    if t_stress_s <= 0 or t_anchor_s <= 0:
        return 1.0
    if t_stress_s <= GOES_STRESS_TS0_S and t_anchor_s <= GOES_STRESS_TS0_S:
        return t_stress_s / t_anchor_s
    base = max(t_anchor_s, GOES_STRESS_TS0_S)
    t_use = max(t_stress_s, GOES_STRESS_TS0_S)
    return (t_use / base) ** GOES_STRESS_N


def goes_phenom_bridge_delta_mv(
    anchor_delta_mv: float,
    *,
    v_gs_v: float,
    t_stress_s: float,
    sp_i: float | None,
    v_anchor_v: float = HCI_ANCHOR_VGS_V,
    t_anchor_s: float = HCI_ANCHOR_T_S,
) -> dict[str, Any]:
    """Off-anchor operating prediction within Goes/NBTI family (eq 1.3-1.4 + duty)."""
    fox = goes_fox_scale_vgs(v_gs_v, v_anchor_v=v_anchor_v)
    sp = float(sp_i) if sp_i is not None else 1.0
    t_fac = goes_time_stress_factor(t_stress_s, t_anchor_s=t_anchor_s)
    delta = anchor_delta_mv * fox * sp * t_fac
    return {
        "oracle": "GOES_PHENOM_BRIDGE",
        "calibration_id": "goes_eq_1_3_1_4_bridge",
        "delta_vth_mv": round(delta, 4),
        "formula": "ΔVth = ΔVth_anchor · (Fox_op/Fox_ref)^2 · SP · (t/t_ref)^n",
        "cites": [
            {"source_slug": GOES_FOX_STRESS_SCALE.slug, "formula_id": GOES_FOX_STRESS_SCALE.formula_id, "oracle": GOES_FOX_STRESS_SCALE.oracle},
            {"source_slug": GOES_STRESS_POWER_N.slug, "formula_id": GOES_STRESS_POWER_N.formula_id, "oracle": GOES_STRESS_POWER_N.oracle},
        ],
        "factors": {"fox_scale": round(fox, 6), "sp_i": sp, "t_stress_factor": round(t_fac, 6)},
        "inputs": {"v_gs_v": v_gs_v, "t_stress_s": t_stress_s, "anchor_delta_mv": anchor_delta_mv},
    }


def integrate_nmp_v2_operating(
    *,
    t_stress_s: float,
    v_gs_v: float,
    sp_i: float | None,
    traps: list[TrapState],
) -> dict[str, Any]:
    """v2: kinetic at anchor; Goes phenomenological bridge off-anchor (ON corpus)."""
    anchor = integrate_nmp(
        t_stress_s=HCI_ANCHOR_T_S,
        v_gs_v=HCI_ANCHOR_VGS_V,
        sp_i=1.0,
        traps=traps,
        calibration_id="nmp_ode_ladder_v2",
    )
    kinetic = integrate_nmp(
        t_stress_s=t_stress_s,
        v_gs_v=v_gs_v,
        sp_i=sp_i,
        traps=traps,
        calibration_id="nmp_ode_ladder_v2",
    )
    at_anchor = abs(v_gs_v - HCI_ANCHOR_VGS_V) < 1e-6 and abs(t_stress_s - HCI_ANCHOR_T_S) < 1e-6 and (sp_i is None or abs(float(sp_i) - 1.0) < 1e-6)
    if at_anchor:
        out = dict(kinetic)
        out["mode"] = "matched_anchor_kinetic"
        return out
    bridge = goes_phenom_bridge_delta_mv(
        float(anchor["delta_vth_mv"]),
        v_gs_v=v_gs_v,
        t_stress_s=t_stress_s,
        sp_i=sp_i,
    )
    return {
        **kinetic,
        "mode": "goes_phenom_bridge",
        "delta_vth_mv": bridge["delta_vth_mv"],
        "kinetic_saturation_mv": kinetic["delta_vth_mv"],
        "goes_bridge": bridge,
        "note": "Kinetic ladder saturates at long t; operating uses Goes eq 1.3-1.4 from matched anchor",
    }


def calibrate_ladder_to_anchor(traps: list[TrapState], *, t_s: float = HCI_ANCHOR_T_S, v_gs_v: float = HCI_ANCHOR_VGS_V) -> list[TrapState]:
    """Scale ΔV0_j so ladder sum matches HCI anchor at reference stress (single-point cal)."""
    raw = integrate_nmp(t_stress_s=t_s, v_gs_v=v_gs_v, sp_i=1.0, traps=traps)
    raw_sum = sum(t["p_occ"] for t in raw["traps"])
    if raw_sum <= 0:
        return traps
    dv0_each = HCI_ANCHOR_DVTH_MV / raw_sum
    return [
        TrapState(tr.trap_id, tr.tau_c_s, tr.tau_e_s, round(dv0_each, 6))
        for tr in traps
    ]


def calibrate_ladder_v2_to_anchor(
    traps: list[TrapState],
    *,
    t_s: float = HCI_ANCHOR_T_S,
    v_gs_v: float = HCI_ANCHOR_VGS_V,
) -> list[TrapState]:
    """Scale non-uniform ΔV0_j so ladder sum matches HCI anchor at reference stress."""
    raw = integrate_nmp(t_stress_s=t_s, v_gs_v=v_gs_v, sp_i=1.0, traps=traps, calibration_id="nmp_ode_ladder_v2")
    raw_mv = float(raw["delta_vth_mv"])
    if raw_mv <= 0:
        return traps
    scale = HCI_ANCHOR_DVTH_MV / raw_mv
    return [
        TrapState(tr.trap_id, tr.tau_c_s, tr.tau_e_s, round(tr.delta_v0_mv * scale, 6))
        for tr in traps
    ]


def write_tdds_params_v2(path: Path | None = None) -> Path:
    target = path or _PARAMS_PATH_V2
    traps = calibrate_ladder_v2_to_anchor(tdds_trap_ladder_v2())
    payload = {
        "version": 2,
        "calibration_id": "nmp_ode_ladder_v2",
        "oracle": "NMP_ODE_LADDER",
        "model": {
            "superposition": "Goes eq 4.3 — ∫ ft·g(τcap,τem)",
            "g_tau": "log-normal eq 4.5",
            "tau_range_s": [_TDDS_TAU_MIN_S, _TDDS_TAU_MAX_S],
            "ln_mu": _LN_MU,
            "ln_sigma": _LN_SIGMA,
            "tau_em_ratio": _TAU_EM_RATIO,
            "delta_v0_taper": "shallow-trap (τ_min/τ_c)^0.25 per eq 3.25 class",
        },
        "anchor": {
            "source_slug": HCI_DVTH_ANCHOR.slug,
            "formula_id": HCI_DVTH_ANCHOR.formula_id,
            "delta_vth_mv": HCI_ANCHOR_DVTH_MV,
            "t_s": HCI_ANCHOR_T_S,
            "v_gs_v": HCI_ANCHOR_VGS_V,
            "note": "Non-uniform ΔV0_j from g(τ)·depth; anchor scale at HCI point only",
        },
        "cites": [
            GOES_NMP_SUPERPOSITION.slug,
            GOES_LOGNORMAL_TAU.slug,
            GOES_TDDS_TAU_RANGE.slug,
            GOES_TRAP_DEPTH_DVTH.slug,
        ],
        "n_traps": len(traps),
        "traps": [
            {
                "trap_id": t.trap_id,
                "tau_c_s": t.tau_c_s,
                "tau_e_s": t.tau_e_s,
                "delta_v0_mv": t.delta_v0_mv,
                "g_weight_norm": round(t.delta_v0_mv / HCI_ANCHOR_DVTH_MV, 6),
            }
            for t in traps
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def scale_traps_fab_disorder(
    traps: list[TrapState],
    *,
    delta_vth0_mv: float,
    ref_stdev_mv: float,
) -> list[TrapState]:
    """v3 PROXY: fab Vth0 spread → shallow-trap ΔV0_j scale (Grasser-class, not full CET)."""
    z = delta_vth0_mv / ref_stdev_mv if ref_stdev_mv > 0 else 0.0
    scaled: list[TrapState] = []
    for tr in traps:
        shallow = (_TDDS_TAU_MIN_S / max(tr.tau_c_s, _TDDS_TAU_MIN_S)) ** 0.25
        factor = 1.0 + _FAB_DISORDER_K * z * shallow
        factor = max(_TRAP_SCALE_MIN, min(_TRAP_SCALE_MAX, factor))
        scaled.append(
            TrapState(
                tr.trap_id,
                tr.tau_c_s,
                tr.tau_e_s,
                round(tr.delta_v0_mv * factor, 6),
            )
        )
    return scaled


def integrate_nmp_v3_fab_disorder(
    *,
    delta_vth0_mv: float,
    ref_stdev_mv: float,
    base_traps: list[TrapState],
    t_stress_s: float,
    v_gs_v: float,
    sp_i: float | None,
) -> dict[str, Any]:
    """Per-device NMP with fab-disorder-scaled trap ladder (nominal device → v2-equivalent traps)."""
    traps = scale_traps_fab_disorder(
        base_traps, delta_vth0_mv=delta_vth0_mv, ref_stdev_mv=ref_stdev_mv
    )
    out = integrate_nmp_v2_operating(t_stress_s=t_stress_s, v_gs_v=v_gs_v, sp_i=sp_i, traps=traps)
    out["calibration_id"] = "nmp_ode_ladder_v3_fab_bind"
    out["fab_disorder"] = {
        "delta_vth0_mv": round(delta_vth0_mv, 4),
        "ref_stdev_mv": ref_stdev_mv,
        "coupling_k": _FAB_DISORDER_K,
        "oracle": "PROXY_STRUCTURE",
        "note": "Shallow traps scale with fab spread — gate Grasser-class hop",
    }
    return out


def write_tdds_params_v3(path: Path | None = None) -> Path:
    """v3 params = v2 ladder + fab disorder bind metadata (same anchor)."""
    v2_path = _PARAMS_PATH_V2
    if not v2_path.is_file():
        write_tdds_params_v2(v2_path)
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    payload = {
        **v2,
        "version": 3,
        "calibration_id": "nmp_ode_ladder_v3_fab_bind",
        "fab_disorder_bind": {
            "coupling_k": _FAB_DISORDER_K,
            "shallow_exponent": 0.25,
            "scale_bounds": [_TRAP_SCALE_MIN, _TRAP_SCALE_MAX],
            "source": "EXP-M1-03 fab ensemble stdev",
            "oracle": "PROXY_STRUCTURE",
            "tabu": "not measured Grasser CET — structure hop only",
        },
        "parent": str(v2_path.relative_to(_REPO)).replace("\\", "/"),
    }
    target = path or _PARAMS_PATH_V3
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def write_default_params(path: Path | None = None) -> Path:
    target = path or _PARAMS_PATH
    traps = calibrate_ladder_to_anchor(default_trap_ladder())
    payload = {
        "version": 1,
        "calibration_id": "nmp_ode_ladder_v1",
        "oracle": "NMP_ODE_LADDER",
        "anchor": {
            "source_slug": HCI_DVTH_ANCHOR.slug,
            "formula_id": HCI_DVTH_ANCHOR.formula_id,
            "delta_vth_mv": HCI_ANCHOR_DVTH_MV,
            "t_s": HCI_ANCHOR_T_S,
            "v_gs_v": HCI_ANCHOR_VGS_V,
            "note": "Single-point scale of ΔV0_j — NOT full TDDS Grasser map",
        },
        "n_traps": len(traps),
        "traps": [
            {"trap_id": t.trap_id, "tau_c_s": t.tau_c_s, "tau_e_s": t.tau_e_s, "delta_v0_mv": t.delta_v0_mv}
            for t in traps
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_traps(path: Path | None = None) -> list[TrapState]:
    p = path or _PARAMS_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    return [
        TrapState(
            int(t["trap_id"]),
            float(t["tau_c_s"]),
            float(t["tau_e_s"]),
            float(t["delta_v0_mv"]),
        )
        for t in data["traps"]
    ]
