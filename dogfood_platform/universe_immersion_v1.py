"""Immersion targets — chip · robot · panel · rocket (U2/P6)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

_REPO = Path(__file__).resolve().parents[1]
_BIND = _REPO / "results" / "platform_bpass" / "universe" / "IMMERSION_TARGET_BIND_v1.json"

TargetId = Literal["chip", "robot", "panel", "rocket"]


def list_target_ids(*, bind: dict[str, Any] | None = None) -> list[str]:
    data = bind or load_immersion_bind()
    return list((data.get("targets") or {}).keys())


def load_immersion_bind(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _BIND).read_text(encoding="utf-8"))


def load_target(target_id: str, *, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    data = bind or load_immersion_bind()
    row = (data.get("targets") or {}).get(target_id)
    if not row:
        raise KeyError(f"unknown immersion target: {target_id}")
    return row


def event_applies_to_target(event: dict[str, Any], target: dict[str, Any]) -> bool:
    ev_targets = set(event.get("coupling_targets") or [])
    tg_targets = set(target.get("coupling_targets") or [])
    return bool(ev_targets & tg_targets)


def susceptibility_weight(target: dict[str, Any], law_id: str) -> float:
    sus = target.get("susceptibility") or {}
    return float(sus.get(law_id) or 0.5)


def check_budget(target_id: str, metrics: dict[str, float], *, bind: dict[str, Any] | None = None) -> dict[str, Any]:
    target = load_target(target_id, bind=bind)
    budget = target.get("epsilon_budget") or {}
    checks: list[dict[str, Any]] = []
    all_ok = True
    for key, limit in budget.items():
        if key == "cite" or not isinstance(limit, (int, float)):
            continue
        val = metrics.get(key)
        if val is None:
            continue
        if key.endswith("_min"):
            ok = float(val) >= float(limit)
        else:
            ok = float(val) <= float(limit)
        checks.append({"metric": key, "value": val, "limit": limit, "pass": ok})
        if not ok:
            all_ok = False
    return {"target_id": target_id, "budget_checks": checks, "within_budget": all_ok}
