"""FAILURE_MODE_GATE — named mission killers refuse Dual current.

Proof tier: FAILURE_MODE_GATE (PROOF_TIER_LADDER_V1).
Not MEASURED · not full multibody · ε_mode_set_incomplete.

Modes (fatal → failure_modes_clear=false → Rust physics_pass false):
  FM_DRAWBAR_DEFICIT   drawbar < 25% of Dual Safe peer
  FM_STORM_DOSE        storm_env.storm_ok is false
  FM_TRAVERSE_JERK     traverse_mechanical.traverse_ok is false
  FM_DUST_INGRESS      dust_ingress.ingress_ok is false when present
  FM_DUST_SEAL_OPEN    dust seal class B5 (open joint) — Benaroya open
  FM_TIP_SLOPE         Mohr slope_stable false / tip risk on Hostile slope
  FM_ENVELOPE_OUTSIDE  radiation envelope_refuse outside published band
  FM_EARTH_BEARING     earth_lane bearing_margin / traverse refuse (Earth globe)
  FM_EARTH_WIND        earth_lane wind_risk >= 2 (Earth globe)
  FM_SINKAGE_RISK      physics.sinkage_risk already true
  FM_TRAVERSE_BLOCKED  physics.traverse_feasible already false
"""
from __future__ import annotations

from typing import Any

DRAWBAR_DEFICIT_FRAC = 0.25
OPEN_SEAL_CLASS = "B5"
PROOF_TIER = "FAILURE_MODE_GATE"


