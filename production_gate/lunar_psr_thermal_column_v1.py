"""GAP-MR-05 / A3-1 — PSR subsurface thermal column (Martinez LPSC + Woods cryo k leg).

Cryo-scaled k(T) oracle is Rust `ha-physics-gate thermal-k --cryo`. Python is glue.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from production_gate.lunar_regolith_thermal_v1 import effective_k_w_mk
from production_gate.regolith_thermal_on_v1 import ORACLE as THERMAL_ORACLE
from production_gate.regolith_thermal_on_v1 import k_from_catalog

_REPO = Path(__file__).resolve().parents[1]
_PSR_BIND = _REPO / "results" / "platform_bpass" / "moon" / "PSR_THERMAL_COLUMN_BIND_v1.json"


def load_psr_thermal_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _PSR_BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def effective_k_with_cryo_leg(
    material_id: str,
    *,
    t_k: float,
    thermal_bind: dict[str, Any] | None = None,
    psr_bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del thermal_bind, psr_bind  # cryo coeffs owned by ON catalog
    rust = k_from_catalog(material_id=material_id, t_k=t_k, cryo=True)
    return {
        "material_id": material_id,
        "t_k": round(t_k, 4),
        "k_w_mk": round(float(rust["k_w_mk"]), 8),
        "k_solid_w_mk": float(rust["k_solid_w_mk"]),
        "b_rad": float(rust["b_rad"]),
        "cryo_scale_applied": float(rust["cryo_scale_applied"]),
        "t_cryo_k": float(rust["t_cryo_k"]),
        "l0_cites": list(rust.get("cite") or []) + ["WOODS-ROBINSON-2019-L0-02"],
        "oracle": THERMAL_ORACLE,
        "honesty": {
            "k_from_on_catalog": True,
            "cryo_from_on_catalog": True,
            "catalog_mirror_of_rust": True,
            "python_not_independent_oracle": True,
            "not_measured": True,
        },
    }


def psr_subsurface_delta_k(*, depth_m: float = 2.0, psr_bind: dict[str, Any] | None = None) -> dict[str, Any]:
    """Martinez LPSC subsurface ΔT adjunct — cited bind, not k(T) oracle."""
    psr = psr_bind or load_psr_thermal_bind()
    rows = psr.get("psr_subsurface_delta_k") or {}
    if "depth_2m_k" not in rows or "depth_4m_k" not in rows:
        raise KeyError("PSR_THERMAL_COLUMN_BIND missing depth anchors")
    d2 = float(rows["depth_2m_k"])
    d4 = float(rows["depth_4m_k"])
    if depth_m <= 2.0:
        delta = d2 * (depth_m / 2.0)
    elif depth_m <= 4.0:
        delta = d2 + (d4 - d2) * ((depth_m - 2.0) / 2.0)
    else:
        delta = d4
    return {
        "depth_m": depth_m,
        "delta_t_k_vs_legacy_model": round(delta, 2),
        "anchor_depth_2m_k": d2,
        "anchor_depth_4m_k": d4,
        "site_class": rows.get("site") or "Shoemaker_PSR_class",
        "l0_cites": ["MARTINEZ-LPSC-L0-05", "MARTINEZ-LPSC-L0-06"],
        "oracle": str(psr.get("oracle") or "CITED_BIND"),
        "honesty": {
            "martinez_adjunct_not_k_oracle": True,
            "k_oracle": THERMAL_ORACLE,
        },
    }


def compare_psr_thermal_column(*, material_id: str = "highland_regolith_loose") -> dict[str, Any]:
    t_floor = 80.0
    k_legacy = effective_k_w_mk(material_id, t_k=t_floor)
    k_cryo = effective_k_with_cryo_leg(material_id, t_k=t_floor)
    sub2 = psr_subsurface_delta_k(depth_m=2.0)
    sub4 = psr_subsurface_delta_k(depth_m=4.0)
    return {
        "compare_id": "PSR_THERMAL_COLUMN_COMPARE_v1",
        "t_floor_k": t_floor,
        "k_legacy_w_mk": k_legacy["k_w_mk"],
        "k_cryo_leg_w_mk": k_cryo["k_w_mk"],
        "cryo_reduces_k": float(k_cryo["k_w_mk"]) < float(k_legacy["k_w_mk"]),
        "subsurface_2m": sub2,
        "subsurface_4m": sub4,
        "subsurface_warmer_with_new_k": sub2["delta_t_k_vs_legacy_model"] > 0,
        "oracle": THERMAL_ORACLE,
        "bind": "fixtures/open_registry/env/regolith_thermal_on_v1.json",
        "honesty": {
            "k_from_on_catalog": True,
            "cryo_from_on_catalog": True,
            "catalog_mirror_of_rust": True,
            "python_not_independent_oracle": True,
        },
    }
