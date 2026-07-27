"""Contact friction identification v1 — Coulomb model + catalog μ params.

Extends grasp ADAPT proxy with identified static/kinetic friction bounds.
TABU: claim MEASURED regolith friction · claim flight grasp qual.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE = _REPO / "fixtures" / "robot" / "contact_friction_catalog_v0.json"

PROOF_TIER = "CONTACT_FRICTION_SLICE"
ORACLE = "FRICTION_IDENTIFICATION_CATALOG"


def load_friction_catalog() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def resolve_friction_pair(
    *,
    pad_material_id: str,
    surface_id: str,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = catalog or load_friction_catalog()
    pairs = doc.get("friction_pairs") or {}
    key = f"{pad_material_id}__{surface_id}"
    if key not in pairs:
        raise KeyError(f"unknown friction pair: {key}")
    row = dict(pairs[key])
    return {"pair_id": key, **row}


def evaluate_coulomb_contact(
    *,
    normal_force_n: float,
    tangential_force_n: float,
    pad_material_id: str,
    surface_id: str,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pair = resolve_friction_pair(
        pad_material_id=pad_material_id,
        surface_id=surface_id,
        catalog=catalog,
    )
    mu_s = float(pair.get("mu_static") or 0.5)
    mu_k = float(pair.get("mu_kinetic") or 0.35)
    n = max(float(normal_force_n), 0.0)
    f_t = abs(float(tangential_force_n))
    f_s_max = mu_s * n
    f_k_max = mu_k * n
    slips = f_t > f_s_max + 1e-9 if n > 1e-9 else False
    return {
        "normal_force_n": n,
        "tangential_force_n": f_t,
        "mu_static": mu_s,
        "mu_kinetic": mu_k,
        "static_limit_n": round(f_s_max, 4),
        "kinetic_limit_n": round(f_k_max, 4),
        "slip_predicted": slips,
        "pair_id": pair["pair_id"],
        "identification_source": pair.get("source", "catalog"),
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
    }


def compare_grasp_envelope_with_friction(
    *,
    grasp_force_n: float,
    pad_id: str,
    zone: str = "massif_traverse",
    tangential_ratio: float = 0.15,
) -> dict[str, Any]:
    from production_gate.lunar_manipulator_grasp_v1 import simulate_grasp_contact

    adapt = simulate_grasp_contact(grasp_force_n=grasp_force_n, pad_id=pad_id, zone=zone)  # type: ignore[arg-type]
    pad_material = str(adapt.get("material_id") or "nbr_70a")
    surface = "lunar_regolith_compact"
    friction = evaluate_coulomb_contact(
        normal_force_n=grasp_force_n,
        tangential_force_n=grasp_force_n * tangential_ratio,
        pad_material_id=pad_material,
        surface_id=surface,
    )
    adapt_allowed = float(adapt.get("ingress_disturbance_mult") or 1.0)
    friction_scale = 0.65 if friction["slip_predicted"] else 1.0
    return {
        "adapt_only": adapt,
        "friction": friction,
        "envelope_diverge": friction_scale < 1.0 or friction["slip_predicted"],
        "combined_ingress_scale": round(adapt_allowed * friction_scale, 4),
    }


def validate_friction_falsifiers() -> dict[str, Any]:
    slip = evaluate_coulomb_contact(
        normal_force_n=10.0,
        tangential_force_n=8.0,
        pad_material_id="nbr_70a",
        surface_id="lunar_regolith_compact",
    )
    stick = evaluate_coulomb_contact(
        normal_force_n=50.0,
        tangential_force_n=2.0,
        pad_material_id="nbr_70a",
        surface_id="lunar_regolith_compact",
    )
    env = compare_grasp_envelope_with_friction(
        grasp_force_n=30.0,
        pad_id="nbr_sealed_finger_b2",
        tangential_ratio=0.75,
    )
    checks = {
        "F_slip_bound": slip["slip_predicted"] is True,
        "F_stick_bound": stick["slip_predicted"] is False,
        "F_envelope_diverge": env["envelope_diverge"] is True,
        "F_catalog_pair": "nbr_70a__lunar_regolith_compact" == slip["pair_id"],
    }
    fail = [k for k, v in checks.items() if not v]
    return {"checks": checks, "fail": fail, "pass": not fail}


def run_contact_friction_smoke() -> dict[str, Any]:
    fals = validate_friction_falsifiers()
    return {
        "verdict": "CONTACT_FRICTION_SLICE_PASS" if fals["pass"] else "CONTACT_FRICTION_SLICE_FAIL",
        "falsifiers": fals,
    }
