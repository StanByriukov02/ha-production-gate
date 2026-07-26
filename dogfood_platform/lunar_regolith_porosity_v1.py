"""GAP-MR-02 — regolith porosity φ cite-bound (Sakatani surface + Wieczorek GRAIL crust)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "results" / "platform_bpass" / "moon" / "REGOLITH_THERMAL_BIND_v1.json"

PorosityClass = Literal["surface_loose", "depth_compact", "crustal_bulk"]


def load_porosity_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def porosity_phi(
    *,
    porosity_class: PorosityClass = "surface_loose",
    depth_m: float = 0.15,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return φ snapshot for harness depth class or crustal bulk metadata."""
    data = bind or load_porosity_bind()
    por = data.get("porosity") or {}
    if porosity_class == "crustal_bulk":
        row = por.get("crustal_bulk_grail") or {}
        return {
            "porosity_class": porosity_class,
            "phi": float(row.get("phi") or 0.12),
            "depth_m": depth_m,
            "scale": row.get("scale") or "km_crust",
            "l0_cites": [str(row.get("cite") or "WIECZOREK-HAL-L0-01")],
            "oracle": str(data.get("oracle") or "CITED_BIND"),
        }
    key = "surface_loose" if porosity_class == "surface_loose" else "depth_compact"
    row = por.get(key) or {}
    d_scale_km = float(por.get("e_folding_depth_km") or 9.8)
    # shallow harness: φ dominated by packing class; GRAIL e-folding negligible <1 m
    phi_base = float(row.get("phi") or (0.42 if key == "surface_loose" else 0.40))
    phi_at_depth = phi_base * math.exp(-depth_m / (d_scale_km * 1000.0))
    return {
        "porosity_class": porosity_class,
        "phi": round(phi_at_depth, 4),
        "phi_surface": phi_base,
        "depth_m": depth_m,
        "material_id": row.get("material_id"),
        "depth_class": row.get("depth_class"),
        "l0_cites": [str(row.get("cite") or "SAKATANI-LPSC-1552")],
        "oracle": str(data.get("oracle") or "CITED_BIND"),
    }


def porosity_for_material(material_id: str, *, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    cls: PorosityClass = "depth_compact" if "compact" in material_id else "surface_loose"
    depth_m = 0.60 if cls == "depth_compact" else 0.15
    return porosity_phi(porosity_class=cls, depth_m=depth_m, bind=bind)


def compare_porosity_branches(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    """Falsifier: compact φ < loose φ at harness depths."""
    loose = porosity_phi(porosity_class="surface_loose", bind=bind)
    compact = porosity_phi(porosity_class="depth_compact", bind=bind)
    crustal = porosity_phi(porosity_class="crustal_bulk", bind=bind)
    phi_loose = float(loose["phi"])
    phi_compact = float(compact["phi"])
    return {
        "compare_id": "REGOLITH_POROSITY_COMPARE_v1",
        "loose": loose,
        "compact": compact,
        "crustal_bulk_grail": crustal,
        "phi_diff": round(phi_loose - phi_compact, 4),
        "compact_lower_phi": phi_compact < phi_loose,
        "crustal_bulk_much_lower": float(crustal["phi"]) < min(phi_loose, phi_compact),
        "oracle": loose.get("oracle"),
        "bind": "results/platform_bpass/moon/REGOLITH_THERMAL_BIND_v1.json",
    }
