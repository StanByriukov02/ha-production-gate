"""Dual socket — bring a body (+ optional owned soils), get Safe ALLOW / Hostile REFUSE.

Robotics wedge: open ROS tutorial body OR your URDF → Dual board with Bekker
sinkage numbers. Soft teaching · not MEASURED · not a Gazebo plugin (yet).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_OUT_DIR = _REPO / "results" / "runtime" / "platform_loop"
_BOARD = _OUT_DIR / "DUAL_SOCKET_BOARD_LATEST.md"
_RECEIPT = _OUT_DIR / "DUAL_SOCKET_LATEST_v1.json"
SCHEMA = "ha_dual_socket_v1"
PROOF_TIER = "DUAL_SOCKET_SLICE"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _console(text: str) -> None:
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write((text + "\n").encode(enc, errors="replace"))
        sys.stdout.buffer.flush()


def _bekker_slice(run: dict[str, Any]) -> dict[str, Any]:
    ph = ((run.get("dual_block") or {}).get("physics") or {})
    bek = ph.get("bekker") if isinstance(ph.get("bekker"), dict) else {}
    gate = run.get("physics_gate") or {}
    return {
        "soil_id": bek.get("soil_id") or ph.get("soil_id"),
        "sinkage_mm": bek.get("sinkage_mm", ph.get("sinkage_mm")),
        "sinkage_risk": bek.get("sinkage_risk", ph.get("sinkage_risk")),
        "drawbar_pull_n": bek.get("drawbar_pull_n"),
        "traverse_feasible": bek.get("traverse_feasible"),
        "physics_pass": gate.get("physics_pass"),
        "current_allowed": gate.get("current_allowed"),
        "g_mps2": ph.get("g_mps2"),
        "ground_pressure_kpa": ph.get("ground_pressure_kpa"),
        "contact_width_b_m": ph.get("contact_width_b_m"),
        "contact_area_m2": ph.get("contact_area_m2"),
    }


def _contact_slice(run: dict[str, Any], body: dict[str, Any] | None) -> dict[str, Any]:
    from production_gate.body_contact_geometry_v1 import contact_from_body

    dual = run.get("dual_block") if isinstance(run.get("dual_block"), dict) else {}
    # Prefer live body resolution (includes owned overrides)
    contact = contact_from_body(body)
    load_keys = (
        "ground_pressure_kpa",
        "contact_width_b_m",
        "contact_area_m2",
    )
    ph = dual.get("physics") if isinstance(dual.get("physics"), dict) else {}
    out = {
        "mass_kg": contact.get("mass_kg"),
        "n_contacts": contact.get("n_contacts"),
        "contact_width_m": contact.get("contact_width_m"),
        "contact_length_m": contact.get("contact_length_m"),
        "contact_area_m2": contact.get("contact_area_m2"),
        "source": contact.get("source"),
        "owned": bool((body or {}).get("owned_contact")),
    }
    for k in load_keys:
        if ph.get(k) is not None:
            out[k] = ph.get(k)
    return out


def run_dual_socket(
    *,
    preset: str | None = None,
    urdf: str | Path | None = None,
    soils: str | Path | None = None,
    root_link: str = "base_link",
    ee_link: str | None = None,
    model_kind: str | None = None,
    mass_kg: float | None = None,
    n_contacts: float | None = None,
    contact_width_m: float | None = None,
    contact_length_m: float | None = None,
    world_id: str | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Run Safe+Hostile Dual on a preset or stranger URDF (+ optional owned soils)."""
    from production_gate import robot_project_desk_v1 as desk
    from production_gate.robot_project_desk_v1 import (
        PRESETS,
        attach_body_from_preset,
        attach_body_from_urdf,
        create_project,
        get_project,
    )
    from production_gate.robot_project_run_v1 import run_project
    from production_gate.silicon_fuse_v1 import ensure_silicon_fuse
    from production_gate.win_hidden_subprocess_v1 import install_global_no_console_flash

    if not preset and not urdf:
        raise ValueError("pass --preset open_diffbot|open_rrbot|… or --urdf PATH")
    if preset and urdf:
        raise ValueError("use either --preset or --urdf, not both")
    if preset and preset not in PRESETS:
        raise ValueError(f"unknown preset={preset!r}; known={sorted(PRESETS)}")

    owned_pack = None
    owned_apply: dict[str, Any] | None = None
    if soils:
        from production_gate.dual_owned_soils_v1 import (
            apply_owned_pack_to_project,
            load_owned_soils,
        )

        owned_pack = load_owned_soils(soils)
        # CLI contact flags win over pack contact when both set
        if mass_kg is None and owned_pack.get("contact"):
            mass_kg = float(owned_pack["contact"]["mass_kg"])
        if n_contacts is None and owned_pack.get("contact"):
            n_contacts = float(owned_pack["contact"]["n_contacts"])
        if contact_width_m is None and owned_pack.get("contact"):
            contact_width_m = float(owned_pack["contact"]["contact_width_m"])
        if contact_length_m is None and owned_pack.get("contact"):
            contact_length_m = float(owned_pack["contact"]["contact_length_m"])

    install_global_no_console_flash()

    from production_gate.terramech_bekker_on_v1 import set_bekker_catalog_override

    catalog_prev = set_bekker_catalog_override(None)
    r_safe: dict[str, Any]
    r_hostile: dict[str, Any]
    contact_used: dict[str, Any]
    body_meta = {}
    try:
        with tempfile.TemporaryDirectory(prefix="ha_dual_socket_") as td:
            root = Path(td)
            projects = root / "projects"
            twin = root / "twin"
            projects.mkdir()
            twin.mkdir()
            desk._PROJECTS = projects
            desk._ACTIVE = projects / "_active.json"
            desk._TWIN_ACTIVE = twin / "active.json"

            # If URDF is outside the repo, stage a copy under TEMP so attach can resolve.
            staged_urdf: str | None = None
            if urdf:
                src = Path(urdf).expanduser().resolve()
                if not src.is_file():
                    raise FileNotFoundError(f"urdf not found: {src}")
                if _REPO.resolve() not in src.parents and src != _REPO.resolve():
                    scratch = _REPO / "results" / "runtime" / "byo_urdf"
                    scratch.mkdir(parents=True, exist_ok=True)
                    dest2 = scratch / src.name
                    shutil.copy2(src, dest2)
                    staged_urdf = dest2.relative_to(_REPO).as_posix()
                else:
                    staged_urdf = src.relative_to(_REPO).as_posix()

            proj = create_project(name="dual-socket")
            pid = str(proj["project_id"])
            if preset:
                attach_body_from_preset(pid, preset)
                meta = PRESETS[preset]
                wid = world_id or str(meta.get("world_id") or "earth_lab_open")
                body_meta = {"mode": "preset", "preset": preset, "world_id": wid}
                # Apply CLI contact overrides onto preset body
                if any(
                    v is not None
                    for v in (mass_kg, n_contacts, contact_width_m, contact_length_m)
                ):
                    doc_b = get_project(pid)
                    body = dict(doc_b.get("body") or {})
                    body["contact_override"] = True
                    if mass_kg is not None:
                        body["mass_kg"] = float(mass_kg)
                    if n_contacts is not None:
                        body["n_contacts"] = float(n_contacts)
                    if contact_width_m is not None:
                        body["contact_width_m"] = float(contact_width_m)
                    if contact_length_m is not None:
                        body["contact_length_m"] = float(contact_length_m)
                    if owned_pack and owned_pack.get("contact"):
                        body["owned_contact"] = True
                    doc_b["body"] = body
                    desk._save_project(doc_b)
            else:
                assert staged_urdf is not None
                kind = (model_kind or "wheeled_base").strip().lower()
                wid = world_id or "earth_lab_open"
                attach_body_from_urdf(
                    pid,
                    staged_urdf,
                    root_link=root_link,
                    ee_link=ee_link,
                    world_id=wid,
                    label=f"BYO {Path(staged_urdf).name}",
                    model_kind=kind,
                    mass_kg=mass_kg,
                    n_contacts=n_contacts,
                    contact_width_m=contact_width_m,
                    contact_length_m=contact_length_m,
                )
                body_meta = {
                    "mode": "urdf",
                    "urdf": staged_urdf,
                    "world_id": wid,
                    "model_kind": kind,
                }

            if owned_pack is not None:
                owned_apply = apply_owned_pack_to_project(pid, owned_pack)
                body_meta["owned_soils"] = {
                    "path": owned_pack.get("path"),
                    "safe": owned_pack["safe_soil_id"],
                    "hostile": owned_pack["hostile_soil_id"],
                    "g_mps2": owned_pack["g_mps2"],
                    "catalog": (owned_apply or {}).get("catalog_path"),
                }

            ensure_silicon_fuse(pid)
            body_live = get_project(pid).get("body") or {}
            r_safe = run_project(pid, "safe")
            r_hostile = run_project(pid, "hostile")
            contact_used = _contact_slice(
                r_safe, body_live if isinstance(body_live, dict) else None
            )
    finally:
        set_bekker_catalog_override(catalog_prev)

    safe = _bekker_slice(r_safe)
    hostile = _bekker_slice(r_hostile)
    dual_ok = bool(safe.get("physics_pass")) and (not bool(hostile.get("physics_pass")))
    refuse_ok = hostile.get("current_allowed") is False
    verdict = "DUAL_SOCKET_PASS" if (dual_ok and refuse_ok) else "DUAL_SOCKET_FAIL"

    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "proof_tier": PROOF_TIER,
        "timestamp_utc": _now(),
        "verdict": verdict,
        "body": body_meta,
        "contact": contact_used,
        "soils": {
            "safe_id": safe.get("soil_id"),
            "hostile_id": hostile.get("soil_id"),
            "owned_path": (owned_pack or {}).get("path") if owned_pack else None,
            "catalog": (owned_apply or {}).get("catalog_path") if owned_apply else None,
        },
        "safe": safe,
        "hostile": hostile,
        "dual_ok": dual_ok,
        "honesty": {
            "soft_teaching": True,
            "not_measured": True,
            "not_gazebo_plugin": True,
            "thin_ros2_wrapper": "ros2/ha_dual_ros2 · ha-dual-ros2 CLI",
            "socket": "URDF|open preset + optional owned soils → Dual Bekker refuse",
            "owned_soils": bool(owned_pack),
        },
    }

    if write_receipt:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        board = f"""# Dual socket board

**Verdict:** `{verdict}`  
**UTC:** {doc["timestamp_utc"]}

## Body

```json
{json.dumps(body_meta, indent=2)}
```

## Contact used

```json
{json.dumps(contact_used, indent=2)}
```

## Soils

| Lane | soil_id | source |
|------|---------|--------|
| Safe | {safe.get("soil_id")} | {"owned" if owned_pack else "default catalog"} |
| Hostile | {hostile.get("soil_id")} | {"owned" if owned_pack else "default catalog"} |

Owned pack: `{doc["soils"].get("owned_path") or "—"}`  
Catalog: `{doc["soils"].get("catalog") or "fixtures/.../bekker_soils_on_v1.json"}`

## Sinkage Dual

| Lane | soil | sinkage_mm | gate |
|------|------|------------|------|
| Safe | {safe.get("soil_id")} | {safe.get("sinkage_mm")} | pass={safe.get("physics_pass")} allowed={safe.get("current_allowed")} |
| Hostile | {hostile.get("soil_id")} | {hostile.get("sinkage_mm")} | pass={hostile.get("physics_pass")} allowed={hostile.get("current_allowed")} |

## Honesty

soft teaching Dual · not MEASURED · owned soils when provided · thin ros2 wrapper available (T5) · Rust Bekker oracle
"""
        _BOARD.write_text(board + "\n", encoding="utf-8")
        doc["board_path"] = str(_BOARD)
        doc["receipt_path"] = str(_RECEIPT)

    return doc


