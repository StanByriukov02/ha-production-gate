"""Robot project desk v1 — durable project object for Start here P0.

Lifecycle: create → attach body (preset) → attach policy (JSONL) → activate → run (other module).

TABU: claim product_ready · claim full builder UI · claim MEASURED field.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_TWIN = _REPO / "results" / "runtime" / "desk"
_PROJECTS = _REPO / "results" / "runtime" / "robot_projects"
_PROJECTS_ROOT = _PROJECTS
_ACTIVE = _PROJECTS / "_active.json"
_ACTIVE_RUNTIME = _ACTIVE
_TWIN_ACTIVE = _TWIN / "robot_project_active_v1.json"
_ACTIVE_TWIN = _TWIN_ACTIVE

PROOF_TIER = "ROBOT_PROJECT_DESK_SLICE"

# Default stranger body — open-registry manipulator (not lunar assembly theater)
DEFAULT_OPEN_PRESET = "open_rrbot"

PRESETS: dict[str, dict[str, Any]] = {
    "open_rrbot": {
        "label": "Open rrbot (2-DoF)",
        "blurb": "Open-registry arm — Dual Bekker + pack law default.",
        "kind": "open_registry",
        "registry_id": "ros_rrbot",
        "world_id": "earth_lab_open",
    },
    "open_diffbot": {
        "label": "Open diffbot",
        "blurb": "Open-registry differential base — Dual soil probe.",
        "kind": "open_registry",
        "registry_id": "ros_diffbot",
        "world_id": "earth_lab_open",
    },
    "lunar_scout": {
        "label": "Lunar scout",
        "blurb": "Hexapod assembly recipe — teaching crater world (optional).",
        "kind": "assembly_recipe",
        "recipe_id": "lunar_scout_field",
        "world_id": "W_lunar_crater_robot_os_v1",
    },
    "earth_bench": {
        "label": "Earth bench",
        "blurb": "Create CLI + wheeled chassis + bench ingress.",
        "kind": "assembly_recipe",
        "recipe_id": "earth_bench_carrier",
        "world_id": "earth_lab_1g",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return s[:48] or "robot"


def project_dir(project_id: str) -> Path:
    return _PROJECTS / project_id


def project_json_path(project_id: str) -> Path:
    return project_dir(project_id) / "project.json"


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    from dogfood_platform.atomic_json_v1 import atomic_write_json

    atomic_write_json(path, doc)


def _read_json(path: Path) -> dict[str, Any]:
    from dogfood_platform.atomic_json_v1 import atomic_read_json

    return atomic_read_json(path)


def list_projects(*, limit: int | None = 48) -> list[dict[str, Any]]:
    if not _PROJECTS.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(_PROJECTS.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        jp = p / "project.json"
        if jp.is_file():
            try:
                rows.append(project_summary(_read_json(jp)))
            except (OSError, json.JSONDecodeError):
                continue
    rows.sort(key=lambda r: r.get("updated_utc") or "", reverse=True)
    if limit is not None and limit > 0:
        return rows[: int(limit)]
    return rows


def prune_projects(
    *,
    keep: int = 40,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete stale project dirs; keep newest + active.

    Prefer keeping projects with body/last_run. Spam from dogfood create loops dies.
    """
    import shutil

    if not _PROJECTS.is_dir():
        return {"ok": True, "kept": 0, "deleted": 0, "dry_run": dry_run}

    active_id = None
    try:
        active = get_active_project()
        active_id = str((active or {}).get("project_id") or "") or None
    except Exception:
        active_id = None

    rows: list[dict[str, Any]] = []
    for p in _PROJECTS.iterdir():
        if not p.is_dir() or p.name.startswith("_"):
            continue
        jp = p / "project.json"
        if not jp.is_file():
            rows.append(
                {
                    "project_id": p.name,
                    "updated_utc": "",
                    "has_body": False,
                    "last_run_id": None,
                    "_path": p,
                    "_broken": True,
                }
            )
            continue
        try:
            doc = _read_json(jp)
        except (OSError, json.JSONDecodeError):
            rows.append(
                {
                    "project_id": p.name,
                    "updated_utc": "",
                    "has_body": False,
                    "last_run_id": None,
                    "_path": p,
                    "_broken": True,
                }
            )
            continue
        summ = project_summary(doc)
        summ["_path"] = p
        summ["_broken"] = False
        rows.append(summ)

    def _score(r: dict[str, Any]) -> tuple:
        return (
            1 if r.get("project_id") == active_id else 0,
            1 if r.get("has_body") else 0,
            1 if r.get("last_run_id") else 0,
            0 if r.get("_broken") else 1,
            str(r.get("updated_utc") or ""),
        )

    rows.sort(key=_score, reverse=True)
    keep_n = max(1, int(keep))
    keep_set = {str(r["project_id"]) for r in rows[:keep_n]}
    if active_id:
        keep_set.add(active_id)

    deleted: list[str] = []
    for r in rows:
        pid = str(r["project_id"])
        if pid in keep_set:
            continue
        path = r.get("_path")
        if not isinstance(path, Path):
            continue
        deleted.append(pid)
        if not dry_run:
            shutil.rmtree(path, ignore_errors=True)

    return {
        "ok": True,
        "kept": len(keep_set),
        "deleted": len(deleted),
        "deleted_ids_sample": deleted[:12],
        "active_id": active_id,
        "dry_run": dry_run,
        "total_before": len(rows),
    }


