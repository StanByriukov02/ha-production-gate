"""Anti-slop Dual spent — map a physical metric into claim joules without free scales.

Rule: spent_j is fully determined by (metric, metric_safe, metric_hostile, budget_j).
No orphan multipliers like 0.35 / 0.01 / 1e-6.

  spent = budget_j * |metric| / (|metric_safe| + |metric_hostile|)

Safe share < Hostile share whenever |m_h| > |m_s|. Identity: spent_s + spent_h = budget_j
when both sides use the same Dual pair (up to abs).
"""
from __future__ import annotations

from typing import Any


def dual_share_spent_j(
    *,
    metric: float,
    metric_safe: float,
    metric_hostile: float,
    budget_j: float,
) -> float:
    """Return spent_j in [0, budget_j] from Dual-pair share. Raises if budget invalid."""
    b = float(budget_j)
    if not (b == b) or b < 0.0:
        raise ValueError(f"budget_j not usable: {budget_j!r}")
    denom = abs(float(metric_safe)) + abs(float(metric_hostile))
    if denom <= 0.0:
        return 0.0
    frac = abs(float(metric)) / denom
    if frac > 1.0:
        frac = 1.0
    return round(b * frac, 6)


def dual_share_receipt(
    *,
    metric: float,
    metric_safe: float,
    metric_hostile: float,
    budget_j: float,
    metric_id: str,
) -> dict[str, Any]:
    spent = dual_share_spent_j(
        metric=metric,
        metric_safe=metric_safe,
        metric_hostile=metric_hostile,
        budget_j=budget_j,
    )
    return {
        "metric_id": metric_id,
        "metric": float(metric),
        "metric_safe": float(metric_safe),
        "metric_hostile": float(metric_hostile),
        "budget_j": float(budget_j),
        "spent_j": spent,
        "formula": "spent = budget * |m| / (|m_safe|+|m_hostile|)",
        "honesty": {
            "no_orphan_scale": True,
            "dual_share_only": True,
            "not_measured": True,
        },
    }
