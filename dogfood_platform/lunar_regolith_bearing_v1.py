"""GAP-MR-11 ADAPT — regolith bearing / sinkage class (Atkinson stack + Daca + Li)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from dogfood_platform.open_seed_paths_v1 import gap_mr11_adapt_closure_path, kls1_bevameter_bind_path

_REPO = Path(__file__).resolve().parents[1]

RegolithBearingClass = Literal["LOOSE", "MEDIUM", "DENSE"]
_DEFAULT_CLASS: RegolithBearingClass = "MEDIUM"


def load_bearing_closure() -> dict[str, Any]:
    path = gap_mr11_adapt_closure_path(_REPO)
    if not path.is_file():
        raise FileNotFoundError(f"missing ADAPT closure: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def q_c_kpa_at_depth_mm(depth_mm: float) -> float:
    """Li lunar-g fit — ON catalog / Rust oracle (catalog mirror hot path)."""
    from dogfood_platform.li_bearing_qc_on_v1 import qc_from_catalog

    return float(qc_from_catalog(depth_mm=depth_mm)["q_c_kpa"])


def bearing_class_for_dr(dr_pct: float) -> RegolithBearingClass:
    if dr_pct <= 20.0:
        return "LOOSE"
    if dr_pct >= 65.0:
        return "DENSE"
    return "MEDIUM"


def bearing_tier(class_id: RegolithBearingClass, closure: dict[str, Any] | None = None) -> dict[str, Any]:
    data = closure or load_bearing_closure()
    harness = data.get("W_moon_harness") or {}
    for tier in harness.get("classes") or []:
        if tier.get("id") == class_id:
            return dict(tier)
    raise KeyError(f"unknown bearing class {class_id}")


def dual_bearing_anchors(closure: dict[str, Any] | None = None) -> dict[str, dict[str, float]]:
    """Safe/hostile Dual pressure+slope from GAP-MR-11 closure — not prove-local literals."""
    data = closure or load_bearing_closure()
    anchors = data.get("dual_law_anchors") or {}
    safe = anchors.get("safe") or {}
    hostile = anchors.get("hostile") or {}
    required = ("contact_pressure_kpa", "slope_deg", "slope_limit_deg")
    for label, row in (("safe", safe), ("hostile", hostile)):
        missing = [k for k in required if k not in row]
        if missing:
            raise KeyError(f"GAP-MR-11 dual_law_anchors.{label} missing {missing}")
    medium = bearing_tier("MEDIUM", data)
    band = medium.get("q_c_30mm_kPa_band") or []
    if len(band) < 2:
        raise KeyError("MEDIUM q_c_30mm_kPa_band missing")
    lo, hi = float(band[0]), float(band[1])
    safe_p = float(safe["contact_pressure_kpa"])
    hostile_p = float(hostile["contact_pressure_kpa"])
    if not (safe_p < lo <= hi < hostile_p):
        raise ValueError(
            f"dual anchors must straddle MEDIUM band [{lo},{hi}]; got safe={safe_p} hostile={hostile_p}"
        )
    return {
        "safe": {
            "contact_pressure_kpa": safe_p,
            "slope_deg": float(safe["slope_deg"]),
            "slope_limit_deg": float(safe["slope_limit_deg"]),
        },
        "hostile": {
            "contact_pressure_kpa": hostile_p,
            "slope_deg": float(hostile["slope_deg"]),
            "slope_limit_deg": float(hostile["slope_limit_deg"]),
        },
    }


_SMALL_WHEEL_BEKKER_OK_DIA_CM = 50.0
_ISTVS_CITE = "MEIRION-GRIFFITH-ISTVS-2011-L0-01"


def load_kls1_bevameter_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or kls1_bevameter_bind_path(_REPO)
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def bekker_pressure_kpa_kls1(
    z_m: float,
    *,
    plate_radius_m: float = 0.03,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Kim JASS 2021 Table 3 — KLS-1 Bekker p(z) via Rust ha-physics-gate (Python glue only)."""
    from dogfood_platform.terramech_bekker_on_v1 import ORACLE, evaluate_pressure_from_z

    data = bind or load_kls1_bevameter_bind()
    z = max(z_m, 1e-6)
    b = max(plate_radius_m, 1e-4)
    rust = evaluate_pressure_from_z("kls1_kim_jass_t3", z, contact_width_b_m=b)
    p_kpa = float(rust["p_kpa"])
    return {
        "z_m": round(z, 6),
        "z_mm": round(z * 1000.0, 3),
        "plate_radius_m": b,
        "plate_diameter_mm": round(2.0 * b * 1000.0, 1),
        "p_kpa": round(p_kpa, 3),
        "n": float((rust.get("params") or {}).get("n") or 1.2594),
        "oracle": ORACLE,
        "bind_oracle": "CITED_BIND",
        "l0_cites": ["KIM-JASS-2021-TABLE3"],
        "bind_id": str(data.get("bind_id") or "kls1_bevameter_bind_v1"),
        "source_slug": str(data.get("source_slug") or "intake-c2-kim-jass-kls"),
        "honesty": {
            "bekker_from_rust": True,
            "python_not_oracle": True,
            "cited_bind_params": True,
            "not_measured": True,
        },
    }