def create_project(*, name: str | None = None, preset_id: str | None = None) -> dict[str, Any]:
    _PROJECTS.mkdir(parents=True, exist_ok=True)
    # Soft auto-prune when desk is drowning (dogfood spam)
    try:
        n = sum(1 for p in _PROJECTS.iterdir() if p.is_dir() and not p.name.startswith("_"))
        if n > 120:
            prune_projects(keep=40, dry_run=False)
    except OSError:
        pass
    label = name or (PRESETS.get(preset_id or "", {}) or {}).get("label") or "Untitled robot"
    project_id = f"{_slug(label)}-{uuid.uuid4().hex[:8]}"
    ts = _now()
    doc: dict[str, Any] = {
        "project_id": project_id,
        "name": label,
        "created_utc": ts,
        "updated_utc": ts,
        "body": None,
        "policy": None,
        "policy_port": None,
        "last_run_id": None,
        "last_run": None,
        "proof_tier": PROOF_TIER,
        "honesty": {
            "not_product_ready": True,
            "not_full_builder": True,
            "not_measured": True,
            "sim_slice": True,
        },
        "hil": None,
        "fleet": None,
        "tabu": ["product_ready claims", "MEASURED field claims"],
    }
    root = project_dir(project_id)
    (root / "body").mkdir(parents=True, exist_ok=True)
    (root / "policy").mkdir(parents=True, exist_ok=True)
    (root / "runs").mkdir(parents=True, exist_ok=True)
    (root / "hil").mkdir(parents=True, exist_ok=True)
    (root / "fleet").mkdir(parents=True, exist_ok=True)
    _write_json(project_json_path(project_id), doc)
    if preset_id:
        doc = attach_body_from_preset(project_id, preset_id)
        return doc
    return enrich_project(doc)

def get_project(project_id: str) -> dict[str, Any]:
    path = project_json_path(project_id)
    if not path.is_file():
        raise FileNotFoundError(f"unknown project_id={project_id}")
    return enrich_project(_read_json(path))


def _save_project(doc: dict[str, Any]) -> dict[str, Any]:
    doc = dict(doc)
    doc["updated_utc"] = _now()
    doc["trust_tier"] = compute_trust_tier(doc)
    _write_json(project_json_path(doc["project_id"]), doc)
    return enrich_project(doc)

def set_active_project(project_id: str) -> dict[str, Any]:
    doc = get_project(project_id)
    active = {
        "active_id": "robot_project_active_v1",
        "project_id": project_id,
        "name": doc.get("name"),
        "updated_utc": _now(),
        "has_body": doc.get("body") is not None,
        "has_policy": doc.get("policy") is not None,
        "last_run_id": doc.get("last_run_id"),
        "project": doc,
    }
    _write_json(_ACTIVE, active)
    _TWIN.mkdir(parents=True, exist_ok=True)
    _write_json(_TWIN_ACTIVE, active)
    return active


def clear_active_project() -> dict[str, Any]:
    """Stranger first-open: no auto-selected leftover project."""
    active = {
        "active_id": "robot_project_active_v1",
        "project_id": None,
        "name": None,
        "updated_utc": _now(),
        "has_body": False,
        "has_policy": False,
        "last_run_id": None,
        "cleared": True,
        "honesty": {"first_open_clean": True, "not_measured": True},
    }
    _ACTIVE.parent.mkdir(parents=True, exist_ok=True)
    _write_json(_ACTIVE, active)
    _TWIN.mkdir(parents=True, exist_ok=True)
    _write_json(_TWIN_ACTIVE, active)
    return active


def get_active_project() -> dict[str, Any] | None:
    path = _ACTIVE if _ACTIVE.is_file() else _TWIN_ACTIVE
    if not path.is_file():
        return None
    active = _read_json(path)
    pid = active.get("project_id")
    if not pid:
        return None
    try:
        project = get_project(str(pid))
    except FileNotFoundError:
        return None
    active["project"] = project
    return active


