"""Moon ↔ Arena coupling — rim ingress, thermal BC, soiling → EDS tile stress."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from dogfood_platform.arena.eds_2r_d2_hook_v1 import d2_soiling_hook
from dogfood_platform.arena.eds_2r_transport_v1 import simulate_transport_tw
from dogfood_platform.lunar_dust_ingress_v1 import (
    SiteZone,
    electrostatic_index,
    ingress_rate_g_m2_per_sol,
    load_dust_ingress_bind,
)
from dogfood_platform.lunar_thermal_l5_v1 import radiative_net_flux_w_m2

_REPO = Path(__file__).resolve().parents[2]
_COUPLE_BIND = _REPO / "results" / "platform_bpass" / "arena" / "ARENA_MOON_COUPLING_BIND_v1.json"
_ANCHOR = _REPO / "results" / "platform_bpass" / "moon" / "MOON_SHACKLETON_ANCHOR_v1.json"


def load_coupling_bind(path: Path | None = None) -> dict[str, Any]:
    p = path or _COUPLE_BIND
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def moon_tile_environment(
    *,
    zone: SiteZone = "rim_sun",
    n_sols: float = 30.0,
    seal_class: str = "B3",
    bind: dict[str, Any] | None = None,
    use_nowcast: bool = False,
    refresh_measured: bool = True,
    nowcast_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pull moon state for EDS tile on sunlit rim / traverse."""
    if nowcast_row is None and use_nowcast and zone == "rim_sun":
        from dogfood_platform.lunar_weather_nowcast_v1 import orient_for_arena

        nowcast_row = orient_for_arena(refresh=refresh_measured)

    couple = bind or load_coupling_bind()
    anchor = json.loads(_ANCHOR.read_text(encoding="utf-8"))
    zones = anchor.get("zones") or {}
    zrow = zones.get(zone) or zones.get("rim_sun") or {}
    if nowcast_row:
        t_k = float(nowcast_row["t_surf_k"])
    else:
        t_k = float(zrow.get("t_k") or zrow.get("t_k_mean") or 220.0)
    es = electrostatic_index(zone)
    rate = ingress_rate_g_m2_per_sol(zone)
    accumulation = min(rate * n_sols, float((load_dust_ingress_bind().get("wear_coupling") or {}).get("accumulation_saturation_g_m2") or 2.0))
    sat = float((couple.get("soiling") or {}).get("saturation_g_m2") or 2.0)
    soiling_frac = min(1.0, accumulation / max(sat, 1e-6))
    zone_rad: Literal["rim_sun", "psr_floor"] = "rim_sun" if zone == "rim_sun" else "psr_floor"
    if nowcast_row:
        raw_illum = nowcast_row.get("illum_frac")
        rad = radiative_net_flux_w_m2(
            t_k,
            zone=zone_rad,
            illum_frac=float(raw_illum if raw_illum is not None else 0.0) if zone == "rim_sun" else None,
        )
        rad["synced_to_nowcast"] = True
    else:
        rad = radiative_net_flux_w_m2(t_k, zone=zone_rad)
    q_mult = 1.0 + float(es["electrostatic_index"]) * float((couple.get("transport") or {}).get("electrostatic_gain") or 0.15)
    out = {
        "zone": zone,
        "t_surf_k": t_k,
        "n_sols": n_sols,
        "ingress_rate_g_m2_per_sol": rate,
        "accumulation_g_m2": round(accumulation, 4),
        "soiling_frac": round(soiling_frac, 4),
        "electrostatic_index": es["electrostatic_index"],
        "q_transport_mult": round(q_mult, 4),
        "radiative": rad,
        "l0_cites": list(zrow.get("l0_cites") or []) + list(es.get("l0_cites") or []),
        "oracle": "CITED_BIND",
    }
    if nowcast_row:
        out["lunar_weather"] = nowcast_row
        raw_illum = nowcast_row.get("illum_frac")
        illum = float(raw_illum if raw_illum is not None else 0.0)
        from dogfood_platform.lunar_charging_proxy_v1 import charging_proxy_dict

        sep = bool(nowcast_row.get("sep_active"))
        chg = charging_proxy_dict(illum_frac=illum, sep_active=sep)
        out["charging_proxy"] = chg
        out["dose_rate_cgy_per_day"] = chg["dose_proxy"]["dose_rate_cgy_per_day"]
        from dogfood_platform.lunar_albedo_dose_v1 import albedo_dose_dict

        surface_dose = albedo_dose_dict(mission_years=30.0 / 365.25, shield_g_cm2=0.0)
        out["surface_dose"] = {
            "incident_dose_gy": surface_dose["incident_dose_gy"],
            "albedo_dose_gy": surface_dose["albedo_dose_gy"],
            "total_dose_gy": surface_dose["total_dose_gy"],
            "albedo_fraction": surface_dose["albedo_fraction"],
            "tier": surface_dose["tier"],
            "oracle": surface_dose["oracle"],
            "bind": surface_dose["bind"],
            "l0_cites": surface_dose["l0_cites"],
        }
        es_mult = 1.0 + abs(chg["surface_potential_v_proxy"]) / 1000.0
        out["q_transport_mult"] = round(float(out["q_transport_mult"]) * es_mult, 4)
    return out


