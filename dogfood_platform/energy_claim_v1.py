"""H7 Energy claim — thin Python orchestration over Rust ha-energy-ledger.

TABU: Python as production oracle for balance / kinetic tax.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BIN_STEM = "ha-energy-ledger"
SCHEMA = "energy_claim_v1"
DEFAULT_BUDGET_J = 1.0
BEKKER_SLICE_J = 1.0


class EnergyClaimError(ValueError):
    """Raised when energy claim is missing or unbalanced."""


def _exe_name() -> str:
    return _BIN_STEM + (".exe" if sys.platform == "win32" else "")


def find_ha_energy_ledger_bin() -> Path:
    env = (os.environ.get("HA_ENERGY_LEDGER_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(
                f"HA_ENERGY_LEDGER_BIN set but not a file: {p} "
                "(no pure-Python balance fallback)"
            )
        return p.resolve()
    name = _exe_name()
    for candidate in (
        _REPO / "target" / "release" / name,
        _REPO / "target" / "debug" / name,
    ):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "ha-energy-ledger binary missing — set HA_ENERGY_LEDGER_BIN or "
        "cargo build -p ha_energy_ledger --release "
        "(no pure-Python balance fallback)"
    )


def _run_cli(args: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    bin_path = find_ha_energy_ledger_bin()
    return subprocess.run(
        [str(bin_path), *args],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        **hidden_run_kwargs(),
    )


def kinetic_tax_joules(magnitude: float) -> float:
    """Soft kinetic tax via Rust `tax --magnitude`."""
    proc = _run_cli(["tax", "--magnitude", str(float(magnitude))])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-energy-ledger tax failed: {err}")
    line = (proc.stdout or "").strip().splitlines()[-1].strip()
    try:
        val = float(line)
    except ValueError as exc:
        raise RuntimeError(f"ha-energy-ledger tax returned non-float: {line!r}") from exc
    if not (val == val) or val < 0:  # NaN check
        raise RuntimeError(f"ha-energy-ledger tax not usable: {val!r}")
    return val


def compaction_work_joules(rc_n: float, distance_m: float) -> float:
    """Bekker compaction work via Rust `work --rc-n --distance-m` (N·m = J)."""
    proc = _run_cli(
        ["work", "--rc-n", str(float(rc_n)), "--distance-m", str(float(distance_m))]
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-energy-ledger work failed: {err}")
    line = (proc.stdout or "").strip().splitlines()[-1].strip()
    try:
        val = float(line)
    except ValueError as exc:
        raise RuntimeError(f"ha-energy-ledger work returned non-float: {line!r}") from exc
    if not (val == val) or val < 0:
        raise RuntimeError(f"ha-energy-ledger work not usable: {val!r}")
    return val


def emit_energy_claim(
    *,
    budget_j: float,
    spent_actuation_j: float,
    kinetic_tax_j: float,
    claim_id: str,
) -> dict[str, Any]:
    """Emit balanced claim via Rust `emit`."""
    proc = _run_cli(
        [
            "emit",
            "--budget",
            str(float(budget_j)),
            "--spent-actuation",
            str(float(spent_actuation_j)),
            "--kinetic-tax",
            str(float(kinetic_tax_j)),
            "--claim-id",
            str(claim_id),
        ]
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-energy-ledger emit failed: {err}")
    claim = json.loads(proc.stdout)
    validate_energy_claim(claim)
    return claim


def validate_energy_claim(doc: dict[str, Any] | str | Path) -> None:
    """Validate via Rust `validate --json`."""
    import tempfile

    if isinstance(doc, Path):
        json_path = doc
        if not json_path.is_file():
            raise FileNotFoundError(f"energy claim json not found: {json_path}")
        proc = _run_cli(["validate", "--json", str(json_path)])
    else:
        payload = doc if isinstance(doc, str) else json.dumps(doc, indent=2, ensure_ascii=False)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(payload if payload.endswith("\n") else payload + "\n")
            json_path = Path(tmp.name)
        try:
            proc = _run_cli(["validate", "--json", str(json_path)])
        finally:
            json_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise EnergyClaimError(f"energy_claim validate FAIL: {err}")


def _command_magnitude(actuation_truth: dict[str, Any]) -> float:
    """Proxy magnitude from actuation legs (cursor deltas + command tokens)."""
    mag = 0.0
    for role in ("stub", "planner"):
        leg = actuation_truth.get(role) or {}
        if not isinstance(leg, dict):
            continue
        mag += abs(float(leg.get("cursor_delta_m") or 0.0))
        cmd = str(leg.get("command") or "").strip().lower()
        if cmd and cmd not in ("hold", "idle", "recover", ""):
            mag += 1.0
        elif cmd in ("recover",):
            mag += 0.5
    return mag


def _distance_m_from_actuation(actuation_truth: dict[str, Any]) -> float:
    dist = 0.0
    for role in ("stub", "planner"):
        leg = actuation_truth.get(role) or {}
        if not isinstance(leg, dict):
            continue
        dist += abs(float(leg.get("cursor_delta_m") or 0.0))
    return dist


def _bekker_adversity(*, rc_n: float, sink_mm: float, drawbar_n: float) -> float:
    """Dimensionless Dual adversity — high Rc/sink + low drawbar. No orphan /100 /50."""
    return abs(float(rc_n)) + abs(float(sink_mm)) + 1.0 / max(abs(float(drawbar_n)), 1e-9)


def _magnitude_from_bekker_physics(
    physics: dict[str, Any] | None,
    actuation_truth: dict[str, Any],
) -> float:
    """Tax magnitude = dual_share of Bekker adversity (+ drive Rust extras). No orphan scales."""
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_spent_j

    cmd = _command_magnitude(actuation_truth)
    if not isinstance(physics, dict):
        return cmd
    dual = physics.get("bekker_dual") if isinstance(physics.get("bekker_dual"), dict) else {}
    rc = float(physics.get("compaction_resistance_n") or 0.0)
    sink = float(physics.get("sinkage_mm") or 0.0)
    drawbar = float(physics.get("drawbar_pull_n") or 0.0)
    m = _bekker_adversity(rc_n=rc, sink_mm=sink, drawbar_n=drawbar)
    m_s = _bekker_adversity(
        rc_n=float(dual.get("rc_safe_n") or rc),
        sink_mm=float(dual.get("sink_safe_mm") or sink),
        drawbar_n=float(dual.get("drawbar_safe_n") or drawbar),
    )
    m_h = _bekker_adversity(
        rc_n=float(dual.get("rc_hostile_n") or rc),
        sink_mm=float(dual.get("sink_hostile_mm") or sink),
        drawbar_n=float(dual.get("drawbar_hostile_n") or drawbar),
    )
    # Budget 1.0 → mag in [0,1] Dual share; soft command still contributes.
    mag = dual_share_spent_j(
        metric=m, metric_safe=m_s, metric_hostile=m_h, budget_j=1.0
    ) + 0.25 * cmd
    dc = physics.get("drive_chain")
    if isinstance(dc, dict):
        # E1: worn gear + dry joint raise thought tax Dual (dimensionless Rust packs).
        n_n = max(float(dc.get("n_n") or 1.0), 1e-9)
        mag += float(dc.get("gear_loss_frac") or 0.0) + abs(float(dc.get("f_friction_n") or 0.0)) / n_n
    return mag


def _spent_from_bekker_work(
    physics: dict[str, Any] | None,
    actuation_truth: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Spent from Rust W=|Rc|·|s| mapped via dual_share — no work/1000 orphan."""
    from dogfood_platform.dual_spent_normalize_v1 import dual_share_receipt

    dist = _distance_m_from_actuation(actuation_truth)
    # Teaching hop floor so zero-delta recover still pays soil work fraction.
    dist_eff = max(dist, 0.05)
    if isinstance(physics, dict) and physics.get("compaction_resistance_n") is not None:
        rc = float(physics.get("compaction_resistance_n") or 0.0)
        work = compaction_work_joules(rc, dist_eff)
        dual = physics.get("bekker_dual") if isinstance(physics.get("bekker_dual"), dict) else {}
        work_s = compaction_work_joules(float(dual.get("rc_safe_n") or rc), dist_eff)
        work_h = compaction_work_joules(float(dual.get("rc_hostile_n") or rc), dist_eff)
        share = dual_share_receipt(
            metric=work,
            metric_safe=work_s,
            metric_hostile=work_h,
            budget_j=BEKKER_SLICE_J,
            metric_id="bekker_Rc*s",
        )
        spent = float(share["spent_j"])
        honesty = {
            "spent_from_bekker_rc_distance": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "cursor_magic_retired": True,
            "rc_n": rc,
            "distance_m": dist_eff,
            "work_j_raw": work,
            "work_safe_j": work_s,
            "work_hostile_j": work_h,
            "dual_share": share,
            "scale": "dual_share(budget*|W|/(|W_s|+|W_h|))",
            "oracle_work": "ha_energy_ledger compaction_work_joules",
        }
        # E1: drive-chain embed (motor η + joint μ) raises Hostile parasitic spend.
        from dogfood_platform.drive_chain_embed_v1 import parasitic_spent_add_j

        add, drive_h = parasitic_spent_add_j(
            physics.get("drive_chain") if isinstance(physics.get("drive_chain"), dict) else None,
            base_spent_j=spent,
            distance_m=dist_eff,
        )
        spent = spent + add
        honesty.update(drive_h)
        return round(spent, 6), honesty
    # Fallback only when Dual physics missing — marked honest (not Dual path).
    spent = 0.05 + 0.2 * dist
    return round(spent, 6), {
        "spent_from_bekker_rc_distance": False,
        "spent_dual_share_only": False,
        "no_orphan_scale": False,
        "cursor_magic_retired": False,
        "fallback_cursor_proxy": True,
        "spent_from_drive_chain_rust": False,
    }


