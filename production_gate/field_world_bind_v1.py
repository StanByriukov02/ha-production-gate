"""Field world bind v1 — globe → measurable Dual soils + g.

Physics is physics: Mission Moon/Earth/Mars must change the soils body probes feel.
Lat/lon remains pose-only.

TABU: MEASURED GPS · product_ready · invent sinkage from lat/lon.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "fixtures" / "open_registry" / "field" / "ha_field_world_bind_v1.json"


def load_field_bind() -> dict[str, Any]:
    if not _BIND.is_file():
        return {"schema": "ha_field_world_bind_v1", "worlds": {}}
    return json.loads(_BIND.read_text(encoding="utf-8"))


def resolve_globe_row(globe: str | None) -> dict[str, Any] | None:
    key = str(globe or "").strip().lower()
    if not key:
        return None
    worlds = load_field_bind().get("worlds") or {}
    row = worlds.get(key)
    return dict(row) if isinstance(row, dict) else None


def resolve_world_id_row(world_id: str | None) -> dict[str, Any] | None:
    wid = str(world_id or "").strip()
    if not wid:
        return None
    worlds = load_field_bind().get("worlds") or {}
    for globe, row in worlds.items():
        if isinstance(row, dict) and str(row.get("world_id") or "") == wid:
            out = dict(row)
            out["globe"] = globe
            return out
    return None


def dual_soils_for(
    *,
    globe: str | None = None,
    world_id: str | None = None,
    field_bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return measurable Dual soil ids + g for a field lane."""
    row: dict[str, Any] | None = None
    if isinstance(field_bind, dict) and field_bind.get("dual_soils"):
        row = dict(field_bind)
    if row is None:
        row = resolve_globe_row(globe)
    if row is None:
        row = resolve_world_id_row(world_id)
    soils = (row or {}).get("dual_soils") if isinstance(row, dict) else None
    if not isinstance(soils, dict):
        soils = {"safe": "firm_lab", "hostile": "soft_hostile"}
    g = float((row or {}).get("g_mps2") or 9.81)
    return {
        "globe": (row or {}).get("globe") or globe,
        "world_id": (row or {}).get("world_id") or world_id,
        "safe_soil_id": str(soils.get("safe") or "firm_lab"),
        "hostile_soil_id": str(soils.get("hostile") or "soft_hostile"),
        "g_mps2": g,
        "site_pose": (row or {}).get("site_pose"),
        "note": (row or {}).get("note"),
        "honesty": {
            "field_measurable": True,
            "lat_lon_is_pose_only": True,
            "not_measured": True,
            "sim_slice": True,
        },
    }


def physics_pair_for_field(
    *,
    globe: str | None = None,
    world_id: str | None = None,
    field_bind: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Safe/Hostile physics rows via Rust Bekker for this field lane (+ body load)."""
    from production_gate.body_contact_geometry_v1 import (
        bekker_load_from_contact,
        contact_from_body,
    )
    from production_gate.terramech_bekker_on_v1 import physics_row_for_dual

    lane = dual_soils_for(globe=globe, world_id=world_id, field_bind=field_bind)
    if isinstance(field_bind, dict) and field_bind.get("g_mps2") is not None:
        lane["g_mps2"] = float(field_bind["g_mps2"])
    g = float(lane["g_mps2"])
    catalog = None
    if isinstance(field_bind, dict):
        raw_cat = field_bind.get("bekker_catalog") or field_bind.get("catalog")
        if raw_cat:
            catalog = Path(str(raw_cat))
            if not catalog.is_file():
                raise FileNotFoundError(f"bekker_catalog not found: {catalog}")
    contact = contact_from_body(body)
    load = bekker_load_from_contact(contact, g_mps2=g)
    p_kpa = float(load["ground_pressure_kpa"])
    b_m = float(load["contact_width_b_m"])
    area_m2 = float(load["contact_area_m2"])
    safe = physics_row_for_dual(
        str(lane["safe_soil_id"]),
        g_mps2=g,
        ground_pressure_kpa=p_kpa,
        contact_width_b_m=b_m,
        contact_area_m2=area_m2,
        catalog=catalog,
    )
    hostile = physics_row_for_dual(
        str(lane["hostile_soil_id"]),
        g_mps2=g,
        ground_pressure_kpa=p_kpa,
        contact_width_b_m=b_m,
        contact_area_m2=area_m2,
        catalog=catalog,
    )
    # E2: Earth globe attaches Terzaghi + wind Dual (not lunar theater alone).
    from production_gate.earth_lane_embed_v1 import attach_earth_lane_to_physics, is_earth_globe

    if is_earth_globe(lane.get("globe")):
        safe = attach_earth_lane_to_physics(
            safe, condition="safe", ground_pressure_kpa=p_kpa
        )
        hostile = attach_earth_lane_to_physics(
            hostile, condition="hostile", ground_pressure_kpa=p_kpa
        )
    return {
        "lane": lane,
        "contact": contact,
        "load": load,
        "safe": {
            "label": (
                f"Safe · {lane['safe_soil_id']} (Bekker · g={g} · "
                f"p={p_kpa:.1f}kPa · {contact.get('source')}"
                + ("; Earth Terzaghi+wind" if is_earth_globe(lane.get("globe")) else "")
                + ")"
            ),
            "physics": safe,
            "soil_id": lane["safe_soil_id"],
        },
        "hostile": {
            "label": (
                f"Hostile · {lane['hostile_soil_id']} (Bekker · g={g} · "
                f"p={p_kpa:.1f}kPa · {contact.get('source')}"
                + ("; Earth Terzaghi+wind" if is_earth_globe(lane.get("globe")) else "")
                + ")"
            ),
            "physics": hostile,
            "soil_id": lane["hostile_soil_id"],
        },
    }
