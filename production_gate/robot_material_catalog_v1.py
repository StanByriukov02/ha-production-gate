"""Robot material catalog v1 — registry materials + variants + seal taxonomy.

Single resolver for MaterialPhysicsPort · wear matrix · sweep · twin HUD.
TABU: ADAPT variant ≠ MEASURED field · dual-slot B2 env vs B3 physics is documented not hidden.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from production_gate.open_seed_paths_v1 import dust_ingress_bind_path, materials_registry_path

_REPO = Path(__file__).resolve().parents[1]
_ADAPT_TREAD = _REPO / "fixtures" / "robot" / "robot_material_adapt_tread_v1.json"

PROOF_TIER = "ROBOT_MATERIAL_CATALOG_SLICE"

TREAD_VARIANT_SLOT_ID = "ROBOT_WHEEL_TREAD_VARIANT"
DEFAULT_TREAD_MATERIAL_ID = "pu_ester_shore_90a"

_TREAD_ALIASES = {
    "pu_shore_70a": "pu_ester_shore_70a",
    "pu_shore_90a": "pu_ester_shore_90a",
    "pu_shore_95a": "pu_ester_shore_95a",
}

# Factory tread slot → material_physics_bind variant (wheel_tread scenarios only)
_TREAD_SLOT_BIND_VARIANT: dict[str, str] = {
    "pu_ester_shore_70a": "scout_tread_shore_70a",
    "pu_ester_shore_90a": "scout_default_medium",
    "pu_ester_shore_95a": "scout_tread_shore_95a",
}


def _rel(path: Path) -> str:
    return str(path.relative_to(_REPO)).replace("\\", "/")


def read_factory_slot_value(slot_id: str) -> Any | None:
    from production_gate.robot_factory_slots_v1 import load_slots

    row = (load_slots().get("slots") or {}).get(slot_id) or {}
    return row.get("value")


def read_active_tread_material_id(*, registry: dict[str, Any] | None = None) -> str:
    slot_val = read_factory_slot_value(TREAD_VARIANT_SLOT_ID)
    if slot_val:
        return normalize_tread_key(str(slot_val))
    reg = registry or load_materials_registry()
    active = reg.get("active_selection") or {}
    return str(active.get("wheel_tread") or DEFAULT_TREAD_MATERIAL_ID)


def resolve_effective_material_variant_id(
    variant_id: str,
    *,
    registry: dict[str, Any] | None = None,
) -> str:
    """Remap default-medium only; other variants get tread overlay in port."""
    tread_mat = read_active_tread_material_id(registry=registry)
    if tread_mat == DEFAULT_TREAD_MATERIAL_ID:
        return variant_id
    if variant_id == "scout_default_medium":
        return _TREAD_SLOT_BIND_VARIANT.get(tread_mat, variant_id)
    return variant_id


def promote_active_tread_variant(
    material_id: str,
    *,
    write: bool = True,
) -> dict[str, Any]:
    """Promote tread to factory slot + registry active_selection (ADAPT or CITED)."""
    from production_gate.robot_factory_slots_v1 import load_slots, save_slots, set_slot

    reg = load_materials_registry()
    canon = normalize_tread_key(material_id)
    primary = (reg.get("materials") or {}).get("wheel_tread") or {}
    variants = get_wheel_tread_variants(reg)
    if canon != primary.get("material_id") and canon not in variants:
        raise KeyError(f"unknown tread material for promote: {material_id}")

    tier = str(primary.get("tier") if canon == primary.get("material_id") else (variants[canon].get("tier") or "ADAPT"))

    active = dict(reg.get("active_selection") or {})
    active["wheel_tread"] = canon
    reg["active_selection"] = active

    data = load_slots()
    set_slot(
        data,
        slot_id=TREAD_VARIANT_SLOT_ID,
        rung="R1",
        value=canon,
        unit="material_id",
        tier=tier,
        environment_id="earth_lab_298k",
        bind=_rel(materials_registry_path(_REPO)),
        formula=f"promoted tread variant · bind maps to {_TREAD_SLOT_BIND_VARIANT.get(canon, 'scout_default_medium')}",
    )

    if write:
        materials_registry_path(_REPO).write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
        save_slots(data)

    return {
        "material_id": canon,
        "tier": tier,
        "bind_variant": resolve_effective_material_variant_id("scout_default_medium", registry=reg),
        "slot_id": TREAD_VARIANT_SLOT_ID,
    }


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_materials_registry() -> dict[str, Any]:
    path = materials_registry_path(_REPO)
    if not path.is_file():
        raise FileNotFoundError(path)
    return _load(path)


def load_dust_bind() -> dict[str, Any]:
    path = dust_ingress_bind_path(_REPO)
    if not path.is_file():
        return {}
    return _load(path)


def _fallback_seal_catalog() -> dict[str, Any]:
    dust = load_dust_bind()
    classes = dust.get("seal_classes") or {}
    ids = {
        "B1": "nbr_fully_sealed_oem_b1",
        "B2": "labyrinth_wiper_b2",
        "B3": "nbr_lip_seal_b3",
        "B4": "minimal_cover_b4",
        "B5": "open_joint_b5",
    }
    dust_p = dust_ingress_bind_path(_REPO)
    out: dict[str, Any] = {}
    for cls, row in classes.items():
        bind = _rel(dust_p) if dust_p.is_file() else "fixtures/open_seed/"
        out[cls] = {
            "material_id": ids.get(cls, f"seal_{cls.lower()}"),
            "seal_class": cls,
            "ingress_scale": float(row.get("ingress_scale") or 1.0),
            "label": str(row.get("label") or cls),
            "tier": "CITED_BIND" if cls == "B3" else "ADAPT",
            "bind": bind,
        }
    return out


def get_seal_catalog(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = registry or load_materials_registry()
    catalog = reg.get("seal_catalog")
    if isinstance(catalog, dict) and catalog:
        return catalog
    return _fallback_seal_catalog()


def get_wheel_tread_variants(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = registry or load_materials_registry()
    variants = (reg.get("material_variants") or {}).get("wheel_tread") or {}
    if variants:
        return dict(variants)
    if _ADAPT_TREAD.is_file():
        doc = _load(_ADAPT_TREAD)
        profiles = doc.get("profiles") or {}
        mapped: dict[str, Any] = {}
        for key, prof in profiles.items():
            mat_id = str(prof.get("material_id") or key)
            canon = _TREAD_ALIASES.get(key, mat_id)
            mapped[canon] = {**prof, "material_id": mat_id, "tier": "ADAPT"}
        return mapped
    return {}


def normalize_tread_key(profile_key: str) -> str:
    return _TREAD_ALIASES.get(profile_key, profile_key)


def resolve_tread_variant(profile_key: str, *, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    canon = normalize_tread_key(profile_key)
    variants = get_wheel_tread_variants(registry)
    if canon in variants:
        return dict(variants[canon])
    reg = registry or load_materials_registry()
    base = (reg.get("materials") or {}).get("wheel_tread") or {}
    if canon == base.get("material_id"):
        geo = reg.get("geometry_assumptions") or {}
        return {
            **base,
            "wheel_width_cm": float(geo.get("wheel_width_cm") or 8.0),
            "wheel_diameter_cm": float(geo.get("wheel_diameter_cm") or 20.0),
            "ingress_mult_factor": 1.0,
        }
    raise KeyError(f"unknown tread variant: {profile_key}")


def resolve_seal_entry(seal_class: str, *, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = get_seal_catalog(registry)
    if seal_class not in catalog:
        raise KeyError(f"unknown seal class: {seal_class}")
    return dict(catalog[seal_class])


def resolve_seal_scale(seal_class: str, *, registry: dict[str, Any] | None = None) -> tuple[float, str, str]:
    entry = resolve_seal_entry(seal_class, registry=registry)
    return (
        float(entry.get("ingress_scale") or 1.0),
        str(entry.get("label") or seal_class),
        str(entry.get("material_id") or seal_class),
    )


def resolve_wheel_geometry(
    *,
    tread_material_id: str | None = None,
    tread_profile: str | None = None,
    registry: dict[str, Any] | None = None,
) -> tuple[float, float, float, dict[str, Any]]:
    reg = registry or load_materials_registry()
    geo = reg.get("geometry_assumptions") or {}
    mass_kg = float((reg.get("mass_ledger_anchor") or {}).get("total_kg") or 50.0)
    wheel_d = float(geo.get("wheel_diameter_cm") or 20.0)
    wheel_w = float(geo.get("wheel_width_cm") or 8.0)
    tread_meta: dict[str, Any] = {}

    key = tread_profile or tread_material_id
    if key:
        prof = resolve_tread_variant(str(key), registry=reg)
        wheel_d = float(prof.get("wheel_diameter_cm") or wheel_d)
        wheel_w = float(prof.get("wheel_width_cm") or wheel_w)
        tread_meta = prof
    elif tread_material_id:
        variants = get_wheel_tread_variants(reg)
        if tread_material_id in variants:
            prof = variants[tread_material_id]
            wheel_d = float(prof.get("wheel_diameter_cm") or wheel_d)
            wheel_w = float(prof.get("wheel_width_cm") or wheel_w)
            tread_meta = prof

    return mass_kg, wheel_d, wheel_w, tread_meta


def get_active_selection(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = registry or load_materials_registry()
    active = reg.get("active_selection") or {}
    joint = (reg.get("materials") or {}).get("joint_seal") or {}
    tread = (reg.get("materials") or {}).get("wheel_tread") or {}
    return {
        "wheel_tread_material_id": active.get("wheel_tread") or tread.get("material_id"),
        "joint_seal_physics_class": active.get("joint_seal_physics") or joint.get("seal_class") or "B3",
        "env_dust_seal_class": active.get("env_dust_seal") or "B2",
        "semantics": active.get("semantics")
        or "B3 articulation lip seal on physics bus · B2 LSIC labyrinth on enclosure env slot",
    }


def catalog_summary(*, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = registry or load_materials_registry()
    tread_variants = get_wheel_tread_variants(reg)
    seal_catalog = get_seal_catalog(reg)
    return {
        "proof_tier": PROOF_TIER,
        "registry_id": reg.get("registry_id"),
        "primary_materials": list((reg.get("materials") or {}).keys()),
        "tread_variant_count": len(tread_variants),
        "tread_variants": list(tread_variants.keys()),
        "seal_classes": list(seal_catalog.keys()),
        "active_selection": get_active_selection(reg),
    }


def run_material_catalog_smoke() -> dict[str, Any]:
    reg = load_materials_registry()
    soft = resolve_tread_variant("pu_shore_70a", registry=reg)
    hard = resolve_tread_variant("pu_shore_95a", registry=reg)
    b2_scale, b2_label, b2_id = resolve_seal_scale("B2", registry=reg)
    b3_scale, _, _ = resolve_seal_scale("B3", registry=reg)
    active = get_active_selection(reg)
    checks = {
        "F_registry_loads": bool(reg.get("materials")),
        "F_tread_variants_present": len(get_wheel_tread_variants(reg)) >= 2,
        "F_soft_wider_than_hard": float(soft.get("wheel_width_cm") or 0) > float(hard.get("wheel_width_cm") or 0),
        "F_seal_b2_lt_b3_scale": b2_scale < b3_scale,
        "F_dual_slot_documented": "B2" in str(active.get("env_dust_seal_class") or active.get("semantics", "")),
        "F_seal_catalog_five_classes": len(get_seal_catalog(reg)) >= 5,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "ROBOT_MATERIAL_CATALOG_PASS" if not fail else "ROBOT_MATERIAL_CATALOG_FAIL",
        "checks": checks,
        "fail": fail,
        "summary": catalog_summary(registry=reg),
        "samples": {"b2": {"scale": b2_scale, "label": b2_label, "material_id": b2_id}},
    }


if __name__ == "__main__":
    print(json.dumps(run_material_catalog_smoke(), indent=2))
