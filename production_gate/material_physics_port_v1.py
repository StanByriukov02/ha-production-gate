"""MaterialPhysicsPort v0 — registry row → W_regolith ENV_IN (cited L0).

PY_GLUE orchestrator · physics truth = lunar_wheel_locomotion_v1 (W_regolith).
TABU: claim registry = measured lunar field · MEASURED without cite.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from production_gate.open_seed_paths_v1 import materials_registry_path

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "fixtures" / "robot" / "material_physics_bind_v0.json"
_ADAPT_TREAD = _REPO / "fixtures" / "robot" / "robot_material_adapt_tread_v1.json"

PROOF_TIER = "MATERIAL_PHYSICS_PORT_SLICE"
ORACLE = "W_regolith_robot_v0"

RegolithBearingClass = Literal["LOOSE", "MEDIUM", "DENSE"]


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise json.JSONDecodeError("empty", "", 0)
    return json.loads(raw)


def load_materials_registry() -> dict[str, Any]:
    path = materials_registry_path(_REPO)
    if not path.is_file():
        raise FileNotFoundError(path)
    return _load(path)


def _heal_material_bind() -> dict[str, Any]:
    """Restore empty/corrupt bind from honesty_latch mirror (gate self-heal)."""
    mirror = (
        _REPO
        / "open_surface"
        / "honesty_latch"
        / "fixtures"
        / "robot"
        / "material_physics_bind_v0.json"
    )
    if not mirror.is_file():
        raise FileNotFoundError(f"material bind missing and no mirror at {mirror}")
    text = mirror.read_text(encoding="utf-8")
    doc = json.loads(text)
    _BIND.parent.mkdir(parents=True, exist_ok=True)
    _BIND.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return doc


def load_material_bind() -> dict[str, Any]:
    if not _BIND.is_file() or _BIND.stat().st_size < 8:
        return _heal_material_bind()
    try:
        return _load(_BIND)
    except (OSError, json.JSONDecodeError):
        return _heal_material_bind()


def _wheel_geometry(registry: dict[str, Any]) -> tuple[float, float, float]:
    geo = registry.get("geometry_assumptions") or {}
    mass_kg = float((registry.get("mass_ledger_anchor") or {}).get("total_kg") or 50.0)
    wheel_d = float(geo.get("wheel_diameter_cm") or 20.0)
    wheel_w = float(geo.get("wheel_width_cm") or 8.0)
    return mass_kg, wheel_d, wheel_w


def load_adapt_tread_bind() -> dict[str, Any]:
    if not _ADAPT_TREAD.is_file():
        raise FileNotFoundError(_ADAPT_TREAD)
    return _load(_ADAPT_TREAD)


def resolve_tread_profile(profile_id: str) -> dict[str, Any]:
    from production_gate.robot_material_catalog_v1 import resolve_tread_variant

    return resolve_tread_variant(profile_id)


def _seal_scale_for_class(seal_class: str) -> tuple[float, str]:
    from production_gate.robot_material_catalog_v1 import resolve_seal_scale

    scale, label, _mid = resolve_seal_scale(seal_class)
    return scale, label


def _seal_from_variant(variant: dict[str, Any], registry: dict[str, Any]) -> tuple[float, str, bool]:
    apply_seal = variant.get("apply_seal")
    if apply_seal is None:
        apply_seal = "joint_seal" in list(variant.get("material_keys") or [])
    if not apply_seal:
        return 1.0, "none", False
    if variant.get("seal_class"):
        scale, label = _seal_scale_for_class(str(variant["seal_class"]))
        return scale, str(variant["seal_class"]), True
    seal_scale, seal_class = _seal_ingress_scale(registry)
    return seal_scale, seal_class, True


def _wheel_geometry_for_variant(registry: dict[str, Any], variant: dict[str, Any]) -> tuple[float, float, float]:
    from production_gate.robot_material_catalog_v1 import resolve_wheel_geometry

    tread_key = variant.get("tread_profile") or variant.get("tread_material_id")
    mass_kg, wheel_d, wheel_w, _meta = resolve_wheel_geometry(
        tread_profile=str(tread_key) if tread_key else None,
        registry=registry,
    )
    return mass_kg, wheel_d, wheel_w


def _seal_ingress_scale(registry: dict[str, Any]) -> tuple[float, str]:
    seal = (registry.get("materials") or {}).get("joint_seal") or {}
    scale = float(seal.get("ingress_scale") or 1.0)
    seal_class = str(seal.get("seal_class") or seal.get("material_id") or "unknown")
    return scale, seal_class


def resolve_material_variant(variant_id: str) -> dict[str, Any]:
    bind = load_material_bind()
    variants = bind.get("variants") or {}
    if variant_id not in variants:
        raise KeyError(f"unknown material variant: {variant_id}")
    return dict(variants[variant_id])


def compute_env_in_from_material(
    *,
    variant_id: str = "scout_default_medium",
    bearing_class: RegolithBearingClass | None = None,
    zone: str | None = None,
    step_m: float | None = None,
    rover_mass_kg: float | None = None,
    wheel_diameter_cm: float | None = None,
    wheel_width_cm: float | None = None,
    n_wheels: int | None = None,
    respect_factory_tread_slot: bool = True,
) -> dict[str, Any]:
    """Material registry + variant → terramech traverse → ENV_IN modifiers."""
    from production_gate.lunar_wheel_locomotion_v1 import simulate_traverse_segment
    from production_gate.robot_material_catalog_v1 import (
        DEFAULT_TREAD_MATERIAL_ID,
        read_active_tread_material_id,
        resolve_effective_material_variant_id,
    )

    registry = load_materials_registry()
    requested_variant_id = variant_id
    if respect_factory_tread_slot:
        variant_id = resolve_effective_material_variant_id(variant_id, registry=registry)
    variant = resolve_material_variant(variant_id)
    mass_kg, wheel_d, wheel_w = _wheel_geometry_for_variant(registry, variant)
    if rover_mass_kg is not None:
        mass_kg = float(rover_mass_kg)
    if wheel_diameter_cm is not None:
        wheel_d = float(wheel_diameter_cm)
    if wheel_width_cm is not None:
        wheel_w = float(wheel_width_cm)
    wheel_count = int(n_wheels) if n_wheels is not None else 4
    seal_scale, seal_class, apply_seal = _seal_from_variant(variant, registry)

    bc: RegolithBearingClass = bearing_class or variant.get("bearing_class") or "MEDIUM"  # type: ignore[assignment]
    z = zone or str(variant.get("zone") or "massif_traverse")
    meters = float(step_m if step_m is not None else variant.get("step_m") or 100.0)

    tread = (registry.get("materials") or {}).get("wheel_tread") or {}
    tread_key = variant.get("tread_profile")
    if (
        respect_factory_tread_slot
        and not tread_key
        and "wheel_tread" in list(variant.get("material_keys") or [])
    ):
        tread_mat = read_active_tread_material_id(registry=registry)
        if tread_mat != DEFAULT_TREAD_MATERIAL_ID:
            tread_key = tread_mat
    tread_prof = resolve_tread_profile(str(tread_key)) if tread_key else {}
    material_id = str(tread_prof.get("material_id") or tread.get("material_id") or "unknown")
    tread_factor = float(tread_prof.get("ingress_mult_factor") or 1.0)

    terramech = simulate_traverse_segment(
        meters,
        rover_mass_kg=mass_kg,
        wheel_diameter_cm=wheel_d,
        wheel_width_cm=wheel_w,
        zone=z,  # type: ignore[arg-type]
        bearing_class=bc,
        n_wheels=wheel_count,
    )
    raw_terramech = float(terramech.get("ingress_disturbance_mult") or 1.0)
    base_ingress = raw_terramech * tread_factor
    scaled_ingress = round(base_ingress * seal_scale, 6)

    return {
        "variant_id": variant_id,
        "requested_variant_id": requested_variant_id,
        "factory_tread_material_id": read_active_tread_material_id(registry=registry)
        if respect_factory_tread_slot
        else DEFAULT_TREAD_MATERIAL_ID,
        "material_id": material_id,
        "tread_profile": tread_key,
        "seal_class": seal_class,
        "seal_ingress_scale": seal_scale,
        "apply_seal": bool(apply_seal),
        "bearing_class": bc,
        "zone": z,
        "step_m": meters,
        "rover_mass_kg": mass_kg,
        "wheel_diameter_cm": wheel_d,
        "wheel_width_cm": wheel_w,
        "n_wheels": wheel_count,
        "wheel_class": (terramech.get("wheel") or {}).get("wheel_class"),
        "ingress_disturbance_mult": scaled_ingress,
        "ingress_disturbance_mult_raw": round(base_ingress, 6),
        "tread_ingress_factor": tread_factor,
        "sinkage_mm": float(terramech.get("sinkage_mm") or 0.0),
        "contact_pressure_kpa": float(terramech.get("contact_pressure_kpa") or 0.0),
        "traverse_feasible": bool(terramech.get("traverse_feasible")),
        "terramech": terramech,
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
        "registry": str(materials_registry_path(_REPO).relative_to(_REPO)).replace("\\", "/"),
        "catalog_tier": str(tread_prof.get("tier") or tread.get("tier") or "CITED_BIND"),
        "material_keys": list(variant.get("material_keys") or []),
    }


def material_row_trace(*, variant_id: str = "scout_default_medium") -> dict[str, Any]:
    """Compact trace for bus / cinema / observation log."""
    env = compute_env_in_from_material(variant_id=variant_id)
    return {
        "variant_id": env["variant_id"],
        "material_id": env["material_id"],
        "seal_class": env["seal_class"],
        "bearing_class": env["bearing_class"],
        "ingress_disturbance_mult": env["ingress_disturbance_mult"],
        "sinkage_mm": env["sinkage_mm"],
        "proof_tier": env["proof_tier"],
        "oracle": env["oracle"],
    }


def run_material_physics_port_smoke() -> dict[str, Any]:
    medium = compute_env_in_from_material(variant_id="scout_default_medium")
    loose = compute_env_in_from_material(variant_id="scout_loose_seal_b3")
    dense = compute_env_in_from_material(variant_id="scout_dense_wheel")
    loose_ratio = float((loose.get("terramech") or {}).get("bearing", {}).get("pressure_ratio") or 0.0)
    dense_ratio = float((dense.get("terramech") or {}).get("bearing", {}).get("pressure_ratio") or 0.0)
    checks = {
        "F_medium_ingress_positive": float(medium["ingress_disturbance_mult"]) > 1.0,
        "F_bearing_changes_pressure_ratio": loose_ratio != dense_ratio,
        "F_seal_scale_applied": float(medium["ingress_disturbance_mult"])
        == round(float(medium["ingress_disturbance_mult_raw"]) * float(medium["seal_ingress_scale"]), 6),
        "F_traverse_feasible_medium": bool(medium["traverse_feasible"]),
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "MATERIAL_PHYSICS_PORT_PASS" if not fail else "MATERIAL_PHYSICS_PORT_FAIL",
        "proof_tier": PROOF_TIER,
        "checks": checks,
        "fail": fail,
        "samples": {
            "medium": material_row_trace(variant_id="scout_default_medium"),
            "loose": material_row_trace(variant_id="scout_loose_seal_b3"),
            "dense": material_row_trace(variant_id="scout_dense_wheel"),
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_material_physics_port_smoke(), indent=2))
