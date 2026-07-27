"""E1 drive-chain embed — motor+gear η + joint μ into Dual physics / energy.

Packs / loads from catalog dual_anchors.
parasitic_mult = 1 + gear_loss_frac + |F_f|/N   (dimensionless; N = catalog dual n_n)
Spent:
  scaled_extra = (mult - 1) * base_spent     ← efficiency loss of soil work (justified)
  joint_share  = dual_share(|F_f|)           ← no orphan 1e-4 / 0.2 cap
  add = scaled_extra + joint_share
"""
from __future__ import annotations

from typing import Any, Literal

ConditionId = Literal["safe", "hostile"]
EMBED_SLICE_J = 1.0


def _drive_pack() -> dict[str, Any]:
    from production_gate.dc_motor_gear_on_v1 import load_dc_motor_catalog
    from production_gate.joint_friction_on_v1 import load_joint_catalog

    m = load_dc_motor_catalog()
    j = load_joint_catalog()
    ma, ja = m["dual_anchors"], j["dual_anchors"]
    return {
        "motor_safe": str(ma["safe_pack"]),
        "motor_hostile": str(ma["hostile_pack"]),
        "omega": float(ma.get("omega_rad_s") or m.get("defaults", {}).get("omega_rad_s") or 150.0),
        "joint_safe": str(ja["safe_pack"]),
        "joint_hostile": str(ja["hostile_pack"]),
        "n_n": float(ja.get("n_n") or j.get("defaults", {}).get("n_n") or 500.0),
    }


def packs_for_condition(condition: ConditionId) -> tuple[str, str]:
    p = _drive_pack()
    if condition == "hostile":
        return p["motor_hostile"], p["joint_hostile"]
    return p["motor_safe"], p["joint_safe"]


def evaluate_drive_chain(
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    """Evaluate motor+joint from Rust; Dual-share joint spent slice."""
    from production_gate.dc_motor_gear_on_v1 import evaluate_dc_motor_gear
    from production_gate.dual_spent_normalize_v1 import dual_share_receipt
    from production_gate.joint_friction_on_v1 import evaluate_joint_friction

    pack = _drive_pack()
    motor_id, joint_id = packs_for_condition(condition)
    motor = evaluate_dc_motor_gear(pack_id=motor_id, omega_rad_s=pack["omega"])
    joint = evaluate_joint_friction(pack_id=joint_id, n_n=pack["n_n"])
    eta = float(motor["eta"])
    mu = float(joint["mu"])
    f_f = float(joint["f_friction_n"])
    tau_out = float(motor["tau_out_nm"])
    gear_loss_frac = max(0.0, 1.0 - eta)
    n_n = float(pack["n_n"])
    parasitic_mult = 1.0 + gear_loss_frac + abs(f_f) / max(n_n, 1e-9)

    # Peer F_f for Dual-share denom.
    peer_id = pack["joint_safe"] if condition == "hostile" else pack["joint_hostile"]
    peer = evaluate_joint_friction(pack_id=peer_id, n_n=n_n)
    peer_f = float(peer["f_friction_n"])
    m_s, m_h = (abs(f_f), abs(peer_f)) if condition == "safe" else (abs(peer_f), abs(f_f))
    joint_share = dual_share_receipt(
        metric=abs(f_f),
        metric_safe=m_s,
        metric_hostile=m_h,
        budget_j=budget_j,
        metric_id="|F_friction_n|",
    )

    return {
        "schema": "ha_drive_chain_embed_v1",
        "condition": condition,
        "motor_pack": motor_id,
        "joint_pack": joint_id,
        "eta": eta,
        "mu": mu,
        "f_friction_n": f_f,
        "tau_out_nm": tau_out,
        "omega_rad_s": pack["omega"],
        "n_n": n_n,
        "gear_loss_frac": gear_loss_frac,
        "parasitic_mult": parasitic_mult,
        "joint_spent_j": joint_share["spent_j"],
        "joint_dual_share": joint_share,
        "motor_oracle": motor.get("oracle"),
        "joint_oracle": joint.get("oracle"),
        "honesty": {
            "drive_chain_from_rust": True,
            "motor_from_rust": True,
            "joint_friction_from_rust": True,
            "spent_dual_share_only": True,
            "no_orphan_scale": True,
            "packs_from_catalog_dual_anchors": True,
            "not_measured": True,
            "not_foc_dyno": True,
        },
    }


def attach_drive_chain_to_physics(
    physics: dict[str, Any],
    *,
    condition: ConditionId,
    budget_j: float = EMBED_SLICE_J,
) -> dict[str, Any]:
    """Copy physics and attach drive_chain embed block for energy Dual."""
    out = dict(physics)
    dc = evaluate_drive_chain(condition=condition, budget_j=budget_j)
    out["drive_chain"] = dc
    honesty = dict(out.get("honesty") or {})
    honesty["drive_chain_from_rust"] = True
    honesty["motor_from_rust"] = True
    honesty["joint_friction_from_rust"] = True
    honesty["spent_dual_share_only"] = True
    out["honesty"] = honesty
    return out


def parasitic_spent_add_j(
    drive_chain: dict[str, Any] | None,
    *,
    base_spent_j: float,
    distance_m: float,
) -> tuple[float, dict[str, Any]]:
    """Scale Bekker spent by drive parasitic mult + Dual-share joint slice."""
    del distance_m  # distance no longer scales orphan F*d*1e-4; joint via dual_share
    if not isinstance(drive_chain, dict):
        return 0.0, {"spent_from_drive_chain_rust": False}
    mult = float(drive_chain.get("parasitic_mult") or 1.0)
    f_f = float(drive_chain.get("f_friction_n") or 0.0)
    joint_add = float(drive_chain.get("joint_spent_j") or 0.0)
    scaled_extra = max(0.0, (mult - 1.0) * max(base_spent_j, 0.0))
    add = scaled_extra + joint_add
    honesty = {
        "spent_from_drive_chain_rust": True,
        "spent_dual_share_only": True,
        "no_orphan_scale": True,
        "motor_from_rust": bool((drive_chain.get("honesty") or {}).get("motor_from_rust")),
        "joint_friction_from_rust": bool(
            (drive_chain.get("honesty") or {}).get("joint_friction_from_rust")
        ),
        "parasitic_mult": mult,
        "gear_loss_frac": drive_chain.get("gear_loss_frac"),
        "eta": drive_chain.get("eta"),
        "mu": drive_chain.get("mu"),
        "f_friction_n": f_f,
        "joint_add_j": joint_add,
        "scaled_extra_j": scaled_extra,
        "motor_pack": drive_chain.get("motor_pack"),
        "joint_pack": drive_chain.get("joint_pack"),
    }
    return round(add, 6), honesty
