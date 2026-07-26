"""E2 Earth-lane embed — Terzaghi q_ult + wind load into Earth Dual physics_row.

Teaching: when field globe is Earth, attach Rust Terzaghi + wind so Safe≠Hostile
burns on bearing margin / wind risk — not lunar Bekker theater alone.
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]

TERZ_SAFE = "earth_firm_safe"
TERZ_HOSTILE = "earth_soft_hostile"
WIND_SAFE = "earth_calm"
WIND_HOSTILE = "earth_storm"
# Teaching reference: wind force above this raises earth_wind_risk Dual.
WIND_F_REF_N = 50.0


def packs_for_condition(condition: ConditionId) -> tuple[str, str]:
    if condition == "hostile":
        return TERZ_HOSTILE, WIND_HOSTILE
    return TERZ_SAFE, WIND_SAFE


def evaluate_earth_lane(
    *,
    condition: ConditionId,
    ground_pressure_kpa: float = 40.0,
) -> dict[str, Any]:
    """Evaluate Terzaghi + wind from Rust for Earth Dual condition."""
    from dogfood_platform.terzaghi_bearing_on_v1 import evaluate_terzaghi_bearing
    from dogfood_platform.wind_load_on_v1 import evaluate_wind_load

    terz_id, wind_id = packs_for_condition(condition)
    terz = evaluate_terzaghi_bearing(pack_id=terz_id)
    wind = evaluate_wind_load(pack_id=wind_id)
    q_ult = float(terz["q_ult_kpa"])
    f_wind = float(wind["f_wind_n"])
    p = max(float(ground_pressure_kpa), 1e-9)
    bearing_margin = q_ult / p
    wind_risk = f_wind / WIND_F_REF_N
    # Teaching Earth feasibility: soft soil + storm can refuse.
    earth_traverse_ok = bearing_margin >= 1.0 and wind_risk < 2.0
    earth_risk = (not earth_traverse_ok) or bearing_margin < 1.5 or wind_risk >= 1.0
    return {
        "schema": "ha_earth_lane_embed_v1",
        "condition": condition,
        "terzaghi_pack": terz_id,
        "wind_pack": wind_id,
        "q_ult_kpa": q_ult,
        "f_wind_n": f_wind,
        "q_pa": float(wind.get("q_pa") or 0.0),
        "ground_pressure_kpa": p,
        "bearing_margin": bearing_margin,
        "wind_risk": wind_risk,
        "earth_traverse_ok": earth_traverse_ok,
        "earth_risk": earth_risk,
        "terzaghi_oracle": terz.get("oracle"),
        "wind_oracle": wind.get("oracle"),
        "honesty": {
            "earth_lane_from_rust": True,
            "terzaghi_from_rust": True,
            "wind_from_rust": True,
            "not_measured": True,
            "not_fem_cfd": True,
            "not_lunar_bekker_theater": True,
        },
    }


def attach_earth_lane_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    ground_pressure_kpa: float | None = None,
) -> dict[str, Any]:
    """Attach Earth Terzaghi+wind block; may tighten traverse/risk Dual."""
    out = dict(physics)
    p = ground_pressure_kpa
    if p is None:
        p = float(out.get("ground_pressure_kpa") or 40.0)
    lane = evaluate_earth_lane(condition=condition, ground_pressure_kpa=float(p))
    out["earth_lane"] = lane
    honesty = dict(out.get("honesty") or {})
    honesty.update(
        {
            "earth_lane_from_rust": True,
            "terzaghi_from_rust": True,
            "wind_from_rust": True,
            "not_lunar_bekker_theater": True,
        }
    )
    out["honesty"] = honesty
    out["bearing_margin"] = float(lane["bearing_margin"])
    out["wind_risk"] = float(lane["wind_risk"])
    out["earth_traverse_ok"] = bool(lane["earth_traverse_ok"])
    # Dual consequence on Earth: Hostile soft+storm can flip feasibility.
    if not lane["earth_traverse_ok"]:
        out["traverse_feasible"] = False
        out["sinkage_risk"] = True
    elif lane["earth_risk"]:
        out["sinkage_risk"] = True
    return out


def is_earth_globe(globe: str | None) -> bool:
    return str(globe or "").strip().lower() == "earth"
