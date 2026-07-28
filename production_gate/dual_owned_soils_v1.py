"""Owned Dual soils — stranger Safe/Hostile params as a first-class input.

Schema: ha_dual_owned_soils_v1
  - safe / hostile soil ids (must be embedded in pack.soils — not silent teaching catalog)
  - embedded soils map (merged into a runtime catalog for Rust)
  - optional catalog path (full bekker_soils catalog)
  - optional contact (mass / pads) — shown on the Dual board

TABU: claim MEASURED · invent soil from lat/lon · hide contact defaults ·
      use firm_lab/soft_hostile as «мои» owned ids.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_CATALOG = (
    _REPO / "fixtures" / "open_registry" / "terramech" / "bekker_soils_on_v1.json"
)
SCHEMA = "ha_dual_owned_soils_v1"
_REQUIRED_SOIL_KEYS = ("n", "kc", "k_phi")
_REQUIRED_SHEAR_KEYS = ("c_kpa", "phi_deg", "K_m")
_CONTACT_KEYS = ("mass_kg", "n_contacts", "contact_width_m", "contact_length_m")

# Teaching catalog ids — forbidden as owned Dual safe/hostile (no silent «мои»).
TEACHING_SOIL_IDS = frozenset({"firm_lab", "soft_hostile"})


def _as_float(v: Any, *, name: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc


def _default_shear(*, soft: bool = False) -> dict[str, Any]:
    if soft:
        return {
            "role": "teaching_janosi_hanamoto",
            "c_kpa": 0.5,
            "phi_deg": 15.0,
            "K_m": 0.04,
            "j_m_default": 0.05,
            "note": "owned teaching shear — not MEASURED",
        }
    return {
        "role": "teaching_janosi_hanamoto",
        "c_kpa": 3.0,
        "phi_deg": 30.0,
        "K_m": 0.02,
        "j_m_default": 0.05,
        "note": "owned teaching shear — not MEASURED",
    }


def validate_soil_row(soil_id: str, row: dict[str, Any], *, require_shear: bool = True) -> None:
    if not isinstance(row, dict):
        raise ValueError(f"soils[{soil_id!r}] must be an object")
    for key in _REQUIRED_SOIL_KEYS:
        if key not in row:
            raise ValueError(f"soils[{soil_id!r}] missing {key}")
        _as_float(row[key], name=f"soils[{soil_id}].{key}")
    shear = row.get("shear")
    if shear is None:
        if require_shear:
            raise ValueError(f"soils[{soil_id!r}] missing shear (c_kpa, phi_deg, K_m)")
        return
    if not isinstance(shear, dict):
        raise ValueError(f"soils[{soil_id!r}].shear must be an object when present")
    if require_shear:
        for key in _REQUIRED_SHEAR_KEYS:
            if key not in shear:
                raise ValueError(f"soils[{soil_id!r}].shear missing {key}")
            _as_float(shear[key], name=f"soils[{soil_id}].shear.{key}")


def _reject_teaching_owned_ids(safe: str, hostile: str) -> None:
    for sid, role in ((safe, "safe"), (hostile, "hostile")):
        if sid in TEACHING_SOIL_IDS:
            raise ValueError(
                f"owned Dual {role} soil_id={sid!r} is a teaching catalog id — "
                "not allowed as «мои». Use make_owned_soils_template() / ha-soils template."
            )


def make_owned_soils_template(
    *,
    safe_id: str = "my_firm",
    hostile_id: str = "my_soft",
    g_mps2: float = 9.81,
    label: str | None = None,
) -> dict[str, Any]:
    """Blank owned Dual pack — edit numbers; ids are yours, not firm_lab."""
    safe_id = str(safe_id).strip()
    hostile_id = str(hostile_id).strip()
    if not safe_id or not hostile_id:
        raise ValueError("safe_id and hostile_id required")
    if safe_id == hostile_id:
        raise ValueError("safe_id and hostile_id must differ")
    _reject_teaching_owned_ids(safe_id, hostile_id)
    return {
        "schema": SCHEMA,
        "label": label
        or "Owned Dual soils — edit n/kc/k_phi/shear (not MEASURED)",
        "g_mps2": float(g_mps2),
        "safe": safe_id,
        "hostile": hostile_id,
        "soils": {
            safe_id: {
                "label": f"{safe_id} (edit me)",
                "role": "owned_safe",
                "n": 1.0,
                "kc": 40.0,
                "k_phi": 2000.0,
                "shear": _default_shear(soft=False),
                "note": "owned Safe — replace with your numbers",
            },
            hostile_id: {
                "label": f"{hostile_id} (edit me)",
                "role": "owned_hostile",
                "n": 0.8,
                "kc": 5.0,
                "k_phi": 80.0,
                "shear": _default_shear(soft=True),
                "note": "owned Hostile — replace with your numbers",
            },
        },
        "honesty": {
            "not_measured": True,
            "owned_by_stranger": True,
            "not_teaching_catalog_ids": True,
        },
    }


def duplicate_soil(
    pack: dict[str, Any],
    *,
    source_id: str,
    new_id: str,
    set_as: str | None = None,
) -> dict[str, Any]:
    """Copy one embedded soil row to a new id. Optional set_as='safe'|'hostile'."""
    if not isinstance(pack, dict):
        raise ValueError("pack must be an object")
    soils = pack.get("soils")
    if not isinstance(soils, dict):
        raise ValueError("pack.soils must be an object")
    src = str(source_id).strip()
    dst = str(new_id).strip()
    if not src or not dst:
        raise ValueError("source_id and new_id required")
    if dst in TEACHING_SOIL_IDS:
        raise ValueError(f"new_id={dst!r} is a teaching catalog id — forbidden")
    if src not in soils:
        raise ValueError(f"source soil_id={src!r} not in pack.soils")
    if dst in soils:
        raise ValueError(f"new_id={dst!r} already exists")
    out = copy.deepcopy(pack)
    out.setdefault("schema", SCHEMA)
    row = copy.deepcopy(out["soils"][src])
    if isinstance(row, dict):
        row["label"] = f"{dst} (duplicated from {src})"
        row["note"] = f"duplicated from {src} — edit me"
    out["soils"][dst] = row
    if set_as == "safe":
        out["safe"] = dst
    elif set_as == "hostile":
        out["hostile"] = dst
    elif set_as is not None:
        raise ValueError("set_as must be 'safe', 'hostile', or None")
    return out


def dump_owned_soils_pack(pack: dict[str, Any]) -> str:
    """Serialize pack for download / CLI write."""
    doc = dict(pack)
    doc["schema"] = SCHEMA
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def load_owned_soils(path: str | Path) -> dict[str, Any]:
    """Load and validate a Dual owned-soils pack."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"owned soils not found: {p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    return parse_owned_soils_doc(doc, path=str(p))


def parse_owned_soils_doc(doc: dict[str, Any], *, path: str | None = None) -> dict[str, Any]:
    """Validate owned soils JSON object (file or desk editor)."""
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
    _reject_teaching_owned_ids(safe, hostile)

    soils = doc.get("soils")
    if soils is None:
        soils = {}
    if not isinstance(soils, dict):
        raise ValueError("soils must be an object when present")
    if safe not in soils or hostile not in soils:
        raise ValueError(
            "owned pack must embed soils[safe] and soils[hostile] — "
            "cannot silently bind teaching catalog ids"
        )
    for sid, row in soils.items():
        validate_soil_row(str(sid), row if isinstance(row, dict) else {}, require_shear=True)

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
            base = Path(path).parent if path else Path.cwd()
            cand = (base / catalog_rel).resolve()
        if not cand.is_file():
            cand = (_REPO / catalog_rel).resolve()
        if not cand.is_file():
            raise FileNotFoundError(f"catalog not found: {catalog_rel}")
        catalog_path = cand

    g = _as_float(doc.get("g_mps2") or 9.81, name="g_mps2")
    return {
        "schema": SCHEMA,
        "path": path,
        "safe_soil_id": safe,
        "hostile_soil_id": hostile,
        "g_mps2": g,
        "soils": soils,
        "contact": contact_out,
        "catalog_path": str(catalog_path) if catalog_path else None,
        "label": doc.get("label"),
        "honesty": doc.get("honesty")
        if isinstance(doc.get("honesty"), dict)
        else {
            "not_measured": True,
            "owned_by_stranger": True,
            "not_teaching_catalog_ids": True,
        },
    }


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
    body["contact_override"] = True
    doc["body"] = body
    _save_project(doc)
    return {
        "catalog_path": str(catalog),
        "field_bind": field_bind,
        "contact": dict(contact),
    }