def attach_body_from_open_registry(
    project_id: str,
    registry_id: str = "ros_rrbot",
    *,
    preset_id: str | None = None,
) -> dict[str, Any]:
    """Attach an open-registry URDF body (trust-spine default — not lunar soup)."""
    reg_path = _REPO / "fixtures" / "open_registry" / "REGISTRY_v1.json"
    if not reg_path.is_file():
        raise FileNotFoundError(reg_path)
    reg = _read_json(reg_path)
    entry = None
    for row in reg.get("entries") or []:
        if str(row.get("id")) == registry_id:
            entry = row
            break
    if entry is None:
        known = [str(r.get("id")) for r in (reg.get("entries") or [])]
        raise ValueError(f"unknown open_registry id={registry_id!r}; known={known}")
    if not entry.get("open_body") or not entry.get("urdf"):
        raise ValueError(f"open_registry entry {registry_id!r} has no open URDF body")
    urdf_rel = str(entry["urdf"])
    urdf_path = _REPO / "fixtures" / "open_registry" / urdf_rel
    if not urdf_path.is_file():
        raise FileNotFoundError(urdf_path)
    label = str(entry.get("product") or registry_id)
    doc = attach_body_from_urdf(
        project_id,
        str(urdf_path.relative_to(_REPO)).replace("\\", "/"),
        root_link=str(entry.get("root_link") or "base_link"),
        ee_link=str(entry["ee_link"]) if entry.get("ee_link") else None,
        world_id="earth_lab_open",
        label=f"Open registry · {label}",
        chain_id=f"open_registry_{registry_id}_v1",
    )
    body = dict(doc.get("body") or {})
    body["preset_id"] = preset_id or (
        "open_rrbot" if registry_id == "ros_rrbot" else f"open_{registry_id}"
    )
    body["open_registry_id"] = registry_id
    body["checks_pass"] = True
    doc["body"] = body
    return _save_project(doc)


def attach_body_from_preset(project_id: str, preset_id: str) -> dict[str, Any]:
    if preset_id not in PRESETS:
        raise ValueError(f"unknown preset_id={preset_id!r}; choose from {sorted(PRESETS)}")
    meta = PRESETS[preset_id]
    if meta.get("kind") == "open_registry":
        return attach_body_from_open_registry(
            project_id,
            str(meta["registry_id"]),
            preset_id=preset_id,
        )

    from dogfood_platform.dogfood_robot_hardware_assembly_lab_v1 import run_assembly_recipe

    recipe = run_assembly_recipe(str(meta["recipe_id"]))
    summary = {
        "preset_id": preset_id,
        "label": meta["label"],
        "blurb": meta["blurb"],
        "world_id": meta["world_id"],
        "recipe_id": meta["recipe_id"],
        "verdict": recipe.get("verdict"),
        "fail": recipe.get("fail") or [],
        "checks_pass": not (recipe.get("fail") or []),
        "create": recipe.get("create"),
        "manifest_path": recipe.get("manifest_path"),
    }
    body_path = project_dir(project_id) / "body" / "manifest.json"
    _write_json(
        body_path,
        {
            "kind": "assembly_recipe",
            "preset_id": preset_id,
            "summary": summary,
            "recipe": {k: recipe.get(k) for k in ("recipe_id", "verdict", "world_id", "fail", "checks")},
            "proof_tier": "DOGFOOD_ROBOT_HARDWARE_ASSEMBLY_LAB_SLICE",
            "timestamp_utc": _now(),
        },
    )
    from dogfood_platform.body_identity_v1 import write_body_identity_artifact

    identity = write_body_identity_artifact(
        project_id,
        body_path,
        kind="assembly_recipe",
        source_name=preset_id,
        chain_id=f"preset:{preset_id}",
    )
    from dogfood_platform.silicon_fuse_v1 import bind_body_to_silicon_fuse

    bind_body_to_silicon_fuse(project_id, str(identity.get("body_sha256") or ""))
    doc = get_project(project_id)
    doc["body"] = {
        "kind": "assembly_recipe",
        "preset_id": preset_id,
        "recipe_id": meta["recipe_id"],
        "label": meta["label"],
        "world_id": meta["world_id"],
        "verdict": summary["verdict"],
        "checks_pass": summary["checks_pass"],
        "manifest_path": "body/manifest.json",
        "stored_file": "body/manifest.json",
        "summary": summary,
        "identity": identity,
    }
    return _save_project(doc)


def bootstrap_open_desk_project(*, name: str | None = None) -> dict[str, Any]:
    """New → open rrbot body → PolicyPort stub — Ready for Dual Run probe."""
    project = create_project(name=name or "Open rrbot desk", preset_id=None)
    pid = str(project["project_id"])
    project = attach_body_from_open_registry(pid, "ros_rrbot", preset_id=DEFAULT_OPEN_PRESET)
    try:
        from examples.policy_port_dropin_adapter_v1.adapter import emit_proposals, proposals_to_jsonl

        port_text = proposals_to_jsonl(emit_proposals(ticks=3, hostile_from=1))
        port_name = "dropin_adapter.jsonl"
    except Exception:  # noqa: BLE001 — keep bootstrap runnable
        from examples.policy_stub_adapter_v1 import emit

        rows = emit(ticks=3, hostile_from=1)
        port_text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
        port_name = "policy_stub_adapter_v1.jsonl"
    project = attach_policy_port(pid, port_text, filename=port_name)
    set_active_project(pid)
    return get_project(pid)


def _resolve_repo_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = _REPO / p
    return p.resolve()


