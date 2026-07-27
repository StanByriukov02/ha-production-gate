"""A1-5 — MEM3 threat mass class bind (not surface flux without trajectory)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "results" / "platform_bpass" / "moon" / "MICROMETEOROID_THREAT_BIND_v1.json"


def load_micrometeoroid_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def threat_mass_in_band(mass_g: float, *, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    data = bind or load_micrometeoroid_bind()
    band = data.get("threat_mass_g") or {}
    lo = float(band.get("min") or 1e-6)
    hi = float(band.get("max") or 10.0)
    in_band = lo <= mass_g <= hi
    return {
        "mass_g": mass_g,
        "threat_mass_min_g": lo,
        "threat_mass_max_g": hi,
        "in_mem_threat_band": in_band,
        "oracle": str(data.get("oracle") or "CITED_BIND"),
        "bind_id": str(data.get("bind_id") or "micrometeoroid_threat_bind_v1"),
        "l0_cites": ["MEM3-L0-03"],
        "note": "MEM requires trajectory — harness class row only",
    }