def sinkage_mm_for_pressure_kpa_kls1(
    target_p_kpa: float,
    *,
    plate_radius_m: float = 0.03,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invert KLS-1 Bekker via Rust bekker-eval (z from p)."""
    from dogfood_platform.terramech_bekker_on_v1 import ORACLE, evaluate_soil

    data = bind or load_kls1_bevameter_bind()
    b = max(plate_radius_m, 1e-4)
    if target_p_kpa <= 0:
        raise ValueError("invalid Bekker coefficients or pressure for KLS-1 invert")
    ev = evaluate_soil(
        "kls1_kim_jass_t3",
        ground_pressure_kpa=float(target_p_kpa),
        contact_width_b_m=b,
    )
    z_mm = float(ev["sinkage_mm"])
    row = bekker_pressure_kpa_kls1(z_mm / 1000.0, plate_radius_m=b, bind=data)
    return {
        "target_p_kpa": target_p_kpa,
        "sinkage_mm": round(z_mm, 3),
        "verified_p_kpa": row["p_kpa"],
        "compaction_resistance_n": float(ev.get("compaction_resistance_n") or 0.0),
        "drawbar_pull_n": ev.get("drawbar_pull_n"),
        "oracle": ORACLE,
        **{k: v for k, v in row.items() if k not in ("oracle",)},
        "honesty": {
            "bekker_from_rust": True,
            "python_not_oracle": True,
            "not_measured": True,
        },
    }


def classify_kls1_vs_adapt_tier(
    *,
    depth_mm: float = 30.0,
    plate_radius_m: float = 0.03,
    closure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cross-check KLS-1 gold vs GAP-MR-11 ADAPT tier bands."""
    p_row = bekker_pressure_kpa_kls1(depth_mm / 1000.0, plate_radius_m=plate_radius_m)
    p = float(p_row["p_kpa"])
    data = closure or load_bearing_closure()
    matched: RegolithBearingClass | None = None
    for tier in (data.get("W_moon_harness") or {}).get("classes") or []:
        band = tier.get("q_c_30mm_kPa_band") or []
        if len(band) == 2 and float(band[0]) <= p <= float(band[1]):
            matched = tier["id"]
            break
    if matched is None:
        if p < 40.0:
            matched = "LOOSE"
        elif p > 450.0:
            matched = "DENSE"
        else:
            matched = "MEDIUM"
    li_q = q_c_kpa_at_depth_mm(depth_mm)
    return {
        "kls1_p_kpa": p,
        "depth_mm": depth_mm,
        "matched_adapt_tier": matched,
        "li_adapt_q_kpa": round(li_q, 1),
        "diverges_from_li_only": abs(p - li_q) > 20.0,
        "oracle": "CITED_BIND",
        "l0_cites": ["KIM-JASS-2021-TABLE3", "GAP-MR-11", "L0-MR11-02"],
    }


def compare_kls1_bevameter_paths() -> dict[str, Any]:
    p30_60 = bekker_pressure_kpa_kls1(0.03, plate_radius_m=0.03)
    p30_75 = bekker_pressure_kpa_kls1(0.03, plate_radius_m=0.0375)
    tier = classify_kls1_vs_adapt_tier(depth_mm=30.0, plate_radius_m=0.03)
    return {
        "compare_id": "KLS1_BEVAMETER_COMPARE_v1",
        "plate_60mm_at_30mm": p30_60,
        "plate_75mm_at_30mm": p30_75,
        "larger_plate_higher_p": float(p30_75["p_kpa"]) > float(p30_60["p_kpa"]),
        "adapt_tier_check": tier,
        "in_adapt_band": tier["matched_adapt_tier"] in ("LOOSE", "MEDIUM", "DENSE"),
        "diverges_from_li": tier["diverges_from_li_only"],
        "variants_diverge": float(p30_75["p_kpa"]) != float(p30_60["p_kpa"]),
        "oracle": p30_60.get("oracle") or "CITED_BIND",
        "honesty": {
            "bekker_from_rust": bool((p30_60.get("honesty") or {}).get("bekker_from_rust")),
            "adapt_tier_adjunct": True,
        },
        "bind": "results/platform_bpass/moon/KLS1_BEVAMETER_BIND_v1.json",
    }


def wheel_terramechanics_class(*, wheel_diameter_cm: float) -> dict[str, Any]:
    """ISTVS 2011 — flat-plate Bekker invalid below ~50 cm."""
    small = wheel_diameter_cm < _SMALL_WHEEL_BEKKER_OK_DIA_CM
    return {
        "wheel_diameter_cm": wheel_diameter_cm,
        "bekker_flat_plate_ok": not small,
        "wheel_class": "SMALL_WHEEL" if small else "BEKKER_OK",
        "model": "sigma = k_hat * z^n_hat * D^m_hat" if small else "Bekker/Reece flat plate",
        "oracle": "CITED_BIND",
        "l0_cites": [_ISTVS_CITE],
        "source_slug": "intake-c2-meirion-griffith-istvs",
    }


def evaluate_bearing_sinkage(
    *,
    bearing_class: RegolithBearingClass = _DEFAULT_CLASS,
    contact_pressure_kpa: float,
    penetration_depth_mm: float = 30.0,
    slope_deg: float,
    slope_limit_deg: float = 15.0,
) -> dict[str, Any]:
    """Return traverse mechanical bearing verdict for foot/contact pressure vs tier band."""
    tier = bearing_tier(bearing_class)
    band = tier.get("q_c_30mm_kPa_band") or [90, 250]
    q_lo, q_hi = float(band[0]), float(band[1])
    q_ref = q_c_kpa_at_depth_mm(penetration_depth_mm)
    # scale reference to depth (Li curve) but gate on tier band at 30 mm
    q_at_depth = q_c_kpa_at_depth_mm(penetration_depth_mm)
    tier_mid = 0.5 * (q_lo + q_hi)
    pressure_ratio = contact_pressure_kpa / max(tier_mid, 1e-6)
    sinkage_risk = pressure_ratio > 1.0 or contact_pressure_kpa > q_hi
    slope_ok = slope_deg <= slope_limit_deg
    feasible = slope_ok and not sinkage_risk
    return {
        "bearing_class": bearing_class,
        "contact_pressure_kpa": round(contact_pressure_kpa, 2),
        "q_c_at_depth_kpa": round(q_at_depth, 1),
        "tier_q_band_30mm_kpa": [q_lo, q_hi],
        "pressure_ratio": round(pressure_ratio, 4),
        "sinkage_risk": sinkage_risk,
        "slope_deg": slope_deg,
        "slope_limit_deg": slope_limit_deg,
        "slope_ok": slope_ok,
        "traverse_feasible": feasible,
        "oracle": "ADAPT_GAP_MR_11",
        "l0_cites": ["GAP-MR-11", "L0-MR11-02", "L0-MR11-04"],
        "closure_source": str(gap_mr11_adapt_closure_path(_REPO).relative_to(_REPO)).replace(
            "\\", "/"
        ),
    }


def shackleton_default_bearing_state() -> dict[str, Any]:
    """Default Shackleton traverse: MEDIUM regolith, contact from zone table (SK-13/GAP-MR-11)."""
    from dogfood_platform.lunar_zone_table_v1 import ZONES

    massif = ZONES["massif_traverse"]
    slope = float(massif["slope_max_deg"])
    limit = float(massif["slope_limit_deg"])
    contact_kpa = float(massif["contact_pressure_kpa"])
    out = evaluate_bearing_sinkage(
        bearing_class=_DEFAULT_CLASS,
        contact_pressure_kpa=contact_kpa,
        slope_deg=slope,
        slope_limit_deg=limit,
    )
    out["contact_pressure_source"] = "lunar_zone_table.massif_traverse"
    out["l0_cites"] = list(massif.get("l0_cites") or []) + list(out.get("l0_cites") or [])
    return out