def _safe_body_filename(name: str) -> str:
    base = Path(str(name or "body.bin")).name
    cleaned = re.sub(r"[^\w.\-]+", "_", base).strip("._") or "body.bin"
    return cleaned[:180]


def _infer_body_kind(filename: str, *, kind: str | None = None) -> str:
    if kind:
        k = str(kind).strip().lower()
        if k in ("urdf", "mjcf", "json_pack", "json", "full_body", "preset", "assembly_recipe"):
            return "json_pack" if k in ("json", "full_body") else k
    lower = str(filename or "").lower()
    if lower.endswith(".urdf"):
        return "urdf"
    if lower.endswith(".mjcf") or lower.endswith(".xml"):
        return "mjcf"
    if lower.endswith(".json"):
        return "json_pack"
    raise ValueError(
        f"cannot infer body kind from filename={filename!r}; pass kind=urdf|mjcf|json_pack"
    )


def attach_body_from_upload(
    project_id: str,
    *,
    filename: str,
    text: str | None = None,
    content_base64: str | None = None,
    kind: str | None = None,
    root_link: str = "base_link",
    ee_link: str | None = None,
    world_id: str = "earth_lab_1g",
    label: str | None = None,
) -> dict[str, Any]:
    """Bring-your-own body: write upload into project body/ then attach.

    Necessity upgrade — engineer attaches THEIR URDF/MJCF/JSON like PolicyPort file.
    TABU: MEASURED · Isaac GT · claim product_ready.
    """
    import base64

    safe = _safe_body_filename(filename)
    inferred = _infer_body_kind(safe, kind=kind)
    if text is None and content_base64 is None:
        raise ValueError("text or content_base64 required for body upload")
    if content_base64 is not None:
        raw = base64.b64decode(str(content_base64))
    else:
        raw = str(text).encode("utf-8")

    body_dir = project_dir(project_id) / "body"
    body_dir.mkdir(parents=True, exist_ok=True)
    dest = body_dir / safe
    dest.write_bytes(raw)

    # Path relative to repo so URDF compiler resolves under _REPO
    try:
        rel = dest.relative_to(_REPO).as_posix()
    except ValueError:
        rel = str(dest)

    display = label or f"BYO {safe}"
    if inferred == "urdf":
        return attach_body_from_urdf(
            project_id,
            rel,
            root_link=root_link,
            ee_link=ee_link,
            world_id=world_id,
            label=display,
        )
    if inferred == "mjcf":
        return attach_body_from_mjcf(
            project_id,
            rel,
            world_id=world_id,
            label=display,
        )
    return attach_body_from_json_pack(
        project_id,
        rel,
        world_id=world_id if world_id else None,
        label=display,
    )


def attach_body_from_urdf(
    project_id: str,
    urdf_path: str,
    *,
    chain_id: str | None = None,
    root_link: str = "base_link",
    ee_link: str | None = None,
    world_id: str = "earth_lab_1g",
    label: str | None = None,
) -> dict[str, Any]:
    """Attach a URDF as desk body (compile to chain IR). Not MEASURED / not Isaac GT."""
    import shutil

    from dogfood_platform.urdf_to_chain_ir_v1 import compile_urdf_to_chain_spec

    src = _resolve_repo_path(urdf_path)
    if not src.is_file():
        raise FileNotFoundError(f"urdf not found: {src}")
    rel = src.relative_to(_REPO).as_posix() if src.is_relative_to(_REPO) else src.name
    cid = chain_id or f"desk_urdf_{src.stem}_v1"
    compiled = compile_urdf_to_chain_spec(
        rel if src.is_relative_to(_REPO) else str(src),
        chain_id=cid,
        root_link=root_link,
        ee_link=ee_link,
    )
    used_root = str(compiled.get("root_link") or root_link)
    body_dir = project_dir(project_id) / "body"
    body_dir.mkdir(parents=True, exist_ok=True)
    dest = body_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    display = label or f"URDF {src.stem}"
    summary = {
        "kind": "urdf",
        "label": display,
        "world_id": world_id,
        "source_path": rel,
        "chain_id": cid,
        "dof": compiled.get("dof"),
        "ee_frame": compiled.get("ee_frame"),
        "root_link": used_root,
        "checks_pass": True,
        "proof_tier": compiled.get("proof_tier"),
    }
    _write_json(
        body_dir / "manifest.json",
        {
            "kind": "urdf",
            "summary": summary,
            "compiled": compiled,
            "source_file": src.name,
            "timestamp_utc": _now(),
            "honesty": {"not_measured": True, "not_isaac_gt": True},
        },
    )
    from dogfood_platform.body_identity_v1 import write_body_identity_artifact

    identity = write_body_identity_artifact(
        project_id,
        dest,
        kind="urdf",
        source_name=src.name,
        chain_id=cid,
        root_link=used_root,
        ee_link=str(compiled.get("ee_frame") or "") or None,
    )
    from dogfood_platform.silicon_fuse_v1 import bind_body_to_silicon_fuse

    bind_body_to_silicon_fuse(project_id, str(identity.get("body_sha256") or ""))
    doc = get_project(project_id)
    doc["body"] = {
        "kind": "urdf",
        "label": display,
        "world_id": world_id,
        "source_path": rel,
        "chain_id": cid,
        "checks_pass": True,
        "manifest_path": "body/manifest.json",
        "stored_file": f"body/{src.name}",
        "root_link": used_root,
        "ee_link": ee_link or compiled.get("ee_frame"),
        "summary": summary,
        "identity": identity,
    }
    return _save_project(doc)


