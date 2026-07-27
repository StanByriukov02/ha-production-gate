"""GAP-MR-12 — dust ingress / accumulation (Stubbs + Colwell + Benaroya ADAPT).

Oracle: Rust `ha-physics-gate dust-ingress`. Hot path = ON catalog mirror.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from production_gate.dust_ingress_on_v1 import ORACLE as DUST_ORACLE
from production_gate.dust_ingress_on_v1 import dust_from_catalog, load_dust_ingress_catalog

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "results" / "platform_bpass" / "moon" / "DUST_INGRESS_BIND_v1.json"

SiteZone = Literal["rim_sun", "massif_traverse", "psr_floor"]
SealClass = Literal["B1", "B2", "B3", "B4", "B5"]


def load_dust_ingress_bind(path: Path | None = None) -> dict[str, Any]:
    """Legacy evidence bind — rate law owned by ON catalog for Rust."""
    p = path or _BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def electrostatic_index(zone: SiteZone, *, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    del bind
    cat = load_dust_ingress_catalog()
    z = cat["zones"][zone]
    return {
        "zone": zone,
        "electrostatic_index": float(z["electrostatic_index"]),
        "loft_altitude_km": float(cat["loft_altitude_km"]),
        "l0_cites": ["STUBBS-2006-L0-05"],
        "oracle": DUST_ORACLE,
    }


def ingress_rate_g_m2_per_sol(zone: SiteZone, *, bind: dict[str, Any] | None = None) -> float:
    del bind
    return float(load_dust_ingress_catalog()["zones"][zone]["base_rate_g_m2_per_sol"])


def evaluate_ingress_hazard(
    *,
    zone: SiteZone = "massif_traverse",
    seal_class: SealClass = "B3",
    mitigation_duty: float = 0.0,
    joint_gap_mm: float = 0.5,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del bind
    row = dust_from_catalog(
        zone=zone,
        seal=seal_class,
        n_sols=0.0,
        mitigation_duty=mitigation_duty,
        joint_gap_mm=joint_gap_mm,
        prev_g_m2=0.0,
    )
    es = electrostatic_index(zone)
    return {
        "zone": zone,
        "seal_class": seal_class,
        "joint_gap_mm": joint_gap_mm,
        "mitigation_duty": mitigation_duty,
        "base_rate_g_m2_per_sol": row["base_rate_g_m2_per_sol"],
        "effective_rate_g_m2_per_sol": round(float(row["effective_rate_g_m2_per_sol"]), 5),
        "ingress_hazard_class": row["ingress_hazard_class"],
        "electrostatic": es,
        "l0_cites": ["STUBBS-2006-L0-05", "BENAROYA-L0-06"],
        "oracle": DUST_ORACLE,
        "bind_id": "dust_ingress_on_v1",
        "honesty": {
            "catalog_mirror_of_rust": True,
            "python_not_independent_oracle": True,
            "not_measured": True,
        },
    }


def accumulation_after_sols(
    *,
    n_sols: float,
    zone: SiteZone = "massif_traverse",
    seal_class: SealClass = "B3",
    mitigation_duty: float = 0.0,
    joint_gap_mm: float = 0.5,
    prev_g_m2: float = 0.0,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del bind
    row = dust_from_catalog(
        zone=zone,
        seal=seal_class,
        n_sols=n_sols,
        mitigation_duty=mitigation_duty,
        joint_gap_mm=joint_gap_mm,
        prev_g_m2=prev_g_m2,
    )
    hazard = evaluate_ingress_hazard(
        zone=zone,
        seal_class=seal_class,
        mitigation_duty=mitigation_duty,
        joint_gap_mm=joint_gap_mm,
    )
    return {
        **hazard,
        "n_sols": n_sols,
        "prev_accumulation_g_m2": prev_g_m2,
        "accumulation_g_m2": round(float(row["accumulation_g_m2"]), 5),
        "saturated": bool(row["saturated"]),
        "oracle": DUST_ORACLE,
    }


def ingress_wear_stress_mult(
    accumulation_g_m2: float,
    *,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del bind
    wear = load_dust_ingress_catalog()["wear_coupling"]
    coeff = float(wear["abrasion_coeff_per_g_m2"])
    cap = float(wear["max_stress_mult"])
    mult = min(cap, 1.0 + coeff * accumulation_g_m2)
    return {
        "accumulation_g_m2": accumulation_g_m2,
        "stress_index_multiplier": round(mult, 6),
        "abrasion_coeff_per_g_m2": coeff,
        "max_stress_mult": cap,
        "l0_cites": ["BENAROYA-L0-04"],
        "oracle": DUST_ORACLE,
    }


def compare_ingress_mitigation_paths(*, zone: SiteZone = "massif_traverse", n_sols: float = 30.0) -> dict[str, Any]:
    open_joint = accumulation_after_sols(n_sols=n_sols, zone=zone, seal_class="B5", mitigation_duty=0.0)
    sealed = accumulation_after_sols(n_sols=n_sols, zone=zone, seal_class="B1", mitigation_duty=1.0)
    open_wear = ingress_wear_stress_mult(float(open_joint["accumulation_g_m2"]))
    sealed_wear = ingress_wear_stress_mult(float(sealed["accumulation_g_m2"]))
    return {
        "compare_id": "DUST_INGRESS_COMPARE_v1",
        "zone": zone,
        "n_sols": n_sols,
        "open_B5_zero_mitigation": open_joint,
        "sealed_B1_full_mitigation": sealed,
        "open_stress_mult": open_wear["stress_index_multiplier"],
        "sealed_stress_mult": sealed_wear["stress_index_multiplier"],
        "open_higher_stress": open_wear["stress_index_multiplier"] > sealed_wear["stress_index_multiplier"],
        "variants_diverge": float(open_joint["accumulation_g_m2"]) != float(sealed["accumulation_g_m2"]),
        "oracle": DUST_ORACLE,
        "bind": "fixtures/open_registry/env/dust_ingress_on_v1.json",
    }
