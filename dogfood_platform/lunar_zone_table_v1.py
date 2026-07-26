"""Shackleton lunar zones — L0-cited constants for W_moon_shackleton_v0."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# L0 cites: shackleton-primary SK rows + merge
ZONES: dict[str, dict[str, Any]] = {
    "rim_sun": {
        "t_k": 220.0,
        "illumination_annual_frac": 0.96,
        "albedo_class": "highland_regolith",
        "l0_cites": ["SK-12", "SK-15", "SK-16"],
    },
    "psr_floor": {
        "t_k_mean": 70.0,
        "t_k_max": 95.0,
        "illumination_annual_frac": 0.0,
        "albedo_class": "psr_shadowed",
        "l0_cites": ["SK-09", "SK-10", "SK-07"],
    },
    "massif_traverse": {
        "slope_max_deg": 12.0,
        "slope_limit_deg": 15.0,
        "regolith_bearing_class": "MEDIUM",
        "contact_pressure_kpa": 120.0,
        "l0_cites": ["SK-13", "A-06", "GAP-MR-11"],
    },
}


@dataclass(frozen=True)
class LunarZoneSnapshot:
    zone_id: str
    t_k: float
    illumination_annual_frac: float
    albedo_class: str
    l0_cites: tuple[str, ...]


def zone_snapshot(zone_id: str) -> LunarZoneSnapshot:
    z = ZONES[zone_id]
    t = float(z.get("t_k") or z.get("t_k_mean") or 0)
    return LunarZoneSnapshot(
        zone_id=zone_id,
        t_k=t,
        illumination_annual_frac=float(z.get("illumination_annual_frac", 0)),
        albedo_class=str(z.get("albedo_class", "")),
        l0_cites=tuple(z.get("l0_cites") or ()),
    )


def polar_delta_t_k() -> float:
    rim = float(ZONES["rim_sun"]["t_k"])
    floor = float(ZONES["psr_floor"]["t_k_mean"])
    return abs(rim - floor)
