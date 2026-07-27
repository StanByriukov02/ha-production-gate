"""L1 materials harness — FGM habitat + regolith ρ · cited constants, not FEM solver."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from production_gate.lunar_regolith_porosity_v1 import porosity_for_material
from production_gate.lunar_regolith_thermal_v1 import effective_k_w_mk

# Heiken L0-03 surface band · FGRM Cheibas L0-10 LHS SPS · FGRM L0-09 Ti6Al4V pair
MATERIALS_L1: dict[str, dict[str, Any]] = {
    "highland_regolith_loose": {
        "rho_g_cm3": 1.59,
        "rho_kg_m3": 1590.0,
        "k_w_mk": 0.022,
        "porosity_phi": 0.42,
        "l0_cites": ["HEIKEN-L0-03", "HEIKEN-L0-05", "SAKATANI-LPSC-1552"],
        "provenance": "highland_surface_15cm",
        "thermal_bind": "REGOLITH_THERMAL_BIND_v1",
    },
    "highland_regolith_compact": {
        "rho_g_cm3": 1.66,
        "rho_kg_m3": 1660.0,
        "k_w_mk": 0.025,
        "porosity_phi": 0.40,
        "l0_cites": ["HEIKEN-L0-02", "HEIKEN-L0-05", "SAKATANI-LPSC-1552"],
        "provenance": "depth_60cm_class",
        "thermal_bind": "REGOLITH_THERMAL_BIND_v1",
    },
    "fgm_lhs_sintered": {
        "rho_g_cm3": 2.616,
        "rho_kg_m3": 2616.0,
        "k_w_mk": 0.8,
        "l0_cites": ["FGRM-L0-10", "FGRM-L0-09"],
        "provenance": "LHS-1 SPS 1050C 80MPa",
    },
    "fgm_eac_sintered": {
        "rho_g_cm3": 2.704,
        "rho_kg_m3": 2704.0,
        "k_w_mk": 0.85,
        "l0_cites": ["FGRM-Table5"],
        "provenance": "EAC-1A SPS 1075C class",
    },
    "ti6al4v_substrate": {
        "rho_g_cm3": 4.43,
        "rho_kg_m3": 4430.0,
        "k_w_mk": 7.0,
        "l0_cites": ["FGRM-L0-09"],
        "provenance": "FGM metal tier",
    },
    "tim_silicone_class": {
        "rho_g_cm3": 1.2,
        "rho_kg_m3": 1200.0,
        "k_w_mk": 5.0,
        "l0_cites": ["PACKAGE_PROXY"],
        "provenance": "LC-2 TIM slot — L1 harness",
    },
}


@dataclass(frozen=True)
class MaterialL1:
    material_id: str
    rho_kg_m3: float
    k_w_mk: float
    porosity_phi: float | None
    l0_cites: tuple[str, ...]


def material_snapshot(material_id: str, *, t_k: float = 300.0) -> MaterialL1:
    row = MATERIALS_L1[material_id]
    k_w_mk = float(row["k_w_mk"])
    phi: float | None = row.get("porosity_phi")
    cites = list(row.get("l0_cites") or [])
    if "regolith" in material_id:
        try:
            k_row = effective_k_w_mk(material_id, t_k=t_k)
            k_w_mk = float(k_row["k_w_mk"])
            phi = float(k_row["phi"]) if k_row.get("phi") is not None else phi
            cites = list(dict.fromkeys(cites + list(k_row.get("l0_cites") or [])))
        except (FileNotFoundError, KeyError):
            pass
        if phi is None:
            try:
                phi = float(porosity_for_material(material_id)["phi"])
            except FileNotFoundError:
                phi = None
    return MaterialL1(
        material_id=material_id,
        rho_kg_m3=float(row["rho_kg_m3"]),
        k_w_mk=k_w_mk,
        porosity_phi=phi,
        l0_cites=tuple(cites),
    )


def regolith_rho_table() -> dict[str, float]:
    """ρ snapshot for anchor receipts — g/cm³."""
    return {mid: float(row["rho_g_cm3"]) for mid, row in MATERIALS_L1.items() if "regolith" in mid or "fgm" in mid}