def build_energy_claim_from_actuation(
    actuation_truth: dict[str, Any],
    *,
    claim_id: str,
    budget_j: float = DEFAULT_BUDGET_J,
    physics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build H7 claim: Rust tax + Rust work/emit. Python derives Dual physics inputs."""
    from dogfood_platform.ballistics_kepler_embed_v1 import apply_ballistics_kepler_to_spent
    from dogfood_platform.dust_envelope_embed_v1 import apply_dust_envelope_to_spent
    from dogfood_platform.env_budget_embed_v1 import apply_env_budget_to_spent
    from dogfood_platform.storm_env_embed_v1 import apply_storm_env_to_spent
    from dogfood_platform.traverse_mechanical_embed_v1 import apply_traverse_mechanical_to_spent
    from dogfood_platform.materials_thermal_embed_v1 import apply_materials_thermal_to_spent
    from dogfood_platform.orbit_residual_embed_v1 import apply_orbit_residual_to_spent
    from dogfood_platform.thermal_world_embed_v1 import apply_thermal_world_to_spent
    from dogfood_platform.isru_sinter_embed_v1 import apply_isru_sinter_to_spent
    from dogfood_platform.atm_drag_embed_v1 import apply_atm_drag_to_spent
    from dogfood_platform.acoustic_embed_v1 import apply_acoustic_to_spent
    from dogfood_platform.li_qc_embed_v1 import apply_li_qc_to_spent
    from dogfood_platform.albedo_dose_embed_v1 import apply_albedo_dose_to_spent
    from dogfood_platform.dust_ingress_embed_v1 import apply_dust_ingress_to_spent
    from dogfood_platform.janosi_embed_v1 import apply_janosi_to_spent
    from dogfood_platform.radiation_rate_embed_v1 import apply_radiation_rate_to_spent
    from dogfood_platform.regolith_thermal_embed_v1 import apply_regolith_thermal_to_spent

    mag = _magnitude_from_bekker_physics(physics, actuation_truth)
    tax = kinetic_tax_joules(mag)
    spent, spent_honesty = _spent_from_bekker_work(physics, actuation_truth)
    env_block = (
        physics.get("env_budget")
        if isinstance(physics, dict) and isinstance(physics.get("env_budget"), dict)
        else None
    )
    storm_block = (
        physics.get("storm_env")
        if isinstance(physics, dict) and isinstance(physics.get("storm_env"), dict)
        else None
    )
    trav_block = (
        physics.get("traverse_mechanical")
        if isinstance(physics, dict) and isinstance(physics.get("traverse_mechanical"), dict)
        else None
    )
    dust_block = (
        physics.get("dust_envelope")
        if isinstance(physics, dict) and isinstance(physics.get("dust_envelope"), dict)
        else None
    )
    mat_block = (
        physics.get("materials_thermal")
        if isinstance(physics, dict) and isinstance(physics.get("materials_thermal"), dict)
        else None
    )
    orbit_block = (
        physics.get("orbit_residual")
        if isinstance(physics, dict) and isinstance(physics.get("orbit_residual"), dict)
        else None
    )
    ball_block = (
        physics.get("ballistics_kepler")
        if isinstance(physics, dict) and isinstance(physics.get("ballistics_kepler"), dict)
        else None
    )
    thermal_block = (
        physics.get("thermal_world")
        if isinstance(physics, dict) and isinstance(physics.get("thermal_world"), dict)
        else None
    )
    sinter_block = (
        physics.get("isru_sinter")
        if isinstance(physics, dict) and isinstance(physics.get("isru_sinter"), dict)
        else None
    )
    drag_block = (
        physics.get("atm_drag")
        if isinstance(physics, dict) and isinstance(physics.get("atm_drag"), dict)
        else None
    )
    acoustic_block = (
        physics.get("acoustic")
        if isinstance(physics, dict) and isinstance(physics.get("acoustic"), dict)
        else None
    )
    li_block = (
        physics.get("li_qc")
        if isinstance(physics, dict) and isinstance(physics.get("li_qc"), dict)
        else None
    )
    albedo_block = (
        physics.get("albedo_dose")
        if isinstance(physics, dict) and isinstance(physics.get("albedo_dose"), dict)
        else None
    )
    ingress_block = (
        physics.get("dust_ingress")
        if isinstance(physics, dict) and isinstance(physics.get("dust_ingress"), dict)
        else None
    )
    janosi_block = (
        physics.get("janosi")
        if isinstance(physics, dict) and isinstance(physics.get("janosi"), dict)
        else None
    )
    rad_block = (
        physics.get("radiation_rate")
        if isinstance(physics, dict) and isinstance(physics.get("radiation_rate"), dict)
        else None
    )
    k_block = (
        physics.get("regolith_thermal")
        if isinstance(physics, dict) and isinstance(physics.get("regolith_thermal"), dict)
        else None
    )
    spent, _env_spent, env_honesty = apply_env_budget_to_spent(spent, env_block)
    spent, _storm_spent, storm_honesty = apply_storm_env_to_spent(spent, storm_block)
    spent, _trav_spent, trav_honesty = apply_traverse_mechanical_to_spent(spent, trav_block)
    spent, _dust_spent, dust_honesty = apply_dust_envelope_to_spent(spent, dust_block)
    spent, _mat_spent, mat_honesty = apply_materials_thermal_to_spent(spent, mat_block)
    spent, _orbit_spent, orbit_honesty = apply_orbit_residual_to_spent(spent, orbit_block)
    spent, _ball_spent, ball_honesty = apply_ballistics_kepler_to_spent(spent, ball_block)
    spent, _thermal_spent, thermal_honesty = apply_thermal_world_to_spent(spent, thermal_block)
    spent, _sinter_spent, sinter_honesty = apply_isru_sinter_to_spent(spent, sinter_block)
    spent, _drag_spent, drag_honesty = apply_atm_drag_to_spent(spent, drag_block)
    spent, _acoustic_spent, acoustic_honesty = apply_acoustic_to_spent(spent, acoustic_block)
    spent, _li_spent, li_honesty = apply_li_qc_to_spent(spent, li_block)
    spent, _albedo_spent, albedo_honesty = apply_albedo_dose_to_spent(spent, albedo_block)
    spent, _ingress_spent, ingress_honesty = apply_dust_ingress_to_spent(spent, ingress_block)
    spent, _janosi_spent, janosi_honesty = apply_janosi_to_spent(spent, janosi_block)
    spent, _rad_spent, rad_honesty = apply_radiation_rate_to_spent(spent, rad_block)
    spent, _k_spent, k_honesty = apply_regolith_thermal_to_spent(spent, k_block)
    embed_spent = (
        bool(env_honesty.get("env_budget_from_rust"))
        or bool(storm_honesty.get("env_storm_from_integrator"))
        or bool(trav_honesty.get("traverse_mechanical_from_bekker"))
        or bool(dust_honesty.get("dust_envelope_from_rust"))
        or bool(mat_honesty.get("materials_thermal_from_rust"))
        or bool(orbit_honesty.get("orbit_residual_from_rust"))
        or bool(ball_honesty.get("ballistics_kepler_from_rust"))
        or bool(thermal_honesty.get("thermal_world_from_rust"))
        or bool(sinter_honesty.get("isru_sinter_from_rust"))
        or bool(drag_honesty.get("atm_drag_from_rust"))
        or bool(acoustic_honesty.get("acoustic_from_rust"))
        or bool(li_honesty.get("li_qc_from_rust"))
        or bool(albedo_honesty.get("albedo_dose_from_rust"))
        or bool(ingress_honesty.get("dust_ingress_from_rust"))
        or bool(janosi_honesty.get("janosi_from_rust"))
        or bool(rad_honesty.get("radiation_rate_from_rust"))
        or bool(k_honesty.get("regolith_thermal_from_rust"))
    )
    if not embed_spent:
        spent = min(spent, max(budget_j - tax, 0.0))
    claim = emit_energy_claim(
        budget_j=budget_j,
        spent_actuation_j=spent,
        kinetic_tax_j=tax,
        claim_id=claim_id,
    )
    honesty = dict(claim.get("honesty") or {})
    honesty.update(spent_honesty)
    honesty.update(env_honesty)
    honesty.update(storm_honesty)
    honesty.update(trav_honesty)
    honesty.update(dust_honesty)
    honesty.update(mat_honesty)
    honesty.update(orbit_honesty)
    honesty.update(ball_honesty)
    honesty.update(thermal_honesty)
    honesty.update(sinter_honesty)
    honesty.update(drag_honesty)
    honesty.update(acoustic_honesty)
    honesty.update(li_honesty)
    honesty.update(albedo_honesty)
    honesty.update(ingress_honesty)
    honesty.update(janosi_honesty)
    honesty.update(rad_honesty)
    honesty.update(k_honesty)
    # F3 conservation honesty: stacked dual_share slices ≠ SI calorimeter.
    honesty["teaching_slice_stack"] = bool(embed_spent)
    honesty["si_joule_calorimeter"] = False
    honesty["no_silent_spent_clamp"] = bool(embed_spent)
    honesty["spent_gt_budget"] = float(spent) > float(budget_j)
    honesty["budget_is_ledger_frame_not_si_sum_cap"] = True
    honesty["conservation_note"] = (
        "named dual_share slices stack into spent; budget_j is ledger frame; "
        "residual may be negative without claiming SI energy balance"
    )
    honesty["tax_magnitude_from_bekker_physics"] = bool(isinstance(physics, dict))
    honesty["tax_magnitude"] = mag
    claim["honesty"] = honesty
    if isinstance(physics, dict):
        claim["physics_bind"] = {
            "oracle": physics.get("oracle"),
            "soil_id": physics.get("soil_id"),
            "compaction_resistance_n": physics.get("compaction_resistance_n"),
            "sinkage_mm": physics.get("sinkage_mm"),
            "drawbar_pull_n": physics.get("drawbar_pull_n"),
            "bekker_from_rust": bool((physics.get("honesty") or {}).get("bekker_from_rust")),
            "drive_chain_from_rust": bool((physics.get("honesty") or {}).get("drive_chain_from_rust")),
            "env_budget_from_rust": bool((physics.get("honesty") or {}).get("env_budget_from_rust")),
            "env_storm_from_integrator": bool(
                (physics.get("honesty") or {}).get("env_storm_from_integrator")
            ),
            "traverse_mechanical_from_bekker": bool(
                (physics.get("honesty") or {}).get("traverse_mechanical_from_bekker")
            ),
            "dust_envelope_from_rust": bool((physics.get("honesty") or {}).get("dust_envelope_from_rust")),
            "materials_thermal_from_rust": bool(
                (physics.get("honesty") or {}).get("materials_thermal_from_rust")
            ),
            "orbit_residual_from_rust": bool(
                (physics.get("honesty") or {}).get("orbit_residual_from_rust")
            ),
            "ballistics_kepler_from_rust": bool(
                (physics.get("honesty") or {}).get("ballistics_kepler_from_rust")
            ),
            "thermal_world_from_rust": bool(
                (physics.get("honesty") or {}).get("thermal_world_from_rust")
            ),
            "isru_sinter_from_rust": bool(
                (physics.get("honesty") or {}).get("isru_sinter_from_rust")
            ),
            "atm_drag_from_rust": bool((physics.get("honesty") or {}).get("atm_drag_from_rust")),
            "acoustic_from_rust": bool((physics.get("honesty") or {}).get("acoustic_from_rust")),
            "li_qc_from_rust": bool((physics.get("honesty") or {}).get("li_qc_from_rust")),
            "albedo_dose_from_rust": bool(
                (physics.get("honesty") or {}).get("albedo_dose_from_rust")
            ),
            "dust_ingress_from_rust": bool(
                (physics.get("honesty") or {}).get("dust_ingress_from_rust")
            ),
            "janosi_from_rust": bool((physics.get("honesty") or {}).get("janosi_from_rust")),
            "radiation_rate_from_rust": bool(
                (physics.get("honesty") or {}).get("radiation_rate_from_rust")
            ),
            "regolith_thermal_from_rust": bool(
                (physics.get("honesty") or {}).get("regolith_thermal_from_rust")
            ),
        }
        dc = physics.get("drive_chain")
        if isinstance(dc, dict):
            claim["drive_chain_bind"] = {
                "motor_pack": dc.get("motor_pack"),
                "joint_pack": dc.get("joint_pack"),
                "eta": dc.get("eta"),
                "mu": dc.get("mu"),
                "parasitic_mult": dc.get("parasitic_mult"),
                "motor_oracle": dc.get("motor_oracle"),
                "joint_oracle": dc.get("joint_oracle"),
            }
        if isinstance(env_block, dict):
            claim["env_budget_bind"] = {
                "budget_factor": env_block.get("budget_factor"),
                "env_pressure": env_block.get("env_pressure"),
                "env_spent_j": env_honesty.get("env_spent_j"),
                "fourier_pack": env_block.get("fourier_pack"),
                "eclipse_orbit": env_block.get("eclipse_orbit"),
                "tid_pack": env_block.get("tid_pack"),
                "battery_pack": env_block.get("battery_pack"),
                "fourier_oracle": env_block.get("fourier_oracle"),
                "eclipse_oracle": env_block.get("eclipse_oracle"),
                "tid_oracle": env_block.get("tid_oracle"),
                "battery_oracle": env_block.get("battery_oracle"),
            }
        if isinstance(storm_block, dict):
            claim["storm_env_bind"] = {
                "storm_id": storm_block.get("storm_id"),
                "dose_gy_final": storm_block.get("dose_gy_final"),
                "storm_spent_j": storm_honesty.get("storm_spent_j"),
                "radiation_mean_flare_scale": storm_block.get("radiation_mean_flare_scale"),
                "thermal_column_final_k": storm_block.get("thermal_column_final_k"),
                "integrator_steps": storm_block.get("integrator_steps"),
                "storm_ok": storm_block.get("storm_ok"),
                "integrator": storm_block.get("integrator"),
            }
        if isinstance(trav_block, dict):
            claim["traverse_mechanical_bind"] = {
                "soil_id": trav_block.get("soil_id"),
                "mlcc_jerk_peak": trav_block.get("mlcc_jerk_peak"),
                "bekker_severity": trav_block.get("bekker_severity"),
                "traverse_spent_j": trav_honesty.get("traverse_spent_j"),
                "compaction_resistance_n": trav_block.get("compaction_resistance_n"),
                "sinkage_mm": trav_block.get("sinkage_mm"),
                "drawbar_pull_n": trav_block.get("drawbar_pull_n"),
                "path_km": trav_block.get("path_km"),
                "oracle": trav_block.get("oracle"),
            }
        if isinstance(dust_block, dict):
            claim["dust_envelope_bind"] = {
                "dust_pressure": dust_block.get("dust_pressure"),
                "dust_spent_j": dust_honesty.get("dust_spent_j"),
                "phi_v": dust_block.get("phi_v"),
                "loft_ratio": dust_block.get("loft_ratio"),
                "mass_g_m2": dust_block.get("mass_g_m2"),
                "charging_oracle": dust_block.get("charging_oracle"),
                "loft_oracle": dust_block.get("loft_oracle"),
                "soiling_oracle": dust_block.get("soiling_oracle"),
            }
        if isinstance(mat_block, dict):
            claim["materials_thermal_bind"] = {
                "sigma_thermal_mpa": mat_block.get("sigma_thermal_mpa"),
                "thermal_spent_j": mat_honesty.get("thermal_spent_j"),
                "dt_k": mat_block.get("dt_k"),
                "materials_oracle": mat_block.get("materials_oracle"),
            }
        if isinstance(orbit_block, dict):
            claim["orbit_residual_bind"] = {
                "orbit_pressure": orbit_block.get("orbit_pressure"),
                "orbit_spent_j": orbit_honesty.get("orbit_spent_j"),
                "fmd_pack": orbit_block.get("fmd_pack"),
                "srp_pack": orbit_block.get("srp_pack"),
                "belt_pack": orbit_block.get("belt_pack"),
                "fmd_oracle": orbit_block.get("fmd_oracle"),
                "srp_oracle": orbit_block.get("srp_oracle"),
                "belt_oracle": orbit_block.get("belt_oracle"),
            }
        if isinstance(ball_block, dict):
            claim["ballistics_kepler_bind"] = {
                "ballistics_spent_j": ball_honesty.get("ballistics_spent_j"),
                "hop_spent_j": ball_block.get("hop_spent_j"),
                "kepler_spent_j": ball_block.get("kepler_spent_j"),
                "apex_m": ball_block.get("apex_m"),
                "v_orb_m_s": ball_block.get("v_orb_m_s"),
                "hop_oracle": ball_block.get("hop_oracle"),
                "visviva_oracle": ball_block.get("visviva_oracle"),
            }
        if isinstance(thermal_block, dict):
            claim["thermal_world_bind"] = {
                "thermal_spent_j": thermal_honesty.get("thermal_spent_j"),
                "thermal_metric": thermal_block.get("thermal_metric"),
                "zone": thermal_block.get("zone"),
                "q_net_w_m2": thermal_block.get("q_net_w_m2"),
                "dT_surface_k": thermal_block.get("dT_surface_k"),
                "psr_cold_trap": thermal_block.get("psr_cold_trap"),
                "radiative_oracle": thermal_block.get("radiative_oracle"),
                "column_oracle": thermal_block.get("column_oracle"),
            }
        if isinstance(sinter_block, dict):
            claim["isru_sinter_bind"] = {
                "sinter_spent_j": sinter_honesty.get("sinter_spent_j"),
                "progress": sinter_block.get("progress"),
                "recipe_id": sinter_block.get("recipe_id"),
                "sinter_ok": sinter_block.get("sinter_ok"),
                "sinter_oracle": sinter_block.get("sinter_oracle"),
            }
        if isinstance(drag_block, dict):
            claim["atm_drag_bind"] = {
                "drag_spent_j": drag_honesty.get("drag_spent_j"),
                "f_drag_n": drag_block.get("f_drag_n"),
                "body": drag_block.get("body"),
                "drag_oracle": drag_block.get("drag_oracle"),
            }
        if isinstance(acoustic_block, dict):
            claim["acoustic_bind"] = {
                "acoustic_spent_j": acoustic_honesty.get("acoustic_spent_j"),
                "vp_m_s": acoustic_block.get("vp_m_s"),
                "transmittance": acoustic_block.get("transmittance"),
                "sense_ok": acoustic_block.get("sense_ok"),
                "medium_id": acoustic_block.get("medium_id"),
                "acoustic_oracle": acoustic_block.get("acoustic_oracle"),
            }
        if isinstance(li_block, dict):
            claim["li_qc_bind"] = {
                "li_spent_j": li_honesty.get("li_spent_j"),
                "q_c_kpa": li_block.get("q_c_kpa"),
                "depth_mm": li_block.get("depth_mm"),
                "bearing_ok": li_block.get("bearing_ok"),
                "li_oracle": li_block.get("li_oracle"),
            }
        if isinstance(albedo_block, dict):
            claim["albedo_dose_bind"] = {
                "albedo_spent_j": albedo_honesty.get("albedo_spent_j"),
                "albedo_dose_gy": albedo_block.get("albedo_dose_gy"),
                "see_rate_per_year": albedo_block.get("see_rate_per_year"),
                "dose_ok": albedo_block.get("dose_ok"),
                "site_class": albedo_block.get("site_class"),
                "albedo_oracle": albedo_block.get("albedo_oracle"),
            }
        if isinstance(ingress_block, dict):
            claim["dust_ingress_bind"] = {
                "ingress_spent_j": ingress_honesty.get("ingress_spent_j"),
                "effective_rate_g_m2_per_sol": ingress_block.get("effective_rate_g_m2_per_sol"),
                "accumulation_g_m2": ingress_block.get("accumulation_g_m2"),
                "ingress_hazard_class": ingress_block.get("ingress_hazard_class"),
                "ingress_ok": ingress_block.get("ingress_ok"),
                "zone": ingress_block.get("zone"),
                "ingress_oracle": ingress_block.get("ingress_oracle"),
            }
        if isinstance(janosi_block, dict):
            claim["janosi_bind"] = {
                "janosi_spent_j": janosi_honesty.get("janosi_spent_j"),
                "tau_probe_kpa": janosi_block.get("tau_probe_kpa"),
                "tau_inf_kpa": janosi_block.get("tau_inf_kpa"),
                "soil_id": janosi_block.get("soil_id"),
                "shear_ok": janosi_block.get("shear_ok"),
                "janosi_oracle": janosi_block.get("janosi_oracle"),
            }
        if isinstance(rad_block, dict):
            claim["radiation_rate_bind"] = {
                "rad_spent_j": rad_honesty.get("rad_spent_j"),
                "window_dose_gy": rad_block.get("window_dose_gy"),
                "window_see_events": rad_block.get("window_see_events"),
                "site_id": rad_block.get("site_id"),
                "rad_ok": rad_block.get("rad_ok"),
                "radiation_oracle": rad_block.get("radiation_oracle"),
            }
        if isinstance(k_block, dict):
            claim["regolith_thermal_bind"] = {
                "k_spent_j": k_honesty.get("k_spent_j"),
                "k_w_mk": k_block.get("k_w_mk"),
                "material_id": k_block.get("material_id"),
                "t_k": k_block.get("t_k"),
                "cryo": k_block.get("cryo"),
                "thermal_k_ok": k_block.get("thermal_k_ok"),
                "thermal_k_oracle": k_block.get("thermal_k_oracle"),
            }
    return claim


def require_energy_claim_on_run(run_doc: dict[str, Any]) -> dict[str, Any]:
    claim = run_doc.get("energy_claim")
    if not isinstance(claim, dict) or claim.get("schema") != SCHEMA:
        raise EnergyClaimError("missing_energy_claim")
    validate_energy_claim(claim)
    return claim
