"""GAP-MR-01/03 — regolith k(T) cite-bound (Heiken + Sakatani).

k(T) oracle is Rust `ha-physics-gate thermal-k`. Python is glue + porosity adjunct.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dogfood_platform.lunar_regolith_porosity_v1 import porosity_for_material
from dogfood_platform.regolith_thermal_on_v1 import ORACLE as THERMAL_ORACLE
from dogfood_platform.regolith_thermal_on_v1 import k_from_catalog, load_regolith_thermal_catalog

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "results" / "platform_bpass" / "moon" / "REGOLITH_THERMAL_BIND_v1.json"


def load_thermal_bind(path: Path | None = None) -> dict[str, Any]:
    """Legacy evidence/porosity bind — k coefficients owned by ON catalog for Rust."""
    p = path or _BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def effective_k_w_mk(
    material_id: str,
    *,
    t_k: float = 300.0,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """k at temperature — ON catalog equation (mirror of Rust; Dual proves Rust match)."""
    del bind  # k coeffs from ON catalog; porosity still from platform bind
    rust = k_from_catalog(material_id=material_id, t_k=t_k, cryo=False)
    data = load_thermal_bind()
    band = (load_regolith_thermal_catalog().get("materials") or {}).get(material_id, {}).get(
        "heiken_band_w_mk"
    ) or []
    k_val = float(rust["k_w_mk"])
    in_band = True
    if len(band) == 2:
        in_band = float(band[0]) <= k_val <= float(band[1]) or abs(t_k - 300.0) > 1.0
    phi_row = porosity_for_material(material_id, bind=data)
    return {
        "material_id": material_id,
        "t_k": round(t_k, 4),
        "k_w_mk": round(k_val, 6),
        "k_solid_w_mk": float(rust["k_solid_w_mk"]),
        "b_rad": float(rust["b_rad"]),
        "phi": phi_row.get("phi"),
        "within_heiken_band_at_300k": in_band if abs(t_k - 300.0) < 1.0 else None,
        "l0_cites": list(
            dict.fromkeys(
                list(rust.get("cite") or []) + list(phi_row.get("l0_cites") or [])
            )
        ),
        "oracle": THERMAL_ORACLE,
        "bind_id": "regolith_thermal_on_v1",
        "honesty": {
            "bekker_not_involved": True,
            "k_from_on_catalog": True,
            "catalog_mirror_of_rust": True,
            "python_not_independent_oracle": True,
            "not_measured": True,
        },
    }


def compare_porosity_thermal_paths(*, fgm_branch: str = "A", bind: dict[str, Any] | None = None) -> dict[str, Any]:
    """Falsifier receipt — φ branches + k(T) polar envelope 250–330 K."""
    data = bind or load_thermal_bind()
    kt = data.get("k_temperature") or {}
    t_lo, t_hi = kt.get("polar_envelope_k") or [250.0, 330.0]
    loose_id = "highland_regolith_loose"
    compact_id = "highland_regolith_compact"
    k_loose_cold = effective_k_w_mk(loose_id, t_k=float(t_lo), bind=data)
    k_loose_hot = effective_k_w_mk(loose_id, t_k=float(t_hi), bind=data)
    k_compact_cold = effective_k_w_mk(compact_id, t_k=float(t_lo), bind=data)
    k_compact_hot = effective_k_w_mk(compact_id, t_k=float(t_hi), bind=data)
    k_loose_300 = effective_k_w_mk(loose_id, t_k=300.0, bind=data)
    k_compact_300 = effective_k_w_mk(compact_id, t_k=300.0, bind=data)
    return {
        "compare_id": "REGOLITH_POROSITY_THERMAL_COMPARE_v1",
        "lane": "L2_cite_bind_phi_and_k_T",
        "fgm_branch_fixed": fgm_branch,
        "t_envelope_k": [float(t_lo), float(t_hi)],
        "at_300k": {
            "loose": k_loose_300,
            "compact": k_compact_300,
            "compact_higher_k": float(k_compact_300["k_w_mk"]) > float(k_loose_300["k_w_mk"]),
        },
        "polar_swing": {
            "loose": {"t_cold_k": t_lo, "k_cold": k_loose_cold["k_w_mk"], "t_hot_k": t_hi, "k_hot": k_loose_hot["k_w_mk"]},
            "compact": {
                "t_cold_k": t_lo,
                "k_cold": k_compact_cold["k_w_mk"],
                "t_hot_k": t_hi,
                "k_hot": k_compact_hot["k_w_mk"],
            },
        },
        "k_increases_with_T_loose": float(k_loose_hot["k_w_mk"]) > float(k_loose_cold["k_w_mk"]),
        "k_increases_with_T_compact": float(k_compact_hot["k_w_mk"]) > float(k_compact_cold["k_w_mk"]),
        "delta_k_loose_hot_minus_cold": round(float(k_loose_hot["k_w_mk"]) - float(k_loose_cold["k_w_mk"]), 6),
        "delta_k_compact_hot_minus_cold": round(float(k_compact_hot["k_w_mk"]) - float(k_compact_cold["k_w_mk"]), 6),
        "oracle": THERMAL_ORACLE,
        "bind": "fixtures/open_registry/env/regolith_thermal_on_v1.json",
        "falsifier": str((kt.get("falsifier") or "")),
    }
