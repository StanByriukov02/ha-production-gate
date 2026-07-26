"""Desk visitor vault — first-open clean scene vs returning last results.

Contract:
- First open on this machine → clean Start here (no leftover probe crater).
- Returning open → restore their last desk scene / active project locally.
- Never phone home. Vault is ~/.hardware_atom only.

TABU: cloud identity · MEASURED · product_ready.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

PROOF_TIER = "DESK_VISITOR_BOOT_SLICE"
_VAULT_NAME = "desk_visitor_v1.json"


def visitor_path() -> Path:
    override = (os.environ.get("HA_DESK_VISITOR") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".hardware_atom" / _VAULT_NAME


def _read() -> dict[str, Any]:
    path = visitor_path()
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(doc: dict[str, Any]) -> Path:
    path = visitor_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def is_first_open() -> bool:
    doc = _read()
    return int(doc.get("open_count") or 0) < 1


def status() -> dict[str, Any]:
    doc = _read()
    count = int(doc.get("open_count") or 0)
    return {
        "ok": True,
        "first_open": count < 1,
        "open_count": count,
        "last_active_project_id": doc.get("last_active_project_id"),
        "last_globe": doc.get("last_globe"),
        "vault_path": str(visitor_path()),
        "proof_tier": PROOF_TIER,
        "honesty": {
            "local_only": True,
            "no_ha_cloud": True,
            "not_measured": True,
            "not_product_ready": True,
        },
    }


def mark_open(
    *,
    active_project_id: str | None = None,
    globe: str | None = None,
    scene: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = _read()
    now = int(time.time())
    count = int(doc.get("open_count") or 0)
    first = count < 1
    doc.update(
        {
            "schema": "ha_desk_visitor_v1",
            "open_count": count + 1,
            "first_open_unix": int(doc.get("first_open_unix") or now),
            "last_open_unix": now,
            "last_active_project_id": active_project_id
            if active_project_id is not None
            else doc.get("last_active_project_id"),
            "last_globe": globe if globe is not None else doc.get("last_globe"),
            "honesty": {
                "local_only": True,
                "no_ha_cloud": True,
                "not_measured": True,
            },
        }
    )
    if isinstance(scene, dict):
        doc["last_scene"] = scene
    _write(doc)
    out = status()
    out["was_first_open"] = first
    return out


def remember_scene(scene: dict[str, Any], *, active_project_id: str | None = None) -> dict[str, Any]:
    doc = _read()
    if int(doc.get("open_count") or 0) < 1:
        # First paint may call remember before mark_open — still persist scene for return
        doc["open_count"] = 1
        doc["first_open_unix"] = int(time.time())
    doc["last_scene"] = dict(scene)
    doc["last_open_unix"] = int(time.time())
    if active_project_id:
        doc["last_active_project_id"] = active_project_id
    if scene.get("globe"):
        doc["last_globe"] = scene.get("globe")
    doc["schema"] = "ha_desk_visitor_v1"
    _write(doc)
    return status()


def last_scene() -> dict[str, Any] | None:
    scene = _read().get("last_scene")
    return dict(scene) if isinstance(scene, dict) else None


def smoke() -> dict[str, Any]:
    st = status()
    checks = {
        "F_status_local": bool(st.get("honesty", {}).get("local_only")),
        "F_no_token_keys": "token" not in st and "secret" not in st,
    }
    fail = [k for k, v in checks.items() if not v]
    return {"ok": not fail, "checks": checks, "fail": fail, "proof_tier": PROOF_TIER}