def _print_doc(doc: dict[str, Any]) -> None:
    safe = doc.get("safe") or {}
    hostile = doc.get("hostile") or {}
    contact = doc.get("contact") or {}
    soils = doc.get("soils") or {}
    lines = [
        "",
        "════════════════════════════════════════════════════════════",
        "  HA DUAL SOCKET — your body · Safe ALLOW · Hostile REFUSE",
        "════════════════════════════════════════════════════════════",
        f"  verdict: {doc.get('verdict')}",
        f"  body:    {json.dumps(doc.get('body') or {}, ensure_ascii=False)}",
        f"  contact: mass_kg={contact.get('mass_kg')} n={contact.get('n_contacts')} "
        f"w={contact.get('contact_width_m')} L={contact.get('contact_length_m')} "
        f"src={contact.get('source')}",
        f"  soils:   safe={soils.get('safe_id')} hostile={soils.get('hostile_id')} "
        f"owned={bool(soils.get('owned_path'))}",
        "",
        f"  Safe     soil={safe.get('soil_id')}  sinkage_mm={safe.get('sinkage_mm')}  "
        f"pass={safe.get('physics_pass')} allowed={safe.get('current_allowed')}",
        f"  Hostile  soil={hostile.get('soil_id')}  sinkage_mm={hostile.get('sinkage_mm')}  "
        f"pass={hostile.get('physics_pass')} allowed={hostile.get('current_allowed')}",
        "",
        f"  board:   {doc.get('board_path') or _BOARD}",
        "════════════════════════════════════════════════════════════",
        "",
    ]
    _console("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ha-dual-socket",
        description=(
            "Robotics socket: body + optional owned soils.json → Dual Safe/Hostile board"
        ),
    )
    p.add_argument(
        "--preset",
        choices=sorted(
            {
                "open_diffbot",
                "open_rrbot",
                "lunar_scout",
                "earth_bench",
            }
        ),
        help="Open/teaching body preset (prefer open_diffbot for ROS-shaped entry)",
    )
    p.add_argument("--urdf", type=str, help="Path to your URDF (copied into runtime scratch)")
    p.add_argument(
        "--soils",
        type=str,
        default=None,
        help="Owned Dual soils JSON (ha_dual_owned_soils_v1) — your Safe/Hostile + optional contact",
    )
    p.add_argument("--root-link", default="base_link")
    p.add_argument("--ee-link", default=None)
    p.add_argument(
        "--kind",
        dest="model_kind",
        default="wheeled_base",
        help="Teaching contact kind when using --urdf (wheeled_base|hexapod|arm|chassis|…)",
    )
    p.add_argument("--mass-kg", type=float, default=None)
    p.add_argument("--n-contacts", type=float, default=None)
    p.add_argument("--contact-width-m", type=float, default=None)
    p.add_argument("--contact-length-m", type=float, default=None)
    p.add_argument("--world-id", default=None)
    p.add_argument("--json", action="store_true", help="Print receipt JSON only")
    args = p.parse_args(argv)

    try:
        doc = run_dual_socket(
            preset=args.preset,
            urdf=args.urdf,
            soils=args.soils,
            root_link=args.root_link,
            ee_link=args.ee_link,
            model_kind=args.model_kind,
            mass_kg=args.mass_kg,
            n_contacts=args.n_contacts,
            contact_width_m=args.contact_width_m,
            contact_length_m=args.contact_length_m,
            world_id=args.world_id,
        )
    except Exception as exc:  # noqa: BLE001 — CLI surface
        _console(f"DUAL_SOCKET_ERROR: {exc}")
        return 2

    if args.json:
        _console(json.dumps(doc, indent=2))
    else:
        _print_doc(doc)
        _console(
            json.dumps(
                {"ok": doc.get("verdict") == "DUAL_SOCKET_PASS", "verdict": doc.get("verdict")}
            )
        )
    return 0 if doc.get("verdict") == "DUAL_SOCKET_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