def attach_body_from_mjcf(
    project_id: str,
    mjcf_path: str,
    *,
    world_id: str = "earth_lab_1g",
    label: str | None = None,
) -> dict[str, Any]:
    """Store MJCF reference on desk. TABU: MuJoCo as oracle / auto assembly→MJCF."""
    import shutil
    import xml.etree.ElementTree as ET

    src = _resolve_repo_path(mjcf_path)
    if not src.is_file():
        raise FileNotFoundError(f"mjcf not found: {src}")
    ET.parse(src)  # well-formed check
    rel = src.relative_to(_REPO).as_posix() if src.is_relative_to(_REPO) else src.name
    body_dir = project_dir(project_id) / "body"
    body_dir.mkdir(parents=True, exist_ok=True)
    dest = body_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    display = label or f"MJCF {src.stem}"
    summary = {
        "kind": "mjcf",
        "label": display,
        "world_id": world_id,
        "source_path": rel,
        "checks_pass": True,
        "note": "file-ref only - desk oracle remains the dual-probe world step",
    }
    _write_json(
        body_dir / "manifest.json",
        {
            "kind": "mjcf",
            "summary": summary,
            "source_file": src.name,
            "timestamp_utc": _now(),
            "honesty": {"not_mujoco_oracle": True, "not_measured": True},
        },
    )
    from dogfood_platform.body_identity_v1 import write_body_identity_artifact

    identity = write_body_identity_artifact(
        project_id,
        dest,
        kind="mjcf",
        source_name=src.name,
    )
    from dogfood_platform.silicon_fuse_v1 import bind_body_to_silicon_fuse

    bind_body_to_silicon_fuse(project_id, str(identity.get("body_sha256") or ""))
    doc = get_project(project_id)
    doc["body"] = {
        "kind": "mjcf",
        "label": display,
        "world_id": world_id,
        "source_path": rel,
        "checks_pass": True,
        "manifest_path": "body/manifest.json",
        "stored_file": f"body/{src.name}",
        "summary": summary,
        "identity": identity,
    }
    return _save_project(doc)


