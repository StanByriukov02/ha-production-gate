"""Owned Dual soils — stranger Safe/Hostile params as a first-class input.

Schema: ha_dual_owned_soils_v1
  - safe / hostile soil ids (in embedded soils or Bekker catalog)
  - optional embedded soils map (merged into a runtime catalog for Rust)
  - optional catalog path (full bekker_soils catalog)
  - optional contact (mass / pads) — shown on the Dual board

TABU: claim MEASURED · invent soil from lat/lon · hide contact defaults.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_CATALOG = (
    _REPO / "fixtures" / "open_registry" / "terramech" / "bekker_soils_on_v1.json"
)
SCHEMA = "ha_dual_owned_soils_v1"
_REQUIRED_SOIL_KEYS = ("n", "kc", "k_phi")
_CONTACT_KEYS = ("mass_kg", "n_contacts", "contact_width_m", "contact_length_m")


def _as_float(v: Any, *, name: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc


def validate_soil_row(soil_id: str, row: dict[str, Any]) -> None:
    if not isinstance(row, dict):
        raise ValueError(f"soils[{soil_id!r}] must be an object")
    for key in _REQUIRED_SOIL_KEYS:
        if key not in row:
            raise ValueError(f"soils[{soil_id!r}] missing {key}")
        _as_float(row[key], name=f"soils[{soil_id}].{key}")
    shear = row.get("shear")
    if shear is not None and not isinstance(shear, dict):
        raise ValueError(f"soils[{soil_id!r}].shear must be an object when present")


def load_owned_soils(path: str | Path) -> dict[str, Any]:
    """Load and validate a Dual owned-soils pack."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"owned soils not found: {p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("owned soils root must be a JSON object")
    schema = str(doc.get("schema") or "").strip()
    if schema and schema != SCHEMA:
        raise ValueError(f"expected schema={SCHEMA!r}, got {schema!r}")
    safe = str(doc.get("safe") or doc.get("safe_soil_id") or "").strip()
    hostile = str(doc.get("hostile") or doc.get("hostile_soil_id") or "").strip()
    if not safe or not hostile:
        raise ValueError("owned soils require safe and hostile soil ids")
    if safe == hostile:
        raise ValueError("safe and hostile soil ids must differ")

    soils = doc.get("soils")
    if soils is None:
        soils = {}
    if not isinstance(soils, dict):
        raise ValueError("soils must be an object when present")
    for sid, row in soils.items():
        validate_soil_row(str(sid), row if isinstance(row, dict) else {})

    contact = doc.get("contact")
    if contact is not None and not isinstance(contact, dict):
        raise ValueError("contact must be an object when present")
    contact_out: dict[str, float] | None = None
    if isinstance(contact, dict):
        contact_out = {}
        for key in _CONTACT_KEYS:
            if contact.get(key) is not None:
                contact_out[key] = _as_float(contact[key], name=f"contact.{key}")
        if contact_out and set(contact_out) != set(_CONTACT_KEYS):
            missing = set(_CONTACT_KEYS) - set(contact_out)
            raise ValueError(f"contact missing keys: {sorted(missing)}")

    catalog_rel = doc.get("catalog")
    catalog_path: Path | None = None
    if catalog_rel:
        cand = Path(str(catalog_rel)).expanduser()
        if not cand.is_file():
            cand = (p.parent / catalog_rel).resolve()
        if not cand.is_file():
            cand = (_REPO / catalog_rel).resolve()
        if not cand.is_file():
            raise FileNotFoundError(f"catalog not found: {catalog_rel}")
        catalog_path = cand

    g = _as_float(doc.get("g_mps2") or 9.81, name="g_mps2")
    out = {
        "schema": SCHEMA,
        "path": str(p),
        "safe_soil_id": safe,
        "hostile_soil_id": hostile,
        "g_mps2": g,
        "soils": soils,
        "contact": contact_out,
        "catalog_path": str(catalog_path) if catalog_path else None,
        "label": doc.get("label"),
        "honesty": doc.get("honesty")
        if isinstance(doc.get("honesty"), dict)
        else {"not_measured": True, "owned_by_stranger": True},
    }
    return out


def materialize_bekker_catalog(pack: dict[str, Any], *, out_dir: Path) -> Path:
    """Write a Bekker catalog the Rust oracle can eval (default + embedded soils)."""
    base_path = Path(pack["catalog_path"]) if pack.get("catalog_path") else _DEFAULT_CATALOG
    base = json.loads(base_path.read_text(encoding="utf-8"))
    if not isinstance(base.get("soils"), dict):
        base["soils"] = {}
    embedded = pack.get("soils") or {}
    if embedded:
        merged = dict(base["soils"])
        merged.update(embedded)
        base["soils"] = merged
        base["owned_soils_overlay"] = {
            "schema": SCHEMA,
            "source": pack.get("path"),
            "ids": sorted(embedded.keys()),
        }

    safe = pack["safe_soil_id"]
    hostile = pack["hostile_soil_id"]
    soils = base["soils"]
    if safe not in soils:
        raise ValueError(
            f"safe soil_id={safe!r} not in catalog (embedded or {base_path.name})"
        )
    if hostile not in soils:
        raise ValueError(
            f"hostile soil_id={hostile!r} not in catalog (embedded or {base_path.name})"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "owned_bekker_catalog_v1.json"
    dest.write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def field_bind_from_pack(pack: dict[str, Any], *, catalog_path: Path) -> dict[str, Any]:
    """Body field_bind so Dual uses owned Safe/Hostile + catalog."""
    return {
        "schema": SCHEMA,
        "dual_soils": {
            "safe": pack["safe_soil_id"],
            "hostile": pack["hostile_soil_id"],
        },
        "g_mps2": pack["g_mps2"],
        "bekker_catalog": str(catalog_path),
        "owned_soils_path": pack.get("path"),
        "label": pack.get("label"),
        "honesty": pack.get("honesty"),
    }


def apply_owned_pack_to_project(project_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Materialize catalog, bind soils + optional contact onto the project body."""
    from production_gate.robot_project_desk_v1 import (
        get_project,
        update_project_field_lane,
        _save_project,
    )

    runtime = _REPO / "results" / "runtime" / "owned_soils"
    catalog = materialize_bekker_catalog(pack, out_dir=runtime)
    from production_gate.terramech_bekker_on_v1 import set_bekker_catalog_override

    set_bekker_catalog_override(catalog)
    field_bind = field_bind_from_pack(pack, catalog_path=catalog)
    update_project_field_lane(
        project_id,
        world_id="owned_soils",
        globe=None,
        field_bind=field_bind,
    )
    contact = pack.get("contact")
    if not contact:
        return {
            "catalog_path": str(catalog),
            "field_bind": field_bind,
            "contact": None,
        }

    doc = get_project(project_id)
    body = dict(doc.get("body") or {})
    for key, val in contact.items():
        body[key] = float(val)
    body["owned_contact"] = True
    doc["body"] = body
    _save_project(doc)
    return {
        "catalog_path": str(catalog),
        "field_bind": field_bind,
        "contact": dict(contact),
    }
