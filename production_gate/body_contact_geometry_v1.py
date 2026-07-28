"""Body contact geometry v1 — map attached body → Bekker p_kpa / b_m.

Resolve order (honesty labels):
  1. override:*     — owned_contact / contact_override / explicit body fields
  2. urdf_extract   — complete extract from URDF inertials + wheel/track/foot primitives
  3. catalog|preset|kind|default — teaching profiles

TABU: claim MEASURED wheel load · product_ready · invent soil from body alone ·
      rename teaching pads as urdf_extract.
"""
from __future__ import annotations

from typing import Any

# Teaching contact profiles — mass / pad size by kind (sim_slice)
_KIND_CONTACT: dict[str, dict[str, float]] = {
    "bench": {
        "mass_kg": 18.0,
        "n_contacts": 1.0,
        "contact_width_m": 0.05,
        "contact_length_m": 0.08,
    },
    "appendage": {
        "mass_kg": 9.0,
        "n_contacts": 1.0,
        "contact_width_m": 0.028,
        "contact_length_m": 0.035,
    },
    "end_effector": {
        "mass_kg": 2.8,
        "n_contacts": 2.0,
        "contact_width_m": 0.012,
        "contact_length_m": 0.04,
    },
    "chassis": {
        "mass_kg": 95.0,
        "n_contacts": 4.0,
        "contact_width_m": 0.09,
        "contact_length_m": 0.14,
    },
    "arm": {
        "mass_kg": 22.0,
        "n_contacts": 1.0,
        "contact_width_m": 0.10,
        "contact_length_m": 0.12,
    },
    "wheeled_base": {
        "mass_kg": 48.0,
        "n_contacts": 4.0,
        "contact_width_m": 0.055,
        "contact_length_m": 0.09,
    },
    "hexapod": {
        "mass_kg": 36.0,
        "n_contacts": 3.0,
        "contact_width_m": 0.025,
        "contact_length_m": 0.03,
    },
    "default": {
        "mass_kg": 25.0,
        "n_contacts": 2.0,
        "contact_width_m": 0.04,
        "contact_length_m": 0.06,
    },
}

_CATALOG_CONTACT: dict[str, dict[str, float]] = {
    "lc2_bench_1dof_v1": dict(_KIND_CONTACT["bench"]),
    "hexapod_leg_3dof_v1": {
        "mass_kg": 7.5,
        "n_contacts": 1.0,
        "contact_width_m": 0.022,
        "contact_length_m": 0.028,
    },
    "gripper_parallel_1dof_v1": dict(_KIND_CONTACT["end_effector"]),
    "head_neck_pan_tilt_v1": {
        "mass_kg": 4.0,
        "n_contacts": 1.0,
        "contact_width_m": 0.03,
        "contact_length_m": 0.03,
    },
    "torso_spine_2dof_v1": {
        "mass_kg": 28.0,
        "n_contacts": 1.0,
        "contact_width_m": 0.08,
        "contact_length_m": 0.12,
    },
    "prismatic_slide_v1": {
        "mass_kg": 14.0,
        "n_contacts": 1.0,
        "contact_width_m": 0.05,
        "contact_length_m": 0.1,
    },
    "lc2_combat_carrier_4wd_v1": dict(_KIND_CONTACT["chassis"]),
}

_PRESET_CONTACT: dict[str, dict[str, float]] = {
    "open_rrbot": dict(_KIND_CONTACT["arm"]),
    "open_diffbot": dict(_KIND_CONTACT["wheeled_base"]),
    "lunar_scout": dict(_KIND_CONTACT["hexapod"]),
    "earth_bench": dict(_KIND_CONTACT["bench"]),
}

_CONTACT_KEYS = ("mass_kg", "n_contacts", "contact_width_m", "contact_length_m")


def _as_contact(row: dict[str, float]) -> dict[str, float]:
    return {
        "mass_kg": float(row["mass_kg"]),
        "n_contacts": float(row["n_contacts"]),
        "contact_width_m": float(row["contact_width_m"]),
        "contact_length_m": float(row["contact_length_m"]),
    }