def coupled_d2_hook(
    *,
    zone: SiteZone = "rim_sun",
    n_sols: float = 30.0,
    use_nowcast: bool = False,
    nowcast_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = moon_tile_environment(zone=zone, n_sols=n_sols, use_nowcast=use_nowcast, nowcast_row=nowcast_row)
    base = d2_soiling_hook(soiling_frac=float(env["soiling_frac"]))
    base["moon_coupling"] = {
        "zone": zone,
        "t_surf_k": env["t_surf_k"],
        "accumulation_g_m2": env["accumulation_g_m2"],
        "q_net_w_m2": env["radiative"]["q_net_w_m2"],
    }
    base["hop_id"] = "h-arena-moon-d2-coupled"
    return base


def coupled_transport(
    *,
    zone: SiteZone = "rim_sun",
    n_sols: float = 30.0,
    use_nowcast: bool = False,
    nowcast_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = moon_tile_environment(zone=zone, n_sols=n_sols, use_nowcast=use_nowcast, nowcast_row=nowcast_row)
    base = simulate_transport_tw(q_proxy=float(env["q_transport_mult"]))
    base["moon_coupling"] = env
    base["hop_id"] = "h-arena-moon-transport-coupled"
    return base


def compare_coupled_vs_baseline(
    *,
    zone: SiteZone = "rim_sun",
    use_nowcast: bool = False,
    refresh_measured: bool = True,
    nowcast_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = moon_tile_environment(
        zone=zone,
        n_sols=30.0,
        use_nowcast=use_nowcast,
        refresh_measured=refresh_measured,
        nowcast_row=nowcast_row,
    )
    idle = simulate_transport_tw(q_proxy=1.0)
    coupled = simulate_transport_tw(q_proxy=float(env["q_transport_mult"]))
    d2_clean = d2_soiling_hook(soiling_frac=0.0)
    d2_moon = coupled_d2_hook(zone=zone, use_nowcast=use_nowcast, nowcast_row=nowcast_row)
    return {
        "compare_id": "ARENA_MOON_COUPLING_COMPARE_v1",
        "zone": zone,
        "coupled_transport_mm": coupled["mean_radial_drift_mm"],
        "baseline_transport_mm": idle["mean_radial_drift_mm"],
        "transport_coupling_raises_drift": coupled["mean_radial_drift_mm"] > idle["mean_radial_drift_mm"],
        "d2_clean_delta_w_m2": d2_clean["delta_absorbed_w_m2"],
        "d2_moon_delta_w_m2": d2_moon["delta_absorbed_w_m2"],
        "soiling_raises_absorption": d2_moon["delta_absorbed_w_m2"] > d2_clean["delta_absorbed_w_m2"],
        "falsifier_pass": (
            coupled["mean_radial_drift_mm"] > idle["mean_radial_drift_mm"]
            and d2_moon["delta_absorbed_w_m2"] > d2_clean["delta_absorbed_w_m2"]
        ),
    }


def write_coupling_receipt(*, use_nowcast: bool = False) -> dict[str, Any]:
    cmp = compare_coupled_vs_baseline(use_nowcast=use_nowcast)
    payload = {
        "receipt_id": "ARENA_MOON_COUPLING_RECEIPT_v1",
        "verdict": "PASS" if cmp["falsifier_pass"] else "FAIL",
        "environment": moon_tile_environment(use_nowcast=use_nowcast),
        "coupled_d2": coupled_d2_hook(),
        "coupled_transport": coupled_transport(),
        "compare": cmp,
        "use_nowcast": use_nowcast,
    }
    out = _COUPLE_BIND.parent / "ARENA_MOON_COUPLING_RECEIPT_v1.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    cmp_path = _COUPLE_BIND.parent / "ARENA_MOON_COUPLING_COMPARE_v1.json"
    cmp_path.write_text(json.dumps(cmp, indent=2) + "\n", encoding="utf-8")
    return payload


def _load_on_port_binds() -> list[str]:
    on_path = _REPO / "results" / "agent_lint" / "ON_PORT_OPEN.json"
    if not on_path.is_file():
        return []
    row = json.loads(on_path.read_text(encoding="utf-8"))
    return list(row.get("mandatory_bind_reads") or [])


def write_live_nowcast_arena_receipt(*, refresh_measured: bool = True, ephemeris_bind_only: bool = False) -> dict[str, Any]:
    """Arena tile on Shackleton rim — live nowcast + EDS coupling (CITED_BIND only)."""
    from dogfood_platform.lunar_weather_nowcast_v1 import orient_row_from_receipt, write_nowcast_receipt

    nowcast = write_nowcast_receipt(
        refresh_measured=refresh_measured,
        include_overflight=not ephemeris_bind_only,
        include_tile=not ephemeris_bind_only,
        ephemeris_bind_only=ephemeris_bind_only,
    )
    orient = orient_row_from_receipt(nowcast)
    measured = nowcast["layers"]["measured"]
    cmp = compare_coupled_vs_baseline(use_nowcast=True, nowcast_row=orient)
    env = moon_tile_environment(zone="rim_sun", n_sols=30.0, use_nowcast=True, nowcast_row=orient)
    payload = {
        "receipt_id": "ARENA_LIVE_NOWCAST_RECEIPT_v1",
        "oracle": "CITED_BIND",
        "site_id": "shackleton_rim",
        "timestamp_utc": nowcast.get("timestamp_utc"),
        "bind_reads": [
            "results/platform_bpass/moon/LUNAR_WEATHER_BIND_v1.json",
            "results/platform_bpass/arena/ARENA_MOON_COUPLING_BIND_v1.json",
            "results/platform_bpass/moon/MOON_SHACKLETON_ANCHOR_v1.json",
            *_load_on_port_binds(),
        ],
        "lunar_weather": {
            "receipt_path": nowcast.get("receipt_path")
            or "results/platform_bpass/moon/LUNAR_WEATHER_NOWCAST_LIVE_v1.json",
            "verdict": nowcast["verdict"],
            "measured_tier": measured.get("tier"),
            "measured_age_class": measured.get("age_class"),
            "measured_age_h": measured.get("age_h"),
            "nowcast_tier": nowcast["layers"]["nowcast"].get("tier"),
            "t_surface_k": nowcast["layers"]["nowcast"].get("t_surface_k"),
            "forward_mode": nowcast.get("falsifier", {}).get("forward_mode"),
            "envelope_ok": nowcast.get("falsifier", {}).get("envelope_ok"),
            "ephemeris_tier": nowcast["layers"]["sun_now"].get("ephemeris_tier"),
            "sun_source": nowcast["layers"]["sun_now"].get("source_detail"),
        },
        "arena_tile": {
            "zone": env["zone"],
            "t_surf_k": env["t_surf_k"],
            "soiling_frac": env["soiling_frac"],
            "q_net_w_m2": env["radiative"]["q_net_w_m2"],
            "synced_to_nowcast": env["radiative"].get("synced_to_nowcast"),
            "l0_cites": env.get("l0_cites"),
        },
        "coupled_d2": coupled_d2_hook(zone="rim_sun", use_nowcast=True, nowcast_row=orient),
        "coupled_transport": coupled_transport(zone="rim_sun", use_nowcast=True, nowcast_row=orient),
        "compare": cmp,
        "verdict": "PASS" if cmp["falsifier_pass"] and nowcast["verdict"] in ("PASS", "DEGRADED") else "FAIL",
        "honesty_note": "DEGRADED nowcast tier is expected when Diviner anchor is MEASURED_STALE/ANCIENT — not a physics override",
    }
    out = _COUPLE_BIND.parent / "ARENA_LIVE_NOWCAST_RECEIPT_v1.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    payload["receipt_path"] = str(out.relative_to(_REPO)).replace("\\", "/")
    return payload
