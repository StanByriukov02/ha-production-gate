"""GAP-MR-06 — site-derived burial thickness and column density (Goossens + Heiken + Benaroya)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "results" / "platform_bpass" / "moon" / "SITE_BURIAL_BIND_v1.json"

EmbedClass = Literal["lc2_micro_package", "traverse_berm", "radiation_berm_1m", "habitat_shield_2m"]
SiteZone = Literal["rim_sun", "massif_traverse", "psr_floor"]


def load_site_burial_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def burial_class_row(embed_class: EmbedClass, *, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    data = bind or load_site_burial_bind()
    classes = data.get("embed_classes") or {}
    if embed_class not in classes:
        raise KeyError(embed_class)
    row = dict(classes[embed_class])
    row["embed_class"] = embed_class
    return row


def burial_thickness_m(embed_class: EmbedClass = "lc2_micro_package", *, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    data = bind or load_site_burial_bind()
    row = burial_class_row(embed_class, bind=data)
    return {
        "embed_class": embed_class,
        "thickness_m": float(row.get("thickness_m") or 0.1),
        "depth_class": row.get("depth_class"),
        "site_zone": row.get("site_zone"),
        "purpose": row.get("purpose"),
        "l0_cites": list(row.get("cite") or []),
        "oracle": str(data.get("oracle") or "CITED_BIND"),
        "bind_id": str(data.get("bind_id") or "site_burial_bind_v1"),
    }


def crustal_density_kg_m3(
    *,
    depth_km: float = 0.0,
    is_psr: bool = False,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = bind or load_site_burial_bind()
    grad = data.get("density_gradient") or {}
    base = float(grad.get("psr_mean_kg_m3") if is_psr else grad.get("non_psr_mean_kg_m3") or 2481)
    slope = float(grad.get("gradient_kg_m3_per_km") or 25.0)
    rho = base - slope * depth_km
    return {
        "depth_km": depth_km,
        "is_psr": is_psr,
        "rho_kg_m3": round(rho, 1),
        "gradient_kg_m3_per_km": slope,
        "l0_cites": list(grad.get("cite") or ["GOOSSENS-L0-01"]),
        "oracle": str(data.get("oracle") or "CITED_BIND"),
    }


def burial_column(
    embed_class: EmbedClass = "lc2_micro_package",
    *,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    thick = burial_thickness_m(embed_class, bind=bind)
    t_m = float(thick["thickness_m"])
    zone = str(thick.get("site_zone") or "rim_sun")
    is_psr = zone == "psr_floor"
    rho_row = crustal_density_kg_m3(depth_km=t_m / 1000.0, is_psr=is_psr, bind=bind)
    rho = float(rho_row["rho_kg_m3"])
    areal_g_cm2 = rho * t_m * 0.1  # kg/m³ * m → g/cm²
    return {
        **thick,
        "rho_kg_m3": rho,
        "areal_density_g_cm2": round(areal_g_cm2, 4),
        "l0_cites": list(dict.fromkeys(list(thick.get("l0_cites") or []) + list(rho_row.get("l0_cites") or []))),
    }


def compare_burial_thickness_paths(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    lc2 = burial_column("lc2_micro_package", bind=bind)
    traverse = burial_column("traverse_berm", bind=bind)
    rad = burial_column("radiation_berm_1m", bind=bind)
    habitat = burial_column("habitat_shield_2m", bind=bind)
    t_lc2 = float(lc2["thickness_m"])
    t_hab = float(habitat["thickness_m"])
    a_lc2 = float(lc2["areal_density_g_cm2"])
    a_hab = float(habitat["areal_density_g_cm2"])
    return {
        "compare_id": "SITE_BURIAL_COMPARE_v1",
        "lc2_micro_package": lc2,
        "traverse_berm": traverse,
        "radiation_berm_1m": rad,
        "habitat_shield_2m": habitat,
        "thickness_monotonic": t_lc2 < float(traverse["thickness_m"]) < t_hab,
        "areal_monotonic": a_lc2 < a_hab,
        "variants_diverge": t_lc2 != t_hab,
        "oracle": "CITED_BIND",
        "bind": "results/platform_bpass/moon/SITE_BURIAL_BIND_v1.json",
    }
