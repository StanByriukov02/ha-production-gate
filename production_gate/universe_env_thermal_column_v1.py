"""U4 — 1D thermal column step + BC from env state (CITED_BIND harness only)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from production_gate.lunar_psr_thermal_column_v1 import (
    effective_k_with_cryo_leg,
    psr_subsurface_delta_k,
)
from production_gate.lunar_regolith_thermal_v1 import effective_k_w_mk, load_thermal_bind
from production_gate.lunar_thermal_l5_v1 import (
    load_transient_bind,
    load_vacuum_bc_bind,
    radiative_net_flux_w_m2,
    thermal_time_constant_s,
)
from production_gate.universe_env_state_v1 import EnvironmentStateV1, ThermalColumnV1

_REPO = Path(__file__).resolve().parents[1]
_METHOD_BIND = _REPO / "results" / "platform_bpass" / "universe" / "ENV_STATE_PHYSICS_METHOD_BIND_v1.json"
_ENV_DRIVER = _REPO / "results" / "platform_bpass" / "universe" / "ENV_DRIVER_BIND_v1.json"

_CFL_SAFETY = 0.45
_PICARD_ITERS = 2


def _method_init_defaults() -> dict[str, Any]:
    if not _METHOD_BIND.is_file():
        return {"material_id": "highland_regolith_loose", "zone": "rim_sun"}
    bind = json.loads(_METHOD_BIND.read_text(encoding="utf-8"))
    for m in bind.get("methods") or []:
        if m.get("axis_id") == "M1_thermal_field":
            return dict(m.get("init_defaults") or {})
    return {"material_id": "highland_regolith_loose", "zone": "rim_sun"}


def lunar_half_period_h() -> float:
    return float(load_transient_bind().get("lunar_half_period_h") or 354.0)


def lunar_day_h() -> float:
    return 2.0 * lunar_half_period_h()


def lunar_timeline_meta(t_h: float) -> dict[str, Any]:
    """Timeline in hours where lunar_half_period_h = half lunar day (THERMAL_TRANSIENT_BIND)."""
    half = lunar_half_period_h()
    full = lunar_day_h()
    phase_half = (t_h % half) / max(half, 1e-9)
    return {
        "t_lunar_h": round(t_h, 4),
        "lunar_half_period_h": half,
        "lunar_day_h": full,
        "lunar_phase_half": round(phase_half, 6),
        "lunar_sol_fraction": round(t_h / max(full, 1e-9), 6),
    }


def earth_hours_to_lunar_sols(dt_h: float) -> float:
    return dt_h / max(lunar_day_h(), 1e-9)


def _env_driver_axes() -> dict[str, Any]:
    if not _ENV_DRIVER.is_file():
        return {}
    return json.loads(_ENV_DRIVER.read_text(encoding="utf-8")).get("driver_axes") or {}


def thermal_envelope_k(*, regime_id: str = "rim_sunlit") -> tuple[float, float]:
    """Regime-specific bounds — rim SK-12 band vs PSR SK-10 floor (not one clamp for all)."""
    vac = load_vacuum_bc_bind()
    sky = vac.get("sky_temperature_k") or {}
    axes = _env_driver_axes()
    vac_ax = axes.get("vacuum_thermal") or {}
    kt = load_thermal_bind()
    polar = (kt.get("k_temperature") or {}).get("polar_envelope_k") or [250.0, 330.0]

    if regime_id == "psr_floor":
        psr_band = (vac_ax.get("t_psr_floor_k") or {}).get("band") or [40.0, 110.0]
        t_lo = float(psr_band[0])
        t_hi = float(psr_band[1])
    else:
        rim_band = (vac_ax.get("t_rim_surf_k") or {}).get("band") or [200.0, 230.0]
        t_lo = float(rim_band[0])
        t_hi = min(float(polar[1]), float(rim_band[1]) + 100.0)
        t_lo = max(t_lo, float(sky.get("rim_effective") or 220.0) - 30.0)

    return t_lo, t_hi


def rim_oblique_solar_scale(*, vac_bind: dict[str, Any] | None = None) -> float:
    """Scale noon flux to oblique polar rim — balance at rim_effective from bind (SK-12)."""
    vac = vac_bind or load_vacuum_bc_bind()
    t_rim = float((vac.get("sky_temperature_k") or {}).get("rim_effective") or 220.0)
    sigma = float(vac.get("stefan_boltzmann_w_m2_k4") or 5.670374419e-8)
    eps = float(vac.get("surface_emissivity_regolith") or 0.95)
    t_sky = float((vac.get("sky_temperature_k") or {}).get("deep_space") or 3.0)
    solar = float(vac.get("solar_constant_w_m2") or 1361.0)
    albedo = float(vac.get("albedo_highland") or 0.12)
    illum = float(vac.get("rim_illumination_frac") or 0.96)
    q_rad_eq = eps * sigma * (t_rim**4 - t_sky**4)
    q_solar_noon = (1.0 - albedo) * solar * illum
    return q_rad_eq / max(q_solar_noon, 1e-9)


def _rho_cp_from_bind() -> tuple[float, float]:
    tm = load_transient_bind().get("regolith_thermal_mass") or {}
    return float(tm.get("rho_kg_m3") or 1600.0), float(tm.get("cp_j_kg_k") or 800.0)


def _k_at_node(
    t_k: float,
    *,
    material_id: str,
    regime_id: str,
) -> float:
    if regime_id == "psr_floor":
        row = effective_k_with_cryo_leg(material_id, t_k=t_k)
    else:
        row = effective_k_w_mk(material_id, t_k=t_k)
    return max(float(row["k_w_mk"]), 1e-9)


def _k_interface(k_a: float, k_b: float) -> float:
    return 0.5 * (k_a + k_b)


def _solve_tridiagonal(a: list[float], b: list[float], c: list[float], d: list[float]) -> list[float]:
    n = len(d)
    cp = [0.0] * n
    dp = [0.0] * n
    denom = b[0]
    if abs(denom) < 1e-30:
        denom = 1e-30
    cp[0] = c[0] / denom if n > 1 else 0.0
    dp[0] = d[0] / denom
    for i in range(1, n):
        denom = b[i] - a[i] * cp[i - 1]
        if abs(denom) < 1e-30:
            denom = 1e-30
        if i < n - 1:
            cp[i] = c[i] / denom
        dp[i] = (d[i] - a[i] * dp[i - 1]) / denom
    x = [0.0] * n
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def _column_dz(column: ThermalColumnV1) -> float:
    n = len(column.t_k)
    if n > 1:
        return max(column.z_m[1] - column.z_m[0], 1e-6)
    stacks = load_transient_bind().get("stack_thickness_classes_m") or {}
    return max(float(stacks.get("lc2_micro") or 0.052), 1e-6)


def _node_k_vector(
    t_k: list[float],
    *,
    material_id: str,
    regime_id: str,
) -> list[float]:
    return [_k_at_node(t, material_id=material_id, regime_id=regime_id) for t in t_k]


def _implicit_system(
    t_old: list[float],
    *,
    dt_s: float,
    dz: float,
    rho_cp: float,
    q_in_w_m2: float,
    k_nodes: list[float],
) -> list[float]:
    n = len(t_old)
    a = [0.0] * n
    b = [0.0] * n
    c = [0.0] * n
    d = [0.0] * n

    if n == 1:
        k01 = k_nodes[0]
        b[0] = rho_cp * dz / (2.0 * dt_s) + k01 / dz
        d[0] = rho_cp * dz / (2.0 * dt_s) * t_old[0] + q_in_w_m2
        return _solve_tridiagonal(a, b, c, d)

    k01 = _k_interface(k_nodes[0], k_nodes[1])
    b[0] = rho_cp * dz / (2.0 * dt_s) + k01 / dz
    c[0] = -k01 / dz
    d[0] = rho_cp * dz / (2.0 * dt_s) * t_old[0] + q_in_w_m2

    for i in range(1, n - 1):
        k_im1 = _k_interface(k_nodes[i - 1], k_nodes[i])
        k_ip1 = _k_interface(k_nodes[i], k_nodes[i + 1])
        a[i] = -k_im1 / dz
        b[i] = rho_cp / dt_s + (k_im1 + k_ip1) / dz
        c[i] = -k_ip1 / dz
        d[i] = rho_cp / dt_s * t_old[i]

    k_nb = _k_interface(k_nodes[n - 2], k_nodes[n - 1])
    a[n - 1] = -k_nb / dz
    b[n - 1] = rho_cp * dz / (2.0 * dt_s) + k_nb / dz
    d[n - 1] = rho_cp * dz / (2.0 * dt_s) * t_old[n - 1]

    return _solve_tridiagonal(a, b, c, d)


def step_column_implicit_1d(
    column: ThermalColumnV1,
    *,
    dt_h: float,
    q_in_w_m2: float,
    regime_id: str = "rim_sunlit",
    material_id: str | None = None,
    step_meta: dict[str, Any] | None = None,
) -> float:
    """Backward-Euler 1D diffusion + surface flux BC; q_in = solar absorbed − radiative loss."""
    if column.n_nodes < 1 or not column.t_k:
        return 0.0

    init = _method_init_defaults()
    mat = material_id or str(init.get("material_id") or "highland_regolith_loose")
    rho, cp = _rho_cp_from_bind()
    rho_cp = rho * cp
    dz = _column_dz(column)
    dt_s = max(dt_h, 1e-9) * 3600.0
    t_lo, t_hi = thermal_envelope_k(regime_id=regime_id)
    t0_before = column.t_k[0]

    t_old = list(column.t_k)
    t_guess = list(column.t_k)
    for _ in range(_PICARD_ITERS):
        k_nodes = _node_k_vector(t_guess, material_id=mat, regime_id=regime_id)
        t_guess = _implicit_system(
            t_old,
            dt_s=dt_s,
            dz=dz,
            rho_cp=rho_cp,
            q_in_w_m2=q_in_w_m2,
            k_nodes=k_nodes,
        )

    t_raw_surf = float(t_guess[0])
    clamped = t_raw_surf < t_lo or t_raw_surf > t_hi
    for i, t in enumerate(t_guess):
        column.t_k[i] = max(t_lo, min(t_hi, t))

    if step_meta is not None:
        step_meta.clear()
        step_meta.update(
            {
                "t_surface_raw_k": round(t_raw_surf, 4),
                "t_surface_clamped_k": round(column.t_k[0], 4),
                "envelope_clamped": clamped,
                "envelope_k": [t_lo, t_hi],
            }
        )

    column.k_w_mk = _k_at_node(column.t_k[0], material_id=mat, regime_id=regime_id)
    return column.t_k[0] - t0_before


def _cfl_dt_s(
    *,
    rho_cp: float,
    dz: float,
    k_w_mk: float,
    q_in_w_m2: float,
) -> float:
    dt_diff = rho_cp * dz * dz / max(2.0 * k_w_mk, 1e-12)
    skin = max(dz * 0.5, 1e-6)
    q_mag = max(abs(q_in_w_m2), 1.0)
    dt_surf = rho_cp * skin / q_mag
    return _CFL_SAFETY * min(dt_diff, dt_surf)


def step_column_explicit_1d(
    column: ThermalColumnV1,
    *,
    dt_h: float,
    q_in_w_m2: float,
    regime_id: str = "rim_sunlit",
    material_id: str | None = None,
) -> float:
    """Explicit reference step (CFL sub-steps) — falsifier baseline only."""
    if column.n_nodes < 1 or not column.t_k:
        return 0.0

    init = _method_init_defaults()
    mat = material_id or str(init.get("material_id") or "highland_regolith_loose")
    rho, cp = _rho_cp_from_bind()
    rho_cp = rho * cp

    n = len(column.t_k)
    dz = _column_dz(column)
    t_lo, t_hi = thermal_envelope_k(regime_id=regime_id)
    t0_before = column.t_k[0]
    t_remaining_s = max(dt_h, 1e-9) * 3600.0

    while t_remaining_s > 1e-9:
        k_surf = _k_at_node(column.t_k[0], material_id=mat, regime_id=regime_id)
        dt_step = min(t_remaining_s, _cfl_dt_s(rho_cp=rho_cp, dz=dz, k_w_mk=k_surf, q_in_w_m2=q_in_w_m2))
        dt_step = max(dt_step, 1e-6)

        skin = dz * 0.5
        column.t_k[0] += q_in_w_m2 * dt_step / max(rho_cp * skin, 1.0)

        if n >= 3:
            for i in range(1, n - 1):
                k_i = _k_at_node(column.t_k[i], material_id=mat, regime_id=regime_id)
                d2t = (column.t_k[i + 1] - 2.0 * column.t_k[i] + column.t_k[i - 1]) / (dz * dz)
                column.t_k[i] += k_i * d2t / rho_cp * dt_step

        for i in range(n):
            column.t_k[i] = max(t_lo, min(t_hi, column.t_k[i]))

        t_remaining_s -= dt_step

    column.k_w_mk = _k_at_node(column.t_k[0], material_id=mat, regime_id=regime_id)
    return column.t_k[0] - t0_before


def compare_explicit_implicit_skin_step(
    *,
    dt_h: float = 0.25,
    q_in_w_m2: float = 50.0,
    regime_id: str = "rim_sunlit",
) -> dict[str, Any]:
    """Falsifier — thin lc2_micro column: implicit vs CFL-refined explicit surface dT."""
    stacks = load_transient_bind().get("stack_thickness_classes_m") or {}
    skin_m = float(stacks.get("lc2_micro") or 0.052)
    col_imp = column_init_from_binds(regime_id=regime_id, n_nodes=3, depth_m=skin_m)
    col_exp = copy.deepcopy(col_imp)
    dT_imp = step_column_implicit_1d(col_imp, dt_h=dt_h, q_in_w_m2=q_in_w_m2, regime_id=regime_id)
    dT_exp = step_column_explicit_1d(col_exp, dt_h=dt_h, q_in_w_m2=q_in_w_m2, regime_id=regime_id)
    rel_err = abs(dT_imp - dT_exp) / max(abs(dT_exp), 1e-6)
    return {
        "compare_id": "IMPLICIT_EXPLICIT_SKIN_STEP_v1",
        "thickness_m": skin_m,
        "dt_h": dt_h,
        "q_in_w_m2": q_in_w_m2,
        "dT_surface_implicit_k": round(dT_imp, 6),
        "dT_surface_explicit_k": round(dT_exp, 6),
        "relative_error": round(rel_err, 6),
        "agree_within_15pct": rel_err <= 0.15,
        "oracle": "CITED_BIND",
        "binds": ["results/platform_bpass/moon/THERMAL_TRANSIENT_BIND_v1.json"],
    }


def zone_from_regime(regime_id: str) -> str:
    return "psr_floor" if regime_id == "psr_floor" else "rim_sun"


def flux_bc_from_env(env: EnvironmentStateV1) -> dict[str, float]:
    """Surface energy BC — q_in into regolith; q_net_bind = q_rad − q_solar (bind convention)."""
    zone = zone_from_regime(env.regime_id)  # type: ignore[arg-type]
    t_surf = env.thermal_column.t_surface_k
    vac = load_vacuum_bc_bind()
    ref_illum = float(vac.get("rim_illumination_frac") or 0.96)
    oblique_bind = rim_oblique_solar_scale(vac_bind=vac) if zone == "rim_sun" else 1.0
    raw_dyn = env.bc_solar.get("oblique_solar_scale")
    if raw_dyn is not None and zone == "rim_sun":
        oblique = oblique_bind * float(raw_dyn)
    else:
        oblique = oblique_bind

    sigma = float(vac.get("stefan_boltzmann_w_m2_k4") or 5.670374419e-8)
    eps = float(vac.get("surface_emissivity_regolith") or 0.95)
    t_sky = float((vac.get("sky_temperature_k") or {}).get("deep_space") or 3.0)
    solar = float(vac.get("solar_constant_w_m2") or 1361.0)
    albedo = float(vac.get("albedo_highland") or 0.12)

    raw_illum = env.bc_solar.get("illum_frac")
    raw_flare = env.bc_solar.get("flare_multiplier")
    illum = float(ref_illum if raw_illum is None else raw_illum)
    flare = float(1.0 if raw_flare is None else raw_flare)

    if zone == "rim_sun":
        q_solar = (1.0 - albedo) * solar * illum * oblique * flare
    else:
        q_solar = 0.0

    q_rad = eps * sigma * (t_surf**4 - t_sky**4)
    q_net_bind = q_rad - q_solar
    q_in = q_solar - q_rad

    return {
        "q_in_w_m2": q_in,
        "q_net_bind_w_m2": q_net_bind,
        "q_solar_w_m2": q_solar,
        "q_rad_w_m2": q_rad,
        "oblique_scale": oblique,
        "t_surf_k": t_surf,
    }


def q_net_from_bc(env: EnvironmentStateV1) -> float:
    """Bind-reporting flux q_rad − q_solar (logging); integrator uses q_in_w_m2."""
    return float(flux_bc_from_env(env)["q_net_bind_w_m2"])


def apply_bc_from_env(env: EnvironmentStateV1) -> dict[str, float]:
    return flux_bc_from_env(env)


def column_init_from_binds(
    *,
    regime_id: str = "rim_sunlit",
    n_nodes: int | None = None,
    depth_m: float | None = None,
    material_id: str | None = None,
) -> ThermalColumnV1:
    init = _method_init_defaults()
    n = int(n_nodes if n_nodes is not None else init.get("n_nodes") or 8)
    depth = float(depth_m if depth_m is not None else init.get("depth_m") or 2.0)
    mat = material_id or str(init.get("material_id") or "highland_regolith_loose")

    vac = load_vacuum_bc_bind()
    sky = vac.get("sky_temperature_k") or {}
    t_surf = float(sky.get("rim_effective") or 220.0)
    if regime_id == "psr_floor":
        t_surf = float(sky.get("psr_effective") or 70.0)

    z_m = [depth * i / max(n - 1, 1) for i in range(n)]
    t_k: list[float] = []
    for z in z_m:
        if regime_id == "psr_floor" and z > 0.0:
            t_k.append(t_surf + float(psr_subsurface_delta_k(depth_m=z)["delta_t_k_vs_legacy_model"]))
        else:
            t_k.append(t_surf)

    mean_t = sum(t_k) / max(len(t_k), 1)
    k_row = (
        effective_k_with_cryo_leg(mat, t_k=mean_t)
        if regime_id == "psr_floor"
        else effective_k_w_mk(mat, t_k=mean_t)
    )
    stacks = load_transient_bind().get("stack_thickness_classes_m") or {}
    skin_m = float(stacks.get("lc2_micro") or 0.052)
    _ = thermal_time_constant_s(thickness_m=skin_m, k_w_mk=float(k_row["k_w_mk"]))

    return ThermalColumnV1(
        z_m=z_m,
        t_k=t_k,
        k_w_mk=float(k_row["k_w_mk"]),
        n_nodes=n,
    )


def rim_steady_state_check(*, regime_id: str = "rim_sunlit", t_tol_k: float = 2.0) -> dict[str, Any]:
    """Falsifier — at rim_effective with oblique scale, q_in ≈ 0."""
    env = EnvironmentStateV1(
        regime_id=regime_id,
        bc_solar={"illum_frac": load_vacuum_bc_bind().get("rim_illumination_frac", 0.96), "flare_multiplier": 1.0},
        bc_vacuum={},
        thermal_column=column_init_from_binds(regime_id=regime_id),
        dust={},
        radiation={},
        mechanical={},
    )
    flux = flux_bc_from_env(env)
    return {
        "check_id": "RIM_OBLIQUE_STEADY_STATE_v1",
        "t_surf_k": env.thermal_column.t_surface_k,
        "q_in_w_m2": round(flux["q_in_w_m2"], 4),
        "oblique_scale": round(flux["oblique_scale"], 6),
        "pass": abs(flux["q_in_w_m2"]) <= max(abs(flux["q_solar_w_m2"]), 1.0) * 0.05,
        "oracle": "CITED_BIND",
    }
