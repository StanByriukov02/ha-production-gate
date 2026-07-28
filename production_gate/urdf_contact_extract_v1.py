"""URDF → Bekker contact fields (mass + pad heuristic).

Honesty: soft extract from URDF inertials + primitive geom on wheel/track/foot
links. Not MEASURED contact patch. Not mesh inertia truth. Not CAD certified.

complete=True only when mass_kg>0 and ≥1 contact primitive resolved.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_CONTACT_NAME = re.compile(
    r"(wheel|track|foot|pad|caster|tire|skid)",
    re.IGNORECASE,
)

# Bekker contact_length along roll — fraction of wheel radius (teaching patch).
_PATCH_LEN_FROM_RADIUS = 0.35


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _child(el: ET.Element, name: str) -> ET.Element | None:
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _local(c.tag) == name]


def _attr_float(el: ET.Element | None, key: str, default: float | None = None) -> float | None:
    if el is None:
        return default
    raw = el.attrib.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return float(raw)


def _geom_pad(geom: ET.Element) -> tuple[float, float] | None:
    """Return (contact_width_m, contact_length_m) from a primitive geometry node."""
    cyl = _child(geom, "cylinder")
    if cyl is not None:
        radius = _attr_float(cyl, "radius")
        length = _attr_float(cyl, "length")
        if radius is None or length is None or radius <= 0 or length <= 0:
            return None
        # URDF cylinder axis = Z; wheel visuals usually roll so length ≈ width.
        width = float(length)
        patch = max(float(radius) * _PATCH_LEN_FROM_RADIUS, 1e-4)
        return width, patch

    sphere = _child(geom, "sphere")
    if sphere is not None:
        radius = _attr_float(sphere, "radius")
        if radius is None or radius <= 0:
            return None
        d = 2.0 * float(radius)
        return d, d

    box = _child(geom, "box")
    if box is not None:
        size = (box.attrib.get("size") or "").strip().split()
        if len(size) != 3:
            return None
        sx, sy, sz = (float(size[0]), float(size[1]), float(size[2]))
        # Footprint: two largest horizontal-ish dims (drop the smallest = height guess).
        dims = sorted((sx, sy, sz))
        return float(dims[1]), float(dims[2])

    return None


def _link_pad(link: ET.Element) -> tuple[float, float] | None:
    """Prefer collision primitives; fall back to visual if collision missing/mesh-only."""
    for coll in _children(link, "collision"):
        geom = _child(coll, "geometry")
        if geom is None:
            continue
        pad = _geom_pad(geom)
        if pad is not None:
            return pad
    for vis in _children(link, "visual"):
        geom = _child(vis, "geometry")
        if geom is None:
            continue
        pad = _geom_pad(geom)
        if pad is not None:
            return pad
    return None


def _is_contact_link(name: str) -> bool:
    return bool(_CONTACT_NAME.search(name or ""))


def extract_contact_from_urdf(urdf_path: str | Path) -> dict[str, Any]:
    """Parse URDF → contact dict. complete=False when mass or pads missing."""
    path = Path(urdf_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"urdf not found: {path}")

    root = ET.parse(path).getroot()
    mass_sum = 0.0
    mass_links = 0
    pads: list[dict[str, Any]] = []

    for link in root.iter():
        if _local(link.tag) != "link":
            continue
        name = str(link.attrib.get("name") or "")
        inertial = _child(link, "inertial")
        if inertial is not None:
            mass_el = _child(inertial, "mass")
            m = _attr_float(mass_el, "value")
            if m is not None and m > 0:
                mass_sum += float(m)
                mass_links += 1
        if _is_contact_link(name):
            pad = _link_pad(link)
            if pad is not None:
                pads.append(
                    {
                        "link": name,
                        "contact_width_m": pad[0],
                        "contact_length_m": pad[1],
                    }
                )

    complete = mass_sum > 0.0 and len(pads) >= 1
    out: dict[str, Any] = {
        "complete": complete,
        "source": "urdf_extract" if complete else "urdf_extract_incomplete",
        "mass_kg": float(mass_sum) if mass_sum > 0 else None,
        "mass_link_count": mass_links,
        "n_contacts": float(len(pads)) if pads else None,
        "contact_width_m": None,
        "contact_length_m": None,
        "pads": pads,
        "urdf": path.name,
        "honesty": {
            "urdf_extract": True,
            "not_measured_contact_patch": True,
            "not_mesh_inertia_truth": True,
            "visual_fallback_ok": True,
            "patch_len_from_radius": _PATCH_LEN_FROM_RADIUS,
        },
    }
    if pads:
        # Representative pad = mean width/length across contact links.
        out["contact_width_m"] = sum(p["contact_width_m"] for p in pads) / len(pads)
        out["contact_length_m"] = sum(p["contact_length_m"] for p in pads) / len(pads)
    return out
