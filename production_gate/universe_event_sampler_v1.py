"""Universe event sampler + campaign — U1/U2/U4 (R1,R3,R4,R5)."""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

from production_gate.universe_event_dispatch_v1 import apply_event
from production_gate.universe_state_v1 import load_law_registry, law_by_id

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "results" / "platform_bpass" / "universe" / "EVENT_CATALOG_BIND_v1.json"
_ENV = _REPO / "results" / "platform_bpass" / "universe" / "ENV_DRIVER_BIND_v1.json"
_OUT = _REPO / "results" / "platform_bpass" / "universe"


def load_event_catalog(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _CATALOG).read_text(encoding="utf-8"))


def load_env_driver_bind(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _ENV).read_text(encoding="utf-8"))


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def _draw_param(rng: random.Random, spec: dict[str, Any]) -> Any:
    if "min" in spec and "max" in spec:
        return _lerp(float(spec["min"]), float(spec["max"]), rng.random())
    if isinstance(spec, list):
        return rng.choice(spec)
    return spec


def draw_event_params(event: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    env = event.get("parameter_envelope") or {}
    params: dict[str, Any] = {}
    for key, spec in env.items():
        if isinstance(spec, dict) and "min" in spec:
            params[key] = _draw_param(rng, spec)
        elif isinstance(spec, list):
            params[key] = rng.choice(spec)
        else:
            params[key] = spec
    typ = event.get("typical_numbers") or {}
    for k, v in typ.items():
        params.setdefault(k, v)
    return params


def sample_events_stratified(
    *,
    n_runs: int = 100,
    seed: int = 20260616,
    catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    data = catalog or load_event_catalog()
    events = list(data.get("events") or [])
    by_scale: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        by_scale.setdefault(str(ev.get("scale_class")), []).append(ev)
    scales = list(by_scale.keys())
    rng = random.Random(seed)
    draws: list[dict[str, Any]] = []
    for i in range(n_runs):
        scale = scales[i % len(scales)]
        pool = by_scale[scale]
        ev = pool[rng.randrange(len(pool))]
        params = draw_event_params(ev, rng)
        draws.append({"run_id": f"EV-{i:03d}", "event": ev, "params": params})
    return draws


def sample_adversarial(catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = catalog or load_event_catalog()
    adv = [e for e in data.get("events") or [] if e.get("rate_prior") == "adversarial_corner"]
    rows: list[dict[str, Any]] = []
    for ev in adv:
        params = draw_event_params(ev, random.Random(hash(ev["event_id"]) % 2**32))
        rows.append({"run_id": f"ADV-{ev['event_id']}", "event": ev, "params": params})
    return rows


def wilson_lower(k: int, n: int, confidence: float = 0.998) -> float:
    if n <= 0:
        return 0.0
    p = k / n
    z = 3.0902323061680958 if confidence >= 0.998 else 1.959963984540054
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
    return max(0.0, (centre - margin) / denom)


def validate_law_registered(event: dict[str, Any], registry: dict[str, Any] | None = None) -> bool:
    reg = registry or load_law_registry()
    try:
        law_by_id(reg, str(event.get("law_id")))
        return True
    except KeyError:
        return False


def run_event_campaign(
    *,
    n_runs: int = 100,
    seed: int = 20260616,
    include_adversarial: bool = True,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = catalog or load_event_catalog()
    registry = load_law_registry()
    mc = sample_events_stratified(n_runs=n_runs, seed=seed, catalog=data)
    adv = sample_adversarial(catalog=data) if include_adversarial else []
    results: list[dict[str, Any]] = []
    scale_hits: dict[str, int] = {s: 0 for s in data.get("scale_classes") or []}
    law_hits: dict[str, int] = {}
    for row in mc + adv:
        ev = row["event"]
        if not validate_law_registered(ev, registry):
            results.append({**row, "verdict": "FAIL", "reason": "unknown_law"})
            continue
        applied = apply_event(ev, row["params"])
        results.append({**row, **applied})
        if applied["verdict"] == "PASS":
            sc = str(ev.get("scale_class"))
            scale_hits[sc] = scale_hits.get(sc, 0) + 1
            lid = str(ev.get("law_id"))
            law_hits[lid] = law_hits.get(lid, 0) + 1
    k_pass = sum(1 for r in results if r.get("verdict") == "PASS")
    n_total = len(results)
    scales_covered = sum(1 for s in data.get("scale_classes") or [] if scale_hits.get(s, 0) > 0)
    verdict = "PASS"
    if k_pass < n_total:
        verdict = "FAIL"
    if scales_covered < len(data.get("scale_classes") or []):
        verdict = "FAIL"
    return {
        "campaign_id": "UNIVERSE_EVENT_CAMPAIGN_v1",
        "catalog_id": data.get("catalog_id"),
        "seed": seed,
        "n_event_runs": n_runs,
        "n_adversarial": len(adv),
        "n_total_applied": n_total,
        "pass_count": k_pass,
        "pass_rate": round(k_pass / max(n_total, 1), 6),
        "wilson_lower_99_8pct": round(wilson_lower(k_pass, n_total), 6),
        "binomial_zero_failures": k_pass == n_total,
        "scale_class_hits": scale_hits,
        "scales_covered": scales_covered,
        "law_hits": law_hits,
        "catalog_event_count": len(data.get("events") or []),
        "verdict": verdict,
        "oracle": "EVENT_TAXONOMY_STRATIFIED",
        "failed_ids": [r.get("run_id") for r in results if r.get("verdict") != "PASS"],
    }


def write_campaign(*, n_runs: int = 100, seed: int = 20260616) -> dict[str, Any]:
    campaign = run_event_campaign(n_runs=n_runs, seed=seed)
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / "UNIVERSE_EVENT_CAMPAIGN_RECEIPT_v1.json"
    path.write_text(json.dumps(campaign, indent=2) + "\n", encoding="utf-8")
    summary = {
        "campaign_id": campaign["campaign_id"],
        "verdict": campaign["verdict"],
        "pass_rate": campaign["pass_rate"],
        "wilson_lower": campaign["wilson_lower_99_8pct"],
        "scales_covered": campaign["scales_covered"],
        "catalog_events": campaign["catalog_event_count"],
        "receipt": str(path.relative_to(_REPO)).replace("\\", "/"),
    }
    (_OUT / "UNIVERSE_EVENT_CAMPAIGN_SUMMARY_v1.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def catalog_selftest() -> dict[str, Any]:
    data = load_event_catalog()
    registry = load_law_registry()
    events = data.get("events") or []
    missing_law: list[str] = []
    by_scale: dict[str, int] = {}
    for ev in events:
        if not validate_law_registered(ev, registry):
            missing_law.append(str(ev.get("event_id")))
        sc = str(ev.get("scale_class"))
        by_scale[sc] = by_scale.get(sc, 0) + 1
    ok = not missing_law and len(events) >= 32 and all(by_scale.get(s, 0) >= 8 for s in data.get("scale_classes") or [])
    return {
        "catalog_id": data.get("catalog_id"),
        "event_count": len(events),
        "by_scale": by_scale,
        "missing_law": missing_law,
        "verdict": "PASS" if ok else "FAIL",
    }


def selftest(*, fast: bool = False) -> None:
    cat = catalog_selftest()
    if cat["verdict"] != "PASS":
        raise AssertionError(cat)
    n = 32 if fast else 100
    summary = write_campaign(n_runs=n, seed=20260616)
    if summary["verdict"] != "PASS":
        raise AssertionError(summary)
