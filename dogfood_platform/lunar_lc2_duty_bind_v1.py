"""LC-2 FOC workload bind — duty_on · f_clock → polar thermal wear stress index."""
from __future__ import annotations

from typing import Any

from dogfood_platform.lunar_lc2_package_harness_v1 import load_lc2_workload_bind

_REF_CLOCK_HZ = 48_000_000.0
_REF_TRANSITIONS_PER_CYCLE = 2.0
_STRESS_COEFF = 0.25


def evaluate_lc2_duty_bind() -> dict[str, Any]:
    bind = load_lc2_workload_bind()
    duty_on = float(bind.get("duty_on") or 0.5)
    f_clock = float(bind.get("f_clock_hz") or _REF_CLOCK_HZ)
    transitions = float(bind.get("transitions_per_cycle") or _REF_TRANSITIONS_PER_CYCLE)
    duty_index = duty_on * (f_clock / _REF_CLOCK_HZ) * (transitions / _REF_TRANSITIONS_PER_CYCLE)
    thermal_stress_mult = round(1.0 + _STRESS_COEFF * duty_index, 6)
    cites = [c.get("formula_id") for c in bind.get("cite") or [] if c.get("formula_id")]
    return {
        "workload_id": bind.get("workload_id"),
        "duty_on": duty_on,
        "f_clock_hz": f_clock,
        "transitions_per_cycle": transitions,
        "duty_index": round(duty_index, 6),
        "thermal_stress_mult": thermal_stress_mult,
        "oracle": "CITED_BIND",
        "workload_bind": "results/platform_bpass/w0_workload_lc2_foc_bound_v1.json",
        "l0_cites": cites + ["E1_SP", "E2_AF", "EMBEDDED_MCU_CLOCK_CLASS"],
        "falsifier": "thermal_delta_vth_mv scales when duty_on or f_clock_hz changes",
    }
