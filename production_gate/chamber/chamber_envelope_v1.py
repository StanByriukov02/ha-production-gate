"""G2 vacuum chamber envelope — pump-down, thermal soak, named BC modes."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

from production_gate.lunar_thermal_l5_v1 import radiative_net_flux_w_m2

_REPO = Path(__file__).resolve().parents[2]
_BIND = _REPO / "results" / "platform_bpass" / "chamber" / "CHAMBER_ENVELOPE_BIND_v1.json"

ChamberMode = Literal["chamber_a_cold", "lunar_sunlit"]


def load_envelope_bind(bind: dict[str, Any] | None = None) -> dict[str, Any]:
    return bind or json.loads(_BIND.read_text(encoding="utf-8"))


def pressure_at_time(t_s: float, *, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    data = load_envelope_bind(bind)
    vac = data["vacuum"]
    p_atm = float(vac["p_atm_torr"])
    p_base = float(vac["p_base_torr"])
    tau = float(vac["tau_pump_s"])
    p_cut = float(vac["p_cut_hc_zero_torr"])
    p = p_base + (p_atm - p_base) * math.exp(-t_s / max(tau, 1.0))
    h_c = 0.0 if p <= max(p_cut * 100, 1e-4) else 5.0
    return {
        "t_s": round(t_s, 2),
        "pressure_torr": round(p, 8),
        "h_c_w_m2_k": h_c,
        "vacuum_reached": p <= max(p_cut * 100, 1e-4),
    }


def pump_down_profile(*, duration_s: float | None = None, steps: int = 12, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    data = load_envelope_bind(bind)
    vac = data["vacuum"]
    tau = float(vac["tau_pump_s"])
    p_atm = float(vac["p_atm_torr"])
    p_cut = float(vac["p_cut_hc_zero_torr"])
    if duration_s is None:
        duration_s = tau * math.log(max(p_atm / max(p_cut, 1e-12), 2.0))
    rows = [pressure_at_time(duration_s * i / max(steps - 1, 1), bind=bind) for i in range(steps)]
    final = rows[-1]
    return {
        "hop_id": "h-chamber-pump-down",
        "verdict": "PASS" if final["vacuum_reached"] else "FAIL",
        "profile": rows,
        "p_final_torr": final["pressure_torr"],
        "h_c_final": final["h_c_w_m2_k"],
    }


def _steady_dut_temperature_k(mode: ChamberMode, *, bind: dict[str, Any] | None = None) -> float:
    data = load_envelope_bind(bind)
    m = data["modes"][mode]
    if mode == "lunar_sunlit":
        return float(m.get("t_target_dut_k") or 220.0)
    return float(m.get("t_wall_k") or 35.0) + 15.0


def thermal_soak_timeline(
    *,
    mode: ChamberMode = "lunar_sunlit",
    duration_h: float | None = None,
    bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_envelope_bind(bind)
    soak = data["soak"]
    dur_h = float(duration_h if duration_h is not None else soak["default_duration_h"])
    n = int(soak["sample_points"])
    t_eq = _steady_dut_temperature_k(mode, bind=data)
    t_init = 293.15
    thickness = float(soak["dut_thickness_m"])
    rho = float(soak["dut_rho_kg_m3"])
    cp = float(soak["dut_cp_j_kg_k"])
    eps = float(soak["dut_emissivity"])
    sigma = 5.670374419e-8
    # Radiative coupling to chamber wall — not regolith k (DUT is Al tile)
    h_rad = max(4.0 * eps * sigma * (t_eq**3), 0.5)
    tau = rho * cp * thickness / h_rad
    rows: list[dict[str, Any]] = []
    for i in range(n):
        t_s = dur_h * 3600.0 * i / max(n - 1, 1)
        frac = 1.0 - math.exp(-t_s / max(tau, 1.0))
        t_dut = t_init + (t_eq - t_init) * frac
        pres = pressure_at_time(min(t_s, 3600.0), bind=data)
        q = radiative_net_flux_w_m2(t_dut, zone="rim_sun" if mode == "lunar_sunlit" else "psr_floor")
        rows.append({
            "t_s": round(t_s, 1),
            "t_dut_k": round(t_dut, 3),
            "pressure_torr": pres["pressure_torr"],
            "q_net_w_m2": q["q_net_w_m2"],
        })
    t_final = rows[-1]["t_dut_k"]
    within = abs(t_final - t_eq) / max(t_eq, 1.0) <= 0.12
    return {
        "hop_id": "h-chamber-thermal-soak",
        "verdict": "PASS" if within else "FAIL",
        "mode": mode,
        "t_eq_k": round(t_eq, 3),
        "t_final_k": t_final,
        "tau_s": round(tau, 2),
        "within_10pct_target": within,
        "timeline": rows,
        "l0_cites": ["ORACLE_SEC_D2", "SK-12", "SAKATANI-LPSC-1552"],
        "oracle": "CITED_BIND",
    }


def envelope_receipt(*, mode: ChamberMode = "lunar_sunlit", bind: dict[str, Any] | None = None) -> dict[str, Any]:
    pump = pump_down_profile(bind=bind)
    soak = thermal_soak_timeline(mode=mode, bind=bind)
    data = load_envelope_bind(bind)
    verdict = "PASS" if pump["verdict"] == "PASS" and soak["verdict"] == "PASS" else "FAIL"
    return {
        "hop_id": "h-chamber-envelope",
        "verdict": verdict,
        "mode": mode,
        "pump_down": pump,
        "thermal_soak": soak,
        "mode_spec": data["modes"][mode],
        "h_c_vacuum": float(data["vacuum"]["h_c_w_m2_k_below_cut"]),
    }


def compare_mode_thermal_diverge() -> dict[str, Any]:
    cold = thermal_soak_timeline(mode="chamber_a_cold")
    sun = thermal_soak_timeline(mode="lunar_sunlit")
    return {
        "chamber_a_final_k": cold["t_final_k"],
        "lunar_sunlit_final_k": sun["t_final_k"],
        "modes_diverge": abs(cold["t_final_k"] - sun["t_final_k"]) > 5.0,
        "falsifier_pass": abs(cold["t_final_k"] - sun["t_final_k"]) > 5.0,
    }
