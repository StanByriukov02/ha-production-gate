"""Local Dual desk run log — save boards, list, compare two runs.

Dogfood stand: no cloud, no accounts. Persist under results/runtime/desk_runs/.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "ha_desk_run_log_v1"
DEFAULT_KEEP = 40

_REPO = Path(__file__).resolve().parents[1]
_LOG_DIR = _REPO / "results" / "runtime" / "desk_runs"
_INDEX = _LOG_DIR / "INDEX_v1.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> Path:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def _load_index() -> dict[str, Any]:
    _ensure_dir()
    if not _INDEX.is_file():
        return {"schema": SCHEMA, "runs": [], "keep": DEFAULT_KEEP}
    doc = json.loads(_INDEX.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("desk run index corrupt")
    runs = doc.get("runs")
    if not isinstance(runs, list):
        runs = []
    return {
        "schema": SCHEMA,
        "runs": runs,
        "keep": int(doc.get("keep") or DEFAULT_KEEP),
    }


def _save_index(doc: dict[str, Any]) -> None:
    _ensure_dir()
    keep = int(doc.get("keep") or DEFAULT_KEEP)
    runs = list(doc.get("runs") or [])
    if len(runs) > keep:
        drop = runs[keep:]
        runs = runs[:keep]
        for row in drop:
            rid = str((row or {}).get("id") or "")
            if rid:
                p = _LOG_DIR / f"{rid}.json"
                if p.is_file():
                    p.unlink()
        doc = {**doc, "runs": runs, "keep": keep}
    _INDEX.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def slice_board(doc: dict[str, Any]) -> dict[str, Any]:
    """Compact board slice for лента + compare (not full Dual receipt)."""
    contact = doc.get("contact") if isinstance(doc.get("contact"), dict) else {}
    soils = doc.get("soils") if isinstance(doc.get("soils"), dict) else {}
    safe = doc.get("safe") if isinstance(doc.get("safe"), dict) else {}
    hostile = doc.get("hostile") if isinstance(doc.get("hostile"), dict) else {}
    body = doc.get("body") if isinstance(doc.get("body"), dict) else {}
    return {
        "verdict": doc.get("verdict"),
        "body": {
            "mode": body.get("mode"),
            "preset": body.get("preset"),
            "urdf": body.get("urdf"),
            "model_kind": body.get("model_kind"),
            "world_id": body.get("world_id"),
        },
        "contact": {
            "mass_kg": contact.get("mass_kg"),
            "n_contacts": contact.get("n_contacts"),
            "contact_width_m": contact.get("contact_width_m"),
            "contact_length_m": contact.get("contact_length_m"),
            "source": contact.get("source"),
        },
        "soils": {
            "safe_id": soils.get("safe_id") or safe.get("soil_id"),
            "hostile_id": soils.get("hostile_id") or hostile.get("soil_id"),
            "owned": bool(soils.get("owned_path")),
        },
        "safe_mm": safe.get("sinkage_mm"),
        "hostile_mm": hostile.get("sinkage_mm"),
        "safe_allowed": safe.get("current_allowed"),
        "hostile_allowed": hostile.get("current_allowed"),
    }


def save_run(doc: dict[str, Any], *, label: str | None = None) -> dict[str, Any]:
    """Append one Dual board slice to the local лента. Returns the saved row."""
    rid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    slice_ = slice_board(doc)
    row = {
        "id": rid,
        "timestamp_utc": _now(),
        "label": (label or "").strip() or None,
        "schema": SCHEMA,
        **slice_,
    }
    path = _ensure_dir() / f"{rid}.json"
    path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    index = _load_index()
    index["runs"] = [row, *list(index.get("runs") or [])]
    _save_index(index)
    return row


def list_runs(*, limit: int | None = None) -> list[dict[str, Any]]:
    index = _load_index()
    runs = list(index.get("runs") or [])
    if limit is not None:
        runs = runs[: max(0, int(limit))]
    return runs


def get_run(run_id: str) -> dict[str, Any] | None:
    rid = str(run_id or "").strip()
    if not rid:
        return None
    path = _LOG_DIR / f"{rid}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    for row in list_runs():
        if str(row.get("id")) == rid:
            return row
    return None


def compare_runs(run_a: str, run_b: str) -> dict[str, Any]:
    a = get_run(run_a)
    b = get_run(run_b)
    if a is None:
        raise FileNotFoundError(f"run not found: {run_a}")
    if b is None:
        raise FileNotFoundError(f"run not found: {run_b}")

    def _side(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": r.get("id"),
            "timestamp_utc": r.get("timestamp_utc"),
            "label": r.get("label"),
            "verdict": r.get("verdict"),
            "body": r.get("body"),
            "contact": r.get("contact"),
            "soils": r.get("soils"),
            "safe_mm": r.get("safe_mm"),
            "hostile_mm": r.get("hostile_mm"),
        }

    sa, sb = _side(a), _side(b)
    diffs: list[str] = []
    for key in ("verdict", "safe_mm", "hostile_mm"):
        if sa.get(key) != sb.get(key):
            diffs.append(key)
    for block in ("body", "contact", "soils"):
        if sa.get(block) != sb.get(block):
            diffs.append(block)
    return {
        "schema": SCHEMA,
        "ok": True,
        "a": sa,
        "b": sb,
        "diff_keys": diffs,
    }
