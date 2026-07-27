"""GAP-MR-10 / A4-1 — regolith column SPE/GCR shielding thresholds (Matthiä 2024 bind)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "results" / "platform_bpass" / "moon" / "RADIATION_SHIELD_BIND_v1.json"

ShieldClass = Literal["SPE_ADEQUATE", "SPE_MARGIN", "SPE_INSUFFICIENT", "GCR_WEAK"]


def load_radiation_shield_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def classify_regolith_shield(
    areal_density_g_cm2: float,
    *,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify shield depth for SPE vs GCR harness rows."""
    data = bind or load_radiation_shield_bind()
    spe = data.get("spe_regolith_g_cm2") or {}
    gcr = data.get("gcr_regolith_g_cm2") or {}
    lo = float(spe.get("below_30day_deterministic_limit") or 4.0)
    hi = float(spe.get("safety_margin_factor_2") or 10.0)
    if areal_density_g_cm2 >= hi:
        spe_class: ShieldClass = "SPE_MARGIN"
    elif areal_density_g_cm2 >= lo:
        spe_class = "SPE_ADEQUATE"
    else:
        spe_class = "SPE_INSUFFICIENT"
    gcr_ceiling = float(gcr.get("weak_shielding_ceiling") or 180.0)
    gcr_weak = areal_density_g_cm2 <= gcr_ceiling
    return {
        "areal_density_g_cm2": areal_density_g_cm2,
        "spe_class": spe_class,
        "spe_below_30day_at_g_cm2": lo,
        "spe_margin_at_g_cm2": hi,
        "gcr_weak_shield": gcr_weak,
        "shield_class": "GCR_WEAK" if gcr_weak and spe_class != "SPE_INSUFFICIENT" else spe_class,
        "l0_cites": ["MATTHIA-2024-L0-01", "MATTHIA-2024-L0-02", "MATTHIA-2024-L0-05"],
        "oracle": str(data.get("oracle") or "CITED_BIND"),
        "bind_id": str(data.get("bind_id") or "radiation_shield_bind_v1"),
    }


def radiation_shield_bind_dict(*, areal_density_g_cm2: float = 10.0) -> dict[str, Any]:
    return classify_regolith_shield(areal_density_g_cm2)


def compare_radiation_shield_paths() -> dict[str, Any]:
    lo = classify_regolith_shield(4.0)
    hi = classify_regolith_shield(10.0)
    weak = classify_regolith_shield(50.0)
    return {
        "compare_id": "RADIATION_SHIELD_COMPARE_v1",
        "spe_adequate_at_4": lo["spe_class"] == "SPE_ADEQUATE",
        "spe_margin_at_10": hi["spe_class"] == "SPE_MARGIN",
        "gcr_weak_at_50": weak["gcr_weak_shield"],
        "variants_diverge": lo["spe_class"] != hi["spe_class"],
        "shield_lo": lo,
        "shield_hi": hi,
        "shield_mid": weak,
        "oracle": "CITED_BIND",
        "bind": "results/platform_bpass/moon/RADIATION_SHIELD_BIND_v1.json",
    }