def evaluate_failure_modes(physics: dict[str, Any] | None) -> dict[str, Any]:
    ph = physics if isinstance(physics, dict) else {}
    modes: list[dict[str, Any]] = []

    if not bool(ph.get("traverse_feasible", True)):
        modes.append(
            {
                "id": "FM_TRAVERSE_BLOCKED",
                "fatal": True,
                "detail": {"traverse_feasible": False},
            }
        )
    if bool(ph.get("sinkage_risk")):
        modes.append(
            {
                "id": "FM_SINKAGE_RISK",
                "fatal": True,
                "detail": {"sinkage_risk": True},
            }
        )

    dual = ph.get("bekker_dual") if isinstance(ph.get("bekker_dual"), dict) else {}
    h = ph.get("drawbar_pull_n")
    h_safe = dual.get("drawbar_safe_n")
    if h is not None and h_safe is not None and float(h_safe) > 1e-9:
        ratio = float(h) / float(h_safe)
        if ratio < DRAWBAR_DEFICIT_FRAC:
            modes.append(
                {
                    "id": "FM_DRAWBAR_DEFICIT",
                    "fatal": True,
                    "detail": {
                        "drawbar_n": float(h),
                        "drawbar_safe_n": float(h_safe),
                        "ratio": ratio,
                        "threshold": DRAWBAR_DEFICIT_FRAC,
                    },
                }
            )

    storm = ph.get("storm_env") if isinstance(ph.get("storm_env"), dict) else None
    if isinstance(storm, dict) and storm.get("storm_ok") is False:
        modes.append(
            {
                "id": "FM_STORM_DOSE",
                "fatal": True,
                "detail": {
                    "storm_id": storm.get("storm_id"),
                    "dose_gy_final": storm.get("dose_gy_final"),
                },
            }
        )

    trav = (
        ph.get("traverse_mechanical")
        if isinstance(ph.get("traverse_mechanical"), dict)
        else None
    )
    if isinstance(trav, dict) and trav.get("traverse_ok") is False:
        modes.append(
            {
                "id": "FM_TRAVERSE_JERK",
                "fatal": True,
                "detail": {
                    "mlcc_jerk_peak": trav.get("mlcc_jerk_peak"),
                    "soil_id": trav.get("soil_id"),
                },
            }
        )

    ingress = ph.get("dust_ingress") if isinstance(ph.get("dust_ingress"), dict) else None
    if isinstance(ingress, dict) and ingress.get("ingress_ok") is False:
        modes.append(
            {
                "id": "FM_DUST_INGRESS",
                "fatal": True,
                "detail": {
                    "rate": ingress.get("ingress_rate") or ingress.get("rate"),
                },
            }
        )
    if isinstance(ingress, dict):
        seal = str(ingress.get("seal_class") or "")
        if seal == OPEN_SEAL_CLASS:
            modes.append(
                {
                    "id": "FM_DUST_SEAL_OPEN",
                    "fatal": True,
                    "detail": {
                        "seal_class": seal,
                        "zone": ingress.get("zone"),
                        "note": "open joint seal B5 — Benaroya open class",
                    },
                }
            )

    slope = ph.get("slope_rut") if isinstance(ph.get("slope_rut"), dict) else None
    tip_risk = False
    if isinstance(slope, dict):
        tip_risk = (not bool(slope.get("slope_stable", True))) or (
            slope.get("slope_ok") is False
        )
    elif ph.get("slope_stable") is False:
        tip_risk = True
    if tip_risk:
        modes.append(
            {
                "id": "FM_TIP_SLOPE",
                "fatal": True,
                "detail": {
                    "theta_deg": (slope or {}).get("theta_deg") or ph.get("theta_deg"),
                    "fs": (slope or {}).get("fs") or ph.get("slope_fs"),
                    "slope_stable": False,
                },
            }
        )

    env = ph.get("envelope_refuse") if isinstance(ph.get("envelope_refuse"), dict) else None
    if isinstance(env, dict) and env.get("inside_envelope") is False:
        modes.append(
            {
                "id": "FM_ENVELOPE_OUTSIDE",
                "fatal": True,
                "detail": {
                    "envelope_id": env.get("envelope_id"),
                    "window_dose_gy": env.get("window_dose_gy"),
                    "mission_budget_gy": env.get("mission_budget_gy"),
                },
            }
        )

    earth = ph.get("earth_lane") if isinstance(ph.get("earth_lane"), dict) else None
    if isinstance(earth, dict):
        if earth.get("earth_traverse_ok") is False or float(earth.get("bearing_margin") or 99.0) < 1.0:
            modes.append(
                {
                    "id": "FM_EARTH_BEARING",
                    "fatal": True,
                    "detail": {
                        "bearing_margin": earth.get("bearing_margin"),
                        "q_ult_kpa": earth.get("q_ult_kpa"),
                        "terzaghi_pack": earth.get("terzaghi_pack"),
                    },
                }
            )
        if float(earth.get("wind_risk") or 0.0) >= 2.0:
            modes.append(
                {
                    "id": "FM_EARTH_WIND",
                    "fatal": True,
                    "detail": {
                        "wind_risk": earth.get("wind_risk"),
                        "f_wind_n": earth.get("f_wind_n"),
                        "wind_pack": earth.get("wind_pack"),
                    },
                }
            )

    fatal = [m for m in modes if m.get("fatal")]
    clear = len(fatal) == 0
    return {
        "schema": "ha_failure_mode_gate_v1",
        "proof_tier": PROOF_TIER,
        "failure_modes_clear": clear,
        "fatal_count": len(fatal),
        "modes": modes,
        "fatal_ids": [m["id"] for m in fatal],
        "honesty": {
            "proof_tier": PROOF_TIER,
            "not_measured": True,
            "not_full_multibody": True,
            "epsilon": ["ε_mode_set_incomplete", "ε_desk_not_world"],
            "tabu_claim_measured": True,
        },
    }


def apply_failure_modes_to_physics(physics: dict[str, Any]) -> dict[str, Any]:
    out = dict(physics)
    block = evaluate_failure_modes(out)
    out["failure_modes"] = block
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "failure_mode_gate": True,
            "failure_modes_clear": bool(block["failure_modes_clear"]),
            "proof_tier_failure_mode_gate": True,
        }
    )
    out["honesty"] = honesty
    if not block["failure_modes_clear"]:
        out["traverse_feasible"] = False
        out["sinkage_risk"] = True
    return out
