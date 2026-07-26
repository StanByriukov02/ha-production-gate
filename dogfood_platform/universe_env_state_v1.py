"""U4 environment state — physical axes contract (schema + validate + bus snapshot)."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SCHEMA = _REPO / "results" / "platform_bpass" / "universe" / "ENV_STATE_PHYSICS_SCHEMA_v1.json"
_METHOD_BIND = _REPO / "results" / "platform_bpass" / "universe" / "ENV_STATE_PHYSICS_METHOD_BIND_v1.json"
_ENV_BIND = _REPO / "results" / "platform_bpass" / "universe" / "ENV_DRIVER_BIND_v1.json"

REGIME_IDS = frozenset({"rim_sunlit", "psr_floor", "chamber_sunlit"})

_REGIME_TO_DUST_ZONE = {
    "rim_sunlit": "rim_sun",
    "chamber_sunlit": "rim_sun",
    "psr_floor": "psr_floor",
}


def _dust_default_ingress(regime_id: str, dust_ax: dict[str, Any]) -> float:
    """Prefer DUST_INGRESS_BIND zone rate (cite owner); ENV_DRIVER typical only if bind absent."""
    from dogfood_platform.lunar_dust_ingress_v1 import ingress_rate_g_m2_per_sol

    zone = _REGIME_TO_DUST_ZONE.get(regime_id, "rim_sun")
    try:
        return float(ingress_rate_g_m2_per_sol(zone))  # type: ignore[arg-type]
    except (FileNotFoundError, KeyError):
        row = dust_ax.get("ingress_g_m2_per_sol") or {}
        if "typical" not in row:
            raise KeyError("dust ingress missing from DUST_INGRESS_BIND and ENV_DRIVER") from None
        return float(row["typical"])


def _dust_default_e_index(regime_id: str, dust_ax: dict[str, Any]) -> float:
    from dogfood_platform.lunar_dust_ingress_v1 import electrostatic_index

    zone = _REGIME_TO_DUST_ZONE.get(regime_id, "rim_sun")
    try:
        return float(electrostatic_index(zone)["electrostatic_index"])  # type: ignore[arg-type]
    except (FileNotFoundError, KeyError):
        row = dust_ax.get("electrostatic_index") or {}
        if "typical" not in row:
            raise KeyError("dust e_index missing from DUST_INGRESS_BIND and ENV_DRIVER") from None
        return float(row["typical"])


@dataclass
class LawIO:
    law_id: str
    reads: list[str]
    writes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActiveWindow:
    event_id: str
    law_id: str
    start_h: float
    end_h: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ThermalColumnV1:
    z_m: list[float]
    t_k: list[float]
    k_w_mk: float
    n_nodes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def t_surface_k(self) -> float:
        return self.t_k[0] if self.t_k else float("nan")

    @property
    def t_subsurface_k(self) -> float:
        return self.t_k[-1] if self.t_k else float("nan")


@dataclass
class EnvironmentStateV1:
    regime_id: str
    bc_solar: dict[str, float]
    bc_vacuum: dict[str, float]
    thermal_column: ThermalColumnV1
    dust: dict[str, float]
    radiation: dict[str, float]
    mechanical: dict[str, float]
    active_windows: list[ActiveWindow] = field(default_factory=list)
    t_h: float = 0.0
    law_io: dict[str, LawIO] = field(default_factory=dict)
    storm_id: str = ""
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = {
            "regime_id": self.regime_id,
            "bc_solar": dict(self.bc_solar),
            "bc_vacuum": dict(self.bc_vacuum),
            "thermal_column": self.thermal_column.to_dict(),
            "dust": dict(self.dust),
            "radiation": dict(self.radiation),
            "mechanical": dict(self.mechanical),
            "active_windows": [w.to_dict() for w in self.active_windows],
            "t_h": self.t_h,
            "law_io": {k: v.to_dict() for k, v in self.law_io.items()},
            "storm_id": self.storm_id,
            "seed": self.seed,
        }
        return d

    def to_bus_env(self) -> dict[str, Any]:
        """Snapshot for universe_state bus / storm integrator (U4)."""
        return {
            "regime_id": self.regime_id,
            "t_h": self.t_h,
            "solar": {
                "flare_multiplier": self.bc_solar.get("flare_multiplier", 1.0),
                "q_solar_w_m2": self.bc_solar.get("q_solar_w_m2", 1361.0),
                "illum_frac": self.bc_solar.get("illum_frac", 0.96),
            },
            "vacuum_thermal": {
                "t_surf_k": self.thermal_column.t_surface_k,
                "pressure_torr": self.bc_vacuum.get("p_torr", 1e-6),
            },
            "thermal_column": self.thermal_column.to_dict(),
            "dust_charge": {
                "mass_loading_g_m2": self.dust.get("loading_g_m2", 0.0),
                "ingress_g_m2_per_sol": self.dust.get("ingress_rate_g_m2_sol", 0.08),
                "electrostatic_index": self.dust.get("e_index", 0.85),
            },
            "radiation": {
                "dose_gy_accum": self.radiation.get("dose_gy", 0.0),
                "dose_gy": self.radiation.get("dose_gy", 0.0),
                "incident_dose_gy": self.radiation.get("incident_dose_gy", 0.0),
                "albedo_dose_gy": self.radiation.get("albedo_dose_gy", 0.0),
                "albedo_fraction": self.radiation.get("albedo_fraction", 0.0),
                "see_events": self.radiation.get("see_rate_1_per_yr", 0.0),
                "see_rate_1_per_yr": self.radiation.get("see_rate_1_per_yr", 0.0),
                "see_albedo_mv": self.radiation.get("see_albedo_mv", 0.0),
                "shield_areal_g_cm2": self.radiation.get("shield_areal_g_cm2", 0.0),
                "tier": self.radiation.get("tier", "PROXY_CHAT"),
                "flare_scale": self.radiation.get("flare_scale", 1.0),
                "dose_rate_gy_per_h": self.radiation.get("dose_rate_gy_per_h", 0.0),
                "rate_oracle": self.radiation.get("rate_oracle"),
                "rate_from_rust": bool(self.radiation.get("rate_from_rust")),
                "rate_cache_dt_scaled": bool(self.radiation.get("rate_cache_dt_scaled")),
            },
            "mechanical": dict(self.mechanical),
            "active_window_count": len(self.active_windows),
        }


def load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _law_io_from_schema() -> dict[str, LawIO]:
    schema = load_schema()
    out: dict[str, LawIO] = {}
    for axis, spec in (schema.get("axes") or {}).items():
        out[axis] = LawIO(
            law_id=str(spec["law_id"]),
            reads=list(spec.get("reads") or []),
            writes=list(spec.get("writes") or []),
        )
    return out


def _thermal_column_defaults(regime_id: str = "rim_sunlit") -> ThermalColumnV1:
    from dogfood_platform.universe_env_thermal_column_v1 import column_init_from_binds

    return column_init_from_binds(regime_id=regime_id)


def fresh(
    storm_id: str,
    *,
    seed: int = 0,
    regime_id: str = "rim_sunlit",
    t_h: float = 0.0,
) -> EnvironmentStateV1:
    env_defaults: dict[str, Any] = {}
    if _ENV_BIND.is_file():
        env_defaults = json.loads(_ENV_BIND.read_text(encoding="utf-8"))
    axes = env_defaults.get("driver_axes") or {}
    solar_ax = axes.get("solar") or {}
    vac_ax = axes.get("vacuum_thermal") or {}
    dust_ax = axes.get("dust_charge") or {}

    bc_solar = {
        "q_solar_w_m2": float((solar_ax.get("solar_constant_w_m2") or {}).get("typical") or 1361.0),
        "illum_frac": float((solar_ax.get("illum_frac_rim") or {}).get("typical") or 0.96),
        "flare_multiplier": float((solar_ax.get("flare_multiplier") or {}).get("typical") or 1.0),
    }
    bc_vacuum = {
        "p_torr": float((vac_ax.get("pressure_torr") or {}).get("typical") or 1e-6),
        "t_sky_k": 3.0,
        "h_c_w_m2k": 0.0,
    }
    dust = {
        "ingress_rate_g_m2_sol": float(_dust_default_ingress(regime_id, dust_ax)),
        "loading_g_m2": 0.0,
        "e_index": float(_dust_default_e_index(regime_id, dust_ax)),
    }
    from dogfood_platform.universe_env_radiation_v1 import radiation_env_defaults

    radiation_raw = radiation_env_defaults()
    radiation = {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in radiation_raw.items()}
    mechanical = {"impulse_scale": 1.0, "jerk_peak": 0.0}

    return EnvironmentStateV1(
        storm_id=storm_id,
        seed=seed,
        regime_id=regime_id,
        bc_solar=bc_solar,
        bc_vacuum=bc_vacuum,
        thermal_column=_thermal_column_defaults(regime_id=regime_id),
        dust=dust,
        radiation=radiation,
        mechanical=mechanical,
        active_windows=[],
        t_h=t_h,
        law_io=_law_io_from_schema(),
    )


def validate(env: EnvironmentStateV1) -> list[str]:
    errors: list[str] = []
    schema = load_schema()

    if env.regime_id not in REGIME_IDS:
        errors.append(f"regime_id invalid: {env.regime_id}")

    tc = env.thermal_column
    for key in schema.get("thermal_column_required") or []:
        val = getattr(tc, key, None) if hasattr(tc, key) else (tc.to_dict().get(key))
        if val is None or (isinstance(val, list) and len(val) == 0):
            errors.append(f"thermal_column missing {key}")

    if tc.n_nodes != len(tc.z_m) or tc.n_nodes != len(tc.t_k):
        errors.append("thermal_column n_nodes mismatch z_m/t_k length")

    if not env.law_io:
        errors.append("law_io empty")
    for axis, spec in (schema.get("axes") or {}).items():
        io = env.law_io.get(axis)
        if io is None:
            errors.append(f"law_io missing axis {axis}")
            continue
        for req in schema.get("law_io_required_per_axis") or []:
            if not getattr(io, req, None) and not (isinstance(getattr(io, req, None), list) and getattr(io, req) == []):
                if req in ("reads", "writes") and not getattr(io, req):
                    errors.append(f"{axis}.{req} empty")

    for w in env.active_windows:
        if w.end_h <= w.start_h:
            errors.append(f"active_window invalid span: {w.event_id}")

    for k, v in env.bc_solar.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            errors.append(f"bc_solar.{k} non-finite")

    return errors


def validate_or_raise(env: EnvironmentStateV1) -> None:
    errs = validate(env)
    if errs:
        raise ValueError("; ".join(errs))


def from_dict(payload: dict[str, Any]) -> EnvironmentStateV1:
    tc_raw = payload.get("thermal_column") or {}
    regime = str(payload.get("regime_id") or "rim_sunlit")
    from dogfood_platform.universe_env_thermal_column_v1 import column_init_from_binds

    default_tc = column_init_from_binds(regime_id=regime)
    tc = ThermalColumnV1(
        z_m=list(tc_raw.get("z_m") or default_tc.z_m),
        t_k=list(tc_raw.get("t_k") or default_tc.t_k),
        k_w_mk=float(tc_raw.get("k_w_mk") or default_tc.k_w_mk),
        n_nodes=int(tc_raw.get("n_nodes") or len(tc_raw.get("z_m") or default_tc.z_m)),
    )
    windows = [
        ActiveWindow(
            event_id=str(w.get("event_id")),
            law_id=str(w.get("law_id")),
            start_h=float(w.get("start_h")),
            end_h=float(w.get("end_h")),
        )
        for w in payload.get("active_windows") or []
    ]
    law_io_raw = payload.get("law_io") or {}
    if law_io_raw and all(isinstance(v, dict) for v in law_io_raw.values()):
        law_io = {
            k: LawIO(law_id=str(v["law_id"]), reads=list(v.get("reads") or []), writes=list(v.get("writes") or []))
            for k, v in law_io_raw.items()
        }
    else:
        law_io = _law_io_from_schema()

    env = EnvironmentStateV1(
        storm_id=str(payload.get("storm_id") or ""),
        seed=int(payload.get("seed") or 0),
        regime_id=str(payload.get("regime_id") or "rim_sunlit"),
        bc_solar=dict(payload.get("bc_solar") or {}),
        bc_vacuum=dict(payload.get("bc_vacuum") or {}),
        thermal_column=tc,
        dust=dict(payload.get("dust") or {}),
        radiation=dict(payload.get("radiation") or {}),
        mechanical=dict(payload.get("mechanical") or {}),
        active_windows=windows,
        t_h=float(payload.get("t_h") or 0.0),
        law_io=law_io,
    )
    validate_or_raise(env)
    return env