def _pack(row: dict[str, float], src: str, honesty: dict[str, Any]) -> dict[str, Any]:
    contact = _as_contact(row)
    area = (
        contact["n_contacts"]
        * contact["contact_width_m"]
        * contact["contact_length_m"]
    )
    return {
        **contact,
        "contact_area_m2": area,
        "source": src,
        "honesty": honesty,
    }


def _teaching_row(body: dict[str, Any]) -> tuple[dict[str, float], str]:
    catalog_id = str(body.get("catalog_id") or "").strip()
    preset_id = str(body.get("preset_id") or "").strip()
    kind = str(body.get("model_kind") or body.get("kind") or "").strip().lower()

    if catalog_id and catalog_id in _CATALOG_CONTACT:
        return dict(_CATALOG_CONTACT[catalog_id]), f"catalog:{catalog_id}"
    if preset_id and preset_id in _PRESET_CONTACT:
        return dict(_PRESET_CONTACT[preset_id]), f"preset:{preset_id}"
    if kind in _KIND_CONTACT:
        return dict(_KIND_CONTACT[kind]), f"kind:{kind}"
    if "diffbot" in str(body.get("label") or "").lower():
        return dict(_KIND_CONTACT["wheeled_base"]), "label:diffbot"
    if "rrbot" in str(body.get("label") or "").lower():
        return dict(_KIND_CONTACT["arm"]), "label:rrbot"
    return dict(_KIND_CONTACT["default"]), "default"


def contact_from_body(body: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve contact geometry with honest source labels."""
    body = body if isinstance(body, dict) else {}

    # 1) Explicit override (soils pack / CLI / contact_override)
    if body.get("owned_contact") or body.get("contact_override"):
        row, teach_src = _teaching_row(body)
        for key in _CONTACT_KEYS:
            if body.get(key) is not None:
                row[key] = float(body[key])
        src = "override:owned" if body.get("owned_contact") else "override:explicit"
        return _pack(
            row,
            src,
            {
                "teaching_geometry": False,
                "not_measured": True,
                "override": True,
                "teach_fallback_base": teach_src,
            },
        )

    # 2) Complete URDF extract
    urdf_c = body.get("urdf_contact")
    if isinstance(urdf_c, dict) and urdf_c.get("complete"):
        row = {
            "mass_kg": float(urdf_c["mass_kg"]),
            "n_contacts": float(urdf_c["n_contacts"]),
            "contact_width_m": float(urdf_c["contact_width_m"]),
            "contact_length_m": float(urdf_c["contact_length_m"]),
        }
        return _pack(
            row,
            "urdf_extract",
            {
                "teaching_geometry": False,
                "not_measured": True,
                "not_cad_inertia": True,
                "urdf_extract": True,
                "not_measured_contact_patch": True,
            },
        )

    # 3) Teaching (+ legacy top-level field patches → override:body)
    row, src = _teaching_row(body)
    if any(body.get(k) is not None for k in _CONTACT_KEYS):
        for key in _CONTACT_KEYS:
            if body.get(key) is not None:
                row[key] = float(body[key])
        src = "override:body"
    return _pack(
        row,
        src,
        {
            "teaching_geometry": not src.startswith("override:"),
            "not_measured": True,
            "not_cad_inertia": True,
        },
    )


def bekker_load_from_contact(
    contact: dict[str, Any],
    *,
    g_mps2: float = 9.81,
) -> dict[str, float]:
    """Convert contact geometry + g → Bekker ground pressure and width."""
    mass = float(contact["mass_kg"])
    area = float(contact["contact_area_m2"])
    if area <= 1e-9:
        area = 1e-4
    force_n = mass * float(g_mps2)
    p_pa = force_n / area
    p_kpa = p_pa / 1000.0
    b_m = float(contact["contact_width_m"])
    return {
        "ground_pressure_kpa": p_kpa,
        "contact_width_b_m": b_m,
        "contact_area_m2": area,
        "force_n": force_n,
        "g_mps2": float(g_mps2),
    }