def attach_body_from_json_pack(
    project_id: str,
    pack_path: str,
    *,
    world_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Attach full-body / hexapod compose JSON pack after region honesty check."""
    import shutil

    from dogfood_platform.full_body_compose_v1 import load_full_body_spec, validate_region_honesty

    src = _resolve_repo_path(pack_path)
    if not src.is_file():
        raise FileNotFoundError(f"json pack not found: {src}")
    rel = src.relative_to(_REPO).as_posix() if src.is_relative_to(_REPO) else src.name
    spec = load_full_body_spec(src)
    honesty = validate_region_honesty(spec)
    fail = list(honesty.get("fail") or [])
    if fail:
        raise ValueError(f"json pack region honesty failed: {fail}")
    body_dir = project_dir(project_id) / "body"
    body_dir.mkdir(parents=True, exist_ok=True)
    dest = body_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    wid = world_id or str(spec.get("world_id") or "W_lunar_crater_robot_os_v1")
    display = label or str(spec.get("robot_id") or spec.get("compose_id") or src.stem)
    summary = {
        "kind": "json_pack",
        "label": display,
        "world_id": wid,
        "source_path": rel,
        "compose_id": spec.get("compose_id"),
        "robot_id": spec.get("robot_id"),
        "region_count": len(spec.get("regions") or []),
        "checks_pass": True,
        "honesty": {
            "total_dof": honesty.get("total_dof"),
            "fail": fail,
        },
    }
    _write_json(
        body_dir / "manifest.json",
        {
            "kind": "json_pack",
            "summary": summary,
            "spec_keys": sorted(spec.keys()),
            "source_file": src.name,
            "timestamp_utc": _now(),
            "honesty": {"not_optimus": True, "not_product_ready": True},
        },
    )
    from dogfood_platform.body_identity_v1 import write_body_identity_artifact

    identity = write_body_identity_artifact(
        project_id,
        dest,
        kind="json_pack",
        source_name=src.name,
    )
    from dogfood_platform.silicon_fuse_v1 import bind_body_to_silicon_fuse

    bind_body_to_silicon_fuse(project_id, str(identity.get("body_sha256") or ""))
    doc = get_project(project_id)
    doc["body"] = {
        "kind": "json_pack",
        "label": display,
        "world_id": wid,
        "source_path": rel,
        "checks_pass": True,
        "manifest_path": "body/manifest.json",
        "stored_file": f"body/{src.name}",
        "summary": summary,
        "identity": identity,
    }
    return _save_project(doc)


def _summarize_trace_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    commands: dict[str, int] = {}
    sources: dict[str, int] = {}
    for r in rows:
        cmd = str(r.get("command") or "?")
        src = str(r.get("source") or "unknown")
        commands[cmd] = commands.get(cmd, 0) + 1
        sources[src] = sources.get(src, 0) + 1
    return {
        "steps": len(rows),
        "commands": commands,
        "sources": sources,
        "first_cursor_m": rows[0].get("cursor_m") if rows else None,
        "last_cursor_m": rows[-1].get("cursor_m") if rows else None,
    }


def attach_policy_trace(project_id: str, text: str, *, filename: str = "policy.jsonl") -> dict[str, Any]:
    from dogfood_platform.start_here_replay_v1 import dump_sha256_text

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        rows.append(json.loads(s))
    if not rows:
        raise ValueError("policy trace has no JSONL rows")
    canonical = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    dump_sha = dump_sha256_text(canonical)
    trace_path = project_dir(project_id) / "policy" / "trace.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(canonical, encoding="utf-8")
    summary = _summarize_trace_rows(rows)
    meta_path = project_dir(project_id) / "policy" / "meta.json"
    _write_json(
        meta_path,
        {
            "filename": filename,
            "summary": summary,
            "dump_sha256": dump_sha,
            "timestamp_utc": _now(),
            "honesty": {"trace_replay": True, "not_robot_stack": True, "not_measured": True},
        },
    )
    doc = get_project(project_id)
    doc["policy"] = {
        "filename": filename,
        "path": "policy/trace.jsonl",
        "summary": summary,
        "kind": "policy_trace_jsonl",
        "dump_sha256": dump_sha,
    }
    return _save_project(doc)


def update_project_last_run(project_id: str, run: dict[str, Any]) -> dict[str, Any]:
    doc = get_project(project_id)
    doc["last_run_id"] = run.get("run_id")
    doc["last_run"] = {
        "run_id": run.get("run_id"),
        "condition": run.get("condition"),
        "timestamp_utc": run.get("timestamp_utc"),
        "diverged": (run.get("dual") or {}).get("diverged"),
        "ee_vetoes": ((run.get("ee") or {}) or {}).get("vetoes"),
        "closed_loop_ok": (run.get("closed_loop_v1") or {}).get("ok"),
        "closed_loop_falsifier": (run.get("closed_loop_v1") or {}).get("active_falsifier"),
    }
    doc["trust_tier"] = compute_trust_tier(doc)
    return _save_project(doc)


def update_project_field_lane(
    project_id: str,
    *,
    world_id: str,
    globe: str | None = None,
    field_bind: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind measurable field lane onto project body (Mission Moon/Earth/Mars → probe soils)."""
    doc = get_project(project_id)
    body = doc.get("body")
    if not isinstance(body, dict):
        raise ValueError(f"project {project_id} has no body to bind field lane")
    body = dict(body)
    body["world_id"] = world_id
    if globe:
        body["globe"] = globe
    if isinstance(field_bind, dict):
        body["field_bind"] = field_bind
    summary = body.get("summary") if isinstance(body.get("summary"), dict) else None
    if summary is not None:
        summary = dict(summary)
        summary["world_id"] = world_id
        if globe:
            summary["globe"] = globe
        body["summary"] = summary
    doc["body"] = body
    return _save_project(doc)


def compute_trust_tier(project: dict[str, Any] | None) -> str:
    """Honest UI ladder — T2 = HIL_SIM / degraded; never MEASURED / T3."""
    if not project:
        return "T0_demo"
    hil = project.get("hil") or {}
    hil_tier = str(hil.get("proof_tier") or "").upper()
    # Clamp: even corrupted receipts cannot surface as MEASURED/T3 in UI ladder
    if hil_tier in ("MEASURED", "MEASURED_FIELD", "T3", "FIELD"):
        return "T2_hil_sim"
    if hil and hil_tier == "DEGRADED_NO_RTL":
        return "T2_degraded_no_rtl"
    if hil and hil_tier in ("HIL_SIM", "HIL_SIM_RTL"):
        return "T2_hil_sim"
    if hil:
        # Unknown hil label — still T2 but mark degraded honesty via attach
        return "T2_hil_sim"
    has_body = project.get("body") is not None
    has_policy = project.get("policy") is not None
    has_port = project.get("policy_port") is not None
    has_run = bool(project.get("last_run_id") or project.get("last_run"))
    if has_run and (has_body or has_policy or has_port):
        return "T1_probed"
    if has_body and (has_policy or has_port):
        return "T1_bound"
    if has_body:
        return "T1_body"
    if has_port and not has_policy:
        return "T1_port"
    if has_policy:
        return "T1_policy"
    return "T1_empty"


TRUST_TIER_UI: dict[str, dict[str, str]] = {
    "T0_demo": {
        "label": "T0",
        "title": "Demo session · sim slice · not MEASURED · not T3",
    },
    "T1_empty": {
        "label": "T1·empty",
        "title": "T1 desk empty · create/attach body+port · not MEASURED",
    },
    "T1_body": {
        "label": "T1·body",
        "title": "T1 body attached · sim_slice · not MEASURED",
    },
    "T1_policy": {
        "label": "T1·policy",
        "title": "T1 audit trace attached · not PolicyPort alone · not MEASURED",
    },
    "T1_port": {
        "label": "T1·port",
        "title": "T1 PolicyPort attached · recorded proposals · not live VLA · not MEASURED",
    },
    "T1_bound": {
        "label": "T1·bound",
        "title": "T1 body+port bound · ready to probe · not MEASURED",
    },
    "T1_probed": {
        "label": "T1·probed",
        "title": "T1 dual-probe done · Earn HIL for T2 · not MEASURED field",
    },
    "T2_hil_sim": {
        "label": "T2·HIL_SIM",
        "title": "T2 HIL_SIM · highest desk rung · never MEASURED / never T3",
    },
    "T2_degraded_no_rtl": {
        "label": "T2·degraded",
        "title": "T2 DEGRADED_NO_RTL · honest skip-RTL · not MEASURED",
    },
}


def trust_tier_ui(tier: str | None) -> dict[str, str]:
    """UI label/title for trust pill — clamps unknown / MEASURED-looking ids."""
    key = str(tier or "T0_demo")
    upper = key.upper()
    if "MEASURED" in upper or upper in ("T3", "FIELD") or key.startswith("T3"):
        return {
            "label": "T2·clamp",
            "title": "Clamped — MEASURED/T3 refused on desk · showing T2 honesty wall",
            "tier": "T2_hil_sim",
        }
    meta = TRUST_TIER_UI.get(key) or TRUST_TIER_UI["T0_demo"]
    return {"label": meta["label"], "title": meta["title"], "tier": key}


_HIL_PRESETS: dict[str, Path] = {
    "golden_hil_sim": _REPO / "fixtures" / "interop" / "golden_hil_sim_receipt_v1.json",
    "degraded_no_rtl": _REPO / "fixtures" / "interop" / "golden_degraded_no_rtl_receipt_v1.json",
}


def attach_hil_receipt(
    project_id: str,
    *,
    preset_id: str | None = None,
    receipt: dict[str, Any] | None = None,
    filename: str = "hil_receipt.json",
) -> dict[str, Any]:
    """Attach HIL_SIM or DEGRADED_NO_RTL receipt — unlocks trust T2, never MEASURED."""
    if receipt is None and preset_id:
        path = _HIL_PRESETS.get(preset_id)
        if path is None or not path.is_file():
            raise ValueError(
                f"unknown hil preset_id={preset_id!r}; choose from {sorted(_HIL_PRESETS)}"
            )
        receipt = _read_json(path)
        filename = path.name
    if not isinstance(receipt, dict) or not receipt:
        raise ValueError("hil receipt required (preset_id or receipt object)")

    proof_tier = str(receipt.get("proof_tier") or "HIL_SIM")
    if proof_tier in ("MEASURED", "MEASURED_FIELD", "T3", "FIELD"):
        raise ValueError(
            f"refusing proof_tier={proof_tier!r} — desk T2 is HIL_SIM / DEGRADED only, not MEASURED"
        )
    if receipt.get("not_measured") is False:
        raise ValueError("receipt claims measured — refused")

    hil_dir = project_dir(project_id) / "hil"
    hil_dir.mkdir(parents=True, exist_ok=True)
    dest = hil_dir / filename
    stored = dict(receipt)
    stored.setdefault("not_measured", True)
    stored.setdefault("not_field", True)
    stored.setdefault("not_product_ready", True)
    stored["attached_utc"] = _now()
    stored["proof_tier"] = proof_tier
    _write_json(dest, stored)

    doc = get_project(project_id)
    doc["hil"] = {
        "receipt_id": stored.get("receipt_id") or dest.stem,
        "proof_tier": proof_tier,
        "preset_id": preset_id,
        "manifest_path": f"hil/{filename}",
        "not_measured": True,
        "not_field": True,
        "earned": bool(stored.get("earned")),
        "summary": stored.get("summary"),
    }
    honesty = dict(doc.get("honesty") or {})
    honesty["not_measured"] = True
    honesty["hil_sim_attached"] = proof_tier.startswith("HIL_SIM")
    honesty["degraded_no_rtl"] = proof_tier == "DEGRADED_NO_RTL"
    if stored.get("earned"):
        honesty["hil_earned"] = True
    doc["honesty"] = honesty
    return _save_project(doc)


_FLEET_PRESETS: dict[str, Path] = {
    "golden_fleet": _REPO / "fixtures" / "interop" / "golden_fleet_state_v1.json",
}


def attach_fleet_state(
    project_id: str,
    *,
    preset_id: str | None = None,
    state: dict[str, Any] | None = None,
    filename: str = "fleet_state.json",
) -> dict[str, Any]:
    """Attach validated fleet_state_v1 — G3 lite, not MEASURED fleet OS."""
    from dogfood_platform.fleet_state_contract_v1 import validate_fleet_state

    if state is None and preset_id:
        path = _FLEET_PRESETS.get(preset_id)
        if path is None or not path.is_file():
            raise ValueError(
                f"unknown fleet preset_id={preset_id!r}; choose from {sorted(_FLEET_PRESETS)}"
            )
        state = _read_json(path)
        filename = path.name
    if not isinstance(state, dict) or not state:
        raise ValueError("fleet state required (preset_id or state object)")

    meta = validate_fleet_state(state)
    fleet_dir = project_dir(project_id) / "fleet"
    fleet_dir.mkdir(parents=True, exist_ok=True)
    dest = fleet_dir / filename
    stored = dict(state)
    honesty = dict(stored.get("honesty") or {})
    honesty.setdefault("not_measured", True)
    honesty.setdefault("not_fleet_os", True)
    stored["honesty"] = honesty
    stored["attached_utc"] = _now()
    _write_json(dest, stored)

    doc = get_project(project_id)
    doc["fleet"] = {
        "state_id": meta["state_id"],
        "version": meta["version"],
        "mission_id": meta["mission_id"],
        "carrier_ids": meta["carrier_ids"],
        "preset_id": preset_id,
        "manifest_path": f"fleet/{filename}",
        "not_measured": True,
    }
    return _save_project(doc)


def enrich_project(doc: dict[str, Any]) -> dict[str, Any]:
    """Attach computed trust_tier without requiring a write."""
    out = dict(doc)
    out["trust_tier"] = compute_trust_tier(out)
    return out


def list_project_runs(project_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Newest-first run summaries from runs/*.json."""
    get_project(project_id)  # raises if missing
    runs_dir = project_dir(project_id) / "runs"
    if not runs_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in runs_dir.glob("run-*.json"):
        try:
            raw = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        dual = raw.get("dual") or {}
        rows.append(
            {
                "run_id": raw.get("run_id") or path.stem,
                "condition": raw.get("condition"),
                "timestamp_utc": raw.get("timestamp_utc"),
                "diverged": dual.get("diverged"),
                "stub_command": dual.get("stub_command"),
                "regolith_command": dual.get("regolith_command"),
                "foreign_command": dual.get("foreign_command"),
                "ee_vetoes": ((raw.get("ee") or {}) or {}).get("vetoes"),
                "path": f"runs/{path.name}",
            }
        )
    rows.sort(key=lambda r: r.get("timestamp_utc") or "", reverse=True)
    return rows[: max(1, min(limit, 100))]


def project_summary(doc: dict[str, Any]) -> dict[str, Any]:
    """Compact row for project switcher."""
    enriched = enrich_project(doc)
    return {
        "project_id": enriched["project_id"],
        "name": enriched.get("name"),
        "updated_utc": enriched.get("updated_utc"),
        "trust_tier": enriched["trust_tier"],
        "has_body": enriched.get("body") is not None,
        "has_policy": enriched.get("policy") is not None,
        "has_policy_port": enriched.get("policy_port") is not None,
        "has_hil": enriched.get("hil") is not None,
        "has_fleet": enriched.get("fleet") is not None,
        "last_run_id": enriched.get("last_run_id"),
        "last_run": enriched.get("last_run"),
    }


def attach_policy_port(
    project_id: str,
    text: str,
    *,
    filename: str = "policy_port.jsonl",
) -> dict[str, Any]:
    """Attach foreign PolicyPort proposals (validated) onto a durable project."""
    from dogfood_platform.policy_port_contract_v1 import parse_proposals_jsonl

    rows = parse_proposals_jsonl(text)
    port_dir = project_dir(project_id) / "policy_port"
    port_dir.mkdir(parents=True, exist_ok=True)
    path = port_dir / "proposals.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    sources: dict[str, int] = {}
    commands: dict[str, int] = {}
    for r in rows:
        sources[str(r["source"])] = sources.get(str(r["source"]), 0) + 1
        commands[str(r["command"])] = commands.get(str(r["command"]), 0) + 1
    summary = {
        "steps": len(rows),
        "commands": commands,
        "sources": sources,
        "first_command": rows[0]["command"],
        "last_command": rows[-1]["command"],
    }
    _write_json(
        port_dir / "meta.json",
        {
            "filename": filename,
            "summary": summary,
            "schema": "schemas/policy_port_proposal_v1.json",
            "timestamp_utc": _now(),
            "honesty": {
                "not_live_vla": True,
                "recorded_proposals": True,
                "sim_slice": True,
            },
        },
    )
    doc = get_project(project_id)
    doc["policy_port"] = {
        "filename": filename,
        "path": "policy_port/proposals.jsonl",
        "summary": summary,
        "kind": "policy_port_proposals_jsonl",
        "schema": "policy_port_proposal_v1",
    }
    return _save_project(doc)
