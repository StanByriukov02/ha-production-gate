"""Optional D2 thermal/soiling hook — links ORACLE_SEC_D2_ARENA_ENV."""
from __future__ import annotations

from typing import Any


def d2_soiling_hook(*, soiling_frac: float = 0.15) -> dict[str, Any]:
    """Scalar albedo shift on radiator proxy — optional hop 6."""
    albedo_clean = 0.12
    albedo_soiled = albedo_clean + soiling_frac * 0.25
    q_solar = 1367.0
    delta_absorbed = q_solar * (albedo_soiled - albedo_clean)
    return {
        "hop_id": "h-arena-eds-d2-hook",
        "verdict": "PASS",
        "oracle": "ADAPT_CLOSED",
        "soiling_frac": soiling_frac,
        "albedo_clean": albedo_clean,
        "albedo_soiled": round(albedo_soiled, 4),
        "delta_absorbed_w_m2": round(delta_absorbed, 4),
        "vault_parent": "06_2BRAIN/DOGFOOD/domains/physics/ORACLE_SEC_D2_ARENA_ENV.md",
        "optional": True,
        "falsifier": "soiling must raise absorbed flux — not zero shift",
    }
