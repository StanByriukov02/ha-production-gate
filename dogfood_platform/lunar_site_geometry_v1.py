"""GAP-MR-07 — Shackleton rim→floor site geometry path (Zuber + Spudis + Fincannon bind)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "results" / "platform_bpass" / "moon" / "SITE_GEOMETRY_BIND_v1.json"


def load_site_geometry_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def shackleton_path_profile(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    data = bind or load_site_geometry_bind()
    crater = data.get("crater") or {}
    depth_km = float(crater.get("depth_rim_to_floor_km") or 4.1)
    segments_in = list(data.get("path_segments") or [])
    segments: list[dict[str, Any]] = []
    total_path_km = 0.0
    illum_weighted = 0.0
    for seg in segments_in:
        frac = float(seg.get("path_fraction") or 0.0)
        slope = max(1.0, float(seg.get("slope_deg") or 12.0))
        seg_depth_km = depth_km * frac
        path_km = seg_depth_km / math.sin(math.radians(slope))
        illum = float(seg.get("illumination_frac") or 0.0)
        total_path_km += path_km
        illum_weighted += illum * frac
        segments.append(
            {
                "segment_id": seg.get("segment_id"),
                "zone_id": seg.get("zone_id"),
                "path_fraction": frac,
                "slope_deg": slope,
                "segment_depth_km": round(seg_depth_km, 4),
                "path_km": round(path_km, 3),
                "illumination_frac": illum,
                "asymmetric_wall": seg.get("asymmetric_wall"),
                "l0_cites": list(seg.get("cite") or []),
            }
        )
    naive_path_km = depth_km / math.sin(math.radians(15.0))
    return {
        "crater_depth_km": depth_km,
        "rim_diameter_km": float(crater.get("rim_diameter_km") or 21.0),
        "massif_slope_limit_deg": float((data.get("massif") or {}).get("slope_max_deg") or 15.0),
        "segments": segments,
        "total_path_km": round(total_path_km, 3),
        "naive_path_at_15deg_km": round(naive_path_km, 3),
        "path_exceeds_naive_15deg": total_path_km > naive_path_km * 0.85,
        "weighted_illumination_frac": round(illum_weighted, 4),
        "rim_annual_frac": float((data.get("illumination") or {}).get("rim_annual_frac") or 0.96),
        "l0_cites": list(crater.get("cite") or ["SK-01", "SK-02"]),
        "oracle": str(data.get("oracle") or "CITED_BIND"),
        "bind_id": str(data.get("bind_id") or "site_geometry_bind_v1"),
    }


def zone_at_path_fraction(path_fraction: float, *, bind: dict[str, Any] | None = None) -> tuple[str, str, float]:
    """Map normalized traverse fraction → site_geometry zone / segment / illumination."""
    profile = shackleton_path_profile(bind=bind)
    frac = max(0.0, min(1.0, float(path_fraction)))
    cum = 0.0
    for seg in profile["segments"]:
        wf = float(seg["path_fraction"])
        if frac <= cum + wf + 1e-9:
            return str(seg["zone_id"]), str(seg["segment_id"]), float(seg["illumination_frac"])
        cum += wf
    last = profile["segments"][-1]
    return str(last["zone_id"]), str(last["segment_id"]), float(last["illumination_frac"])


def depth_m_at_path_fraction(path_fraction: float, *, bind: dict[str, Any] | None = None) -> float:
    profile = shackleton_path_profile(bind=bind)
    frac = max(0.0, min(1.0, float(path_fraction)))
    cum = 0.0
    depth = 0.0
    for seg in profile["segments"]:
        wf = float(seg["path_fraction"])
        seg_depth_m = float(seg["segment_depth_km"]) * 1000.0
        if frac <= cum + wf + 1e-9:
            local = (frac - cum) / wf if wf > 0 else 1.0
            return depth + local * seg_depth_m
        depth += seg_depth_m
        cum += wf
    return float(profile["crater_depth_km"]) * 1000.0


def shackleton_traverse_geo_at_fraction(
    path_fraction: float,
    *,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rim→PSR lat/lon/elev from SITE_GEOMETRY_BIND (CITED_BIND · not photogrammetry)."""
    data = bind or load_site_geometry_bind()
    crater = data.get("crater") or {}
    profile = shackleton_path_profile(bind=data)
    lat0 = float(crater.get("center_lat_deg") or -89.655)
    lon0 = float(crater.get("center_lon_deg") or 129.174)
    frac = max(0.0, min(1.0, float(path_fraction)))
    rim_m = float(profile.get("rim_diameter_km") or 21.0) * 500.0
    floor_m = 1800.0
    r_m = rim_m * (1.0 - frac) + floor_m * frac
    bearing_deg = 120.0
    bearing = math.radians(bearing_deg)
    east_m = r_m * math.sin(bearing)
    north_m = r_m * math.cos(bearing)
    moon_r = 1_737_400.0
    lat = lat0 + math.degrees(north_m / moon_r)
    cos_lat = max(math.cos(math.radians(lat0)), 1e-6)
    lon = lon0 + math.degrees(east_m / (moon_r * cos_lat))
    depth_m = depth_m_at_path_fraction(frac, bind=data)
    zone_id, segment_id, illum = zone_at_path_fraction(frac, bind=data)
    rim_ref_m = 450.0
    elev_m = rim_ref_m - depth_m
    return {
        "lat_deg": round(lat, 6),
        "lon_deg": round(lon, 6),
        "elev_m": round(elev_m, 1),
        "depth_m": round(depth_m, 1),
        "zone_id": zone_id,
        "segment_id": segment_id,
        "illumination_frac": illum,
        "path_fraction": frac,
        "bearing_deg": bearing_deg,
        "oracle": "CITED_BIND",
        "geo_bind": "results/platform_bpass/moon/SITE_GEOMETRY_BIND_v1.json",
        "l0_cites": list(profile.get("l0_cites") or []),
    }


def shackleton_path_geo_table(*, ticks: int = 50, bind: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(ticks):
        frac = (i + 1) / ticks
        row = shackleton_traverse_geo_at_fraction(frac, bind=bind)
        row["tick"] = i
        rows.append(row)
    return rows


def rim_duty_for_embed(*, bind: dict[str, Any] | None = None) -> float:
    """Mission-average rim sun weight for LC-2 thermal path."""
    profile = shackleton_path_profile(bind=bind)
    rim_frac = float(profile.get("rim_annual_frac") or 0.96)
    weighted = float(profile.get("weighted_illumination_frac") or 0.72)
    # embed at rim with traverse exposure mix
    return round(0.55 * rim_frac + 0.45 * weighted, 4)


def compare_geometry_paths(*, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = shackleton_path_profile(bind=bind)
    duty = rim_duty_for_embed(bind=bind)
    west = next(s for s in profile["segments"] if s["segment_id"] == "massif_descent")
    psr = next(s for s in profile["segments"] if s["segment_id"] == "psr_approach")
    return {
        "compare_id": "SITE_GEOMETRY_PATH_COMPARE_v1",
        "profile": profile,
        "rim_duty_for_lc2_embed": duty,
        "rim_duty_above_half": duty > 0.5,
        "massif_path_km": west["path_km"],
        "psr_illum_lower_than_massif": float(psr["illumination_frac"]) < float(west["illumination_frac"]),
        "variants_diverge": float(west["path_km"]) != float(psr["path_km"]),
        "oracle": "CITED_BIND",
        "bind": "results/platform_bpass/moon/SITE_GEOMETRY_BIND_v1.json",
    }
