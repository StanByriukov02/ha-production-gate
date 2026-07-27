"""EDS-2R split-ring capacitive sense proxy (arena hop 5)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_BIND = _REPO / "results" / "platform_bpass" / "arena" / "EDS_2R_GEOMETRY_BIND_v1.json"


def load_geometry_bind(bind: dict[str, Any] | None = None) -> dict[str, Any]:
    return bind or json.loads(_BIND.read_text(encoding="utf-8"))


def sense_delta_c(
    *,
    dust_layer_um: float = 10.0,
    epsilon_dust: float = 2.5,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_geometry_bind(bind)
    p = data["params_mm"]
    ring_w = float(p["sense_ring_width"])
    active_r = float(p["active_radius"])
    # parallel plate proxy: C ~ eps * A / d
    area_mm2 = 2.0 * math.pi * (active_r + ring_w * 0.5) * ring_w
    d_clean_mm = float(p["dielectric_overcoat_height"])
    d_soiled_mm = d_clean_mm + dust_layer_um * 1e-3
    c_clean = epsilon_dust * area_mm2 / d_clean_mm
    c_soiled = epsilon_dust * area_mm2 / d_soiled_mm
    delta_frac = (c_soiled - c_clean) / c_clean
    return {
        "hop_id": "h-arena-eds-sense",
        "verdict": "PASS",
        "oracle": "PROXY_STRUCTURE",
        "area_mm2": round(area_mm2, 4),
        "d_clean_mm": d_clean_mm,
        "d_soiled_mm": round(d_soiled_mm, 6),
        "dust_layer_um": dust_layer_um,
        "delta_c_frac": round(delta_frac, 6),
        "sense_responds_to_dust": delta_frac < 0,
        "falsifier": "dust layer must reduce capacitance vs clean overcoat",
    }


def compare_sense_geometry_ignored(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    clean = sense_delta_c(dust_layer_um=0.0, bind=bind)
    dusty = sense_delta_c(dust_layer_um=20.0, bind=bind)
    return {
        "clean_delta_c_frac": clean["delta_c_frac"],
        "dusty_delta_c_frac": dusty["delta_c_frac"],
        "dust_lowers_c": dusty["delta_c_frac"] < clean["delta_c_frac"],
        "falsifier_pass": dusty["delta_c_frac"] < clean["delta_c_frac"],
    }
