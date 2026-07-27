"""Start here session v1 — Load trace + Start robot presets (thin wedge).

Kinds:
  demo          — built-in dual-run (default)
  robot_preset  — assembly-lab recipe (novice start)
  loaded_trace  — operator JSONL (engineer bring-your-own)

TABU: claim full robot builder UI · claim product_ready · claim MEASURED field.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_TWIN = _REPO / "results" / "runtime" / "desk"
_RUNTIME = _REPO / "results" / "runtime"
_EE = _REPO.parent / "evidence_engine"
_EE_ART = _EE / "artifacts" / "gate_cinema_live"

SESSION_NAME = "start_here_session_v1.json"
LOADED_TRACE_NAME = "start_here_loaded_trace.jsonl"
SESSION_RECEIPT_HTML = "start_here_session_receipt.html"
SESSION_RECEIPT_JSON = "start_here_session_receipt.json"

PRESETS: dict[str, dict[str, Any]] = {
    "open_rrbot": {
        "label": "Open rrbot (2-DoF)",
        "blurb": "Open-registry arm — Dual Bekker + pack law default.",
        "kind": "open_registry",
        "registry_id": "ros_rrbot",
        "world_id": "earth_lab_open",
        "for": "stranger",
    },
    "open_diffbot": {
        "label": "Open diffbot",
        "blurb": "Open-registry differential base — Dual soil probe.",
        "kind": "open_registry",
        "registry_id": "ros_diffbot",
        "world_id": "earth_lab_open",
        "for": "stranger",
    },
    "lunar_scout": {
        "label": "Lunar scout",
        "blurb": "Hexapod assembly recipe — optional crater teaching world.",
        "recipe_id": "lunar_scout_field",
        "world_id": "W_lunar_crater_robot_os_v1",
        "for": "optional",
    },
    "earth_bench": {
        "label": "Earth bench",
        "blurb": "Create CLI + wheeled chassis + bench ingress — lab carrier starter.",
        "recipe_id": "earth_bench_carrier",
        "world_id": "earth_lab_1g",
        "for": "optional",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_paths() -> dict[str, Path]:
    return {
        "twin": _TWIN / SESSION_NAME,
        "runtime": _RUNTIME / SESSION_NAME,
        "trace": _TWIN / LOADED_TRACE_NAME,
        "receipt_html": _TWIN / SESSION_RECEIPT_HTML,
        "receipt_json": _TWIN / SESSION_RECEIPT_JSON,
    }


def default_demo_session() -> dict[str, Any]:
    return {
        "session_id": "start_here_session_v1",
        "kind": "demo",
        "label": "Built-in dual-run demo",
        "timestamp_utc": _now(),
        "rev": 1,
        "preset_id": None,
        "robot": None,
        "trace": None,
        "scene": {
            "clean": False,
            "sinkage_mm": None,
            "sinkage_risk": None,
            "globe": None,
            "note": "demo snapshot may drive World bed",
        },
        "pane_hints": {
            "policies": "Flip Safe/Hostile — Dual soils on the open body.",
            "mission": "Cinema mission under the shared condition flag.",
            "receipt": "Audit Dual / LAW / iron — not MEASURED field.",
        },
        "cta": {
            "novice": "New — open rrbot + Port ready — Run probe (Safe/Hostile Dual).",
            "engineer": "BYO URDF or open registry · Dual diverge · IRON opt-in (soft != OTP).",
        },
        "presets": [
            {"id": k, "label": v["label"], "blurb": v["blurb"], "for": v.get("for")}
            for k, v in PRESETS.items()
        ],
        "honesty": {
            "not_full_builder": True,
            "not_product_ready": True,
            "not_measured": True,
            "sim_slice": True,
            "default_body": "open_rrbot",
        },
    }


def clean_welcome_session() -> dict[str, Any]:
    """Stranger first-open: empty World bed, no leftover probe crater."""
    doc = default_demo_session()
    doc.update(
        {
            "kind": "welcome_clean",
            "label": "Start here — clean desk",
            "scene": {
                "clean": True,
                "sinkage_mm": 0.0,
                "sinkage_risk": False,
                "traverse_feasible": True,
                "globe": None,
                "condition": "safe",
                "note": "first open on this machine — Run probe to shape the bed",
            },
            "pane_hints": {
                "policies": "Clean World bed. New project → body → Run probe — Safe/Hostile Dual.",
                "mission": "Pick Moon / Earth / Mars — soils + g bind the bed (not lat/lon).",
                "receipt": "No probe yet — LAW idle until Dual exists.",
            },
            "cta": {
                "novice": "New → Pick body → Run probe. First open is empty on purpose.",
                "engineer": "Field globe sets soils; particles follow sinkage — not a wallpaper.",
            },
        }
    )
    return doc


def ensure_desk_boot(*, force_clean: bool = False) -> dict[str, Any]:
    """First machine open → clean scene. Returning → keep their last session/results."""
    from production_gate.desk_visitor_v1 import is_first_open, last_scene, mark_open

    if force_clean or is_first_open():
        doc = clean_welcome_session()
        write_session(doc)
        # Do not auto-activate a leftover operator project on first stranger paint
        try:
            from production_gate.robot_project_desk_v1 import clear_active_project

            clear_active_project()
        except Exception:
            pass
        boot = mark_open(active_project_id=None, globe=None, scene=doc.get("scene"))
        doc["boot"] = boot
        return doc

    doc = load_session()
    scene = last_scene()
    if isinstance(scene, dict) and scene.get("clean") is False:
        doc = dict(doc)
        doc["scene"] = scene
        write_session(doc)
    active_id = None
    try:
        from production_gate.desk_visitor_v1 import status as visitor_status
        from production_gate.robot_project_desk_v1 import (
            get_active_project,
            get_project,
            set_active_project,
        )

        active = get_active_project()
        active_id = str((active or {}).get("project_id") or "") or None
        if not active_id:
            # Returning desk: revive last project from local visitor vault if still on disk
            remembered = str(visitor_status().get("last_active_project_id") or "").strip()
            if remembered:
                try:
                    get_project(remembered)
                    active = set_active_project(remembered)
                    active_id = remembered
                except (FileNotFoundError, ValueError, KeyError, OSError):
                    active_id = None
    except Exception:
        active_id = None
    globe = None
    robot = doc.get("robot") if isinstance(doc.get("robot"), dict) else {}
    if isinstance(robot.get("field_bind"), dict):
        globe = robot["field_bind"].get("globe")
    globe = globe or robot.get("globe") or (doc.get("scene") or {}).get("globe")
    boot = mark_open(active_project_id=active_id, globe=globe, scene=doc.get("scene"))
    doc = dict(doc)
    doc["boot"] = boot
    if active_id:
        doc["restored_active_project_id"] = active_id
    return doc


def write_session(doc: dict[str, Any]) -> dict[str, Path]:
    from production_gate.atomic_json_v1 import atomic_write_text

    _TWIN.mkdir(parents=True, exist_ok=True)
    _RUNTIME.mkdir(parents=True, exist_ok=True)
    doc = dict(doc)
    doc["timestamp_utc"] = doc.get("timestamp_utc") or _now()
    doc["rev"] = int(doc.get("rev") or 0) + 1
    payload = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    paths = session_paths()
    atomic_write_text(paths["twin"], payload)
    atomic_write_text(paths["runtime"], payload)
    return paths


def load_session() -> dict[str, Any]:
    from production_gate.atomic_json_v1 import atomic_read_text

    p = session_paths()["twin"]
    if not p.is_file() or p.stat().st_size < 8:
        doc = default_demo_session()
        write_session(doc)
        return doc
    try:
        raw = atomic_read_text(p).strip()
        if not raw:
            raise json.JSONDecodeError("empty", "", 0)
        doc = json.loads(raw)
        if not isinstance(doc, dict) or not doc.get("session_id"):
            raise ValueError("session missing session_id")
        return doc
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        doc = default_demo_session()
        write_session(doc)
        return doc


def reset_demo_session() -> dict[str, Any]:
    doc = clean_welcome_session()
    write_session(doc)
    try:
        from production_gate.desk_visitor_v1 import remember_scene

        remember_scene(doc.get("scene") or {"clean": True})
    except Exception:
        pass
    return doc


def _summarize_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    return {
        "recipe_id": recipe.get("recipe_id"),
        "verdict": recipe.get("verdict"),
        "world_id": recipe.get("world_id"),
        "fail": recipe.get("fail") or [],
        "checks_pass": not (recipe.get("fail") or []),
        "create": recipe.get("create"),
        "manifest_path": recipe.get("manifest_path"),
        "fixture_id": recipe.get("fixture_id"),
        "operator_steps": recipe.get("operator_steps"),
        "keys": sorted(k for k in recipe.keys() if k not in ("checks",)),
    }


def start_robot_preset(preset_id: str) -> dict[str, Any]:
    """Novice path — open-registry preset or assembly-lab recipe → session bind."""
    if preset_id not in PRESETS:
        raise ValueError(f"unknown preset_id={preset_id!r}; choose from {sorted(PRESETS)}")

    meta = PRESETS[preset_id]

    # Open-registry strangers: no assembly recipe_id
    if meta.get("kind") == "open_registry" or not meta.get("recipe_id"):
        doc = {
            "session_id": "start_here_session_v1",
            "kind": "robot_preset",
            "label": meta["label"],
            "timestamp_utc": _now(),
            "rev": 0,
            "preset_id": preset_id,
            "robot": {
                "preset_id": preset_id,
                "label": meta["label"],
                "blurb": meta["blurb"],
                "world_id": meta["world_id"],
                "registry_id": meta.get("registry_id"),
                "kind": meta.get("kind") or "open_registry",
                "proof_tier": "START_HERE_OPEN_REGISTRY_PRESET",
            },
            "trace": None,
            "pane_hints": {
                "policies": f"{meta['label']} — Safe/Hostile Dual soils on this body.",
                "mission": f"Mission bound to {meta['label']} · world {meta['world_id']}.",
                "receipt": "Open registry body — Dual / LAW / iron · not MEASURED.",
            },
            "cta": {
                "novice": "Robot started. Flip Safe/Hostile · Run probe · Mission.",
                "engineer": "Or BYO URDF / Load trace.",
            },
            "presets": default_demo_session()["presets"],
            "honesty": {
                "not_full_builder": True,
                "not_product_ready": True,
                "not_measured": True,
                "open_registry": True,
            },
        }
        write_session(doc)
        return doc

    from production_gate.robot_hardware_assembly_lab_v1 import run_assembly_recipe

    recipe = run_assembly_recipe(str(meta["recipe_id"]))
    summary = _summarize_recipe(recipe)

    # Keep dual-run conditions available; bind robot story into session.
    doc = {
        "session_id": "start_here_session_v1",
        "kind": "robot_preset",
        "label": meta["label"],
        "timestamp_utc": _now(),
        "rev": 0,
        "preset_id": preset_id,
        "robot": {
            "preset_id": preset_id,
            "label": meta["label"],
            "blurb": meta["blurb"],
            "world_id": meta["world_id"],
            "recipe": summary,
            "proof_tier": "ROBOT_HARDWARE_ASSEMBLY_LAB_SLICE",
        },
        "trace": None,
        "pane_hints": {
            "policies": (
                f"Your starter robot: {meta['label']}. "
                "Safe/Hostile still probes policy divergence on the world gate."
            ),
            "mission": (
                f"Mission view bound to {meta['label']} · world {meta['world_id']}. "
                "Cinema remains the visual carrier for lunar; Earth shows recipe HUD."
            ),
            "receipt": (
                f"Assembly recipe verdict: {summary.get('verdict')}. "
                "Full builder UI is NOT here — gate recipe receipt is the proof."
            ),
        },
        "cta": {
            "novice": "Robot started. Flip condition · open Mission · read Receipt.",
            "engineer": "Or Load trace to replace policies with YOUR JSONL.",
        },
        "presets": default_demo_session()["presets"],
        "honesty": {
            "not_full_builder": True,
            "not_product_ready": True,
            "assembly_via_gate_recipes": True,
            "recipe_verdict": summary.get("verdict"),
        },
    }
    write_session(doc)
    # Write slim chip receipt for assembly start
    chip = _REPO / "results" / "platform_bpass" / "chip" / "START_HERE_ROBOT_PRESET_RECEIPT.json"
    chip.parent.mkdir(parents=True, exist_ok=True)
    chip.write_text(
        json.dumps(
            {
                "receipt_id": "START_HERE_ROBOT_PRESET_RECEIPT",
                "timestamp_utc": doc["timestamp_utc"],
                "preset_id": preset_id,
                "verdict": summary.get("verdict"),
                "recipe": summary,
                "honesty": doc["honesty"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return doc


def _parse_jsonl_text(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        rows.append(json.loads(s))
    if not rows:
        raise ValueError("trace has no JSONL rows")
    return rows


def _trace_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    commands: dict[str, int] = {}
    sources: dict[str, int] = {}
    for r in rows:
        cmd = str(r.get("command") or r.get("proposal", {}).get("command") or "?")
        src = str(r.get("source") or r.get("policy_source") or "unknown")
        commands[cmd] = commands.get(cmd, 0) + 1
        sources[src] = sources.get(src, 0) + 1
    return {
        "steps": len(rows),
        "commands": commands,
        "sources": sources,
        "first_cursor_m": rows[0].get("cursor_m"),
        "last_cursor_m": rows[-1].get("cursor_m"),
    }


def _eval_trace_to_receipt(trace_path: Path) -> dict[str, Any] | None:
    if not (_EE / "src").is_dir():
        return None
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_EE / "src")
    paths = session_paths()
    receipt_json = paths["receipt_json"]
    receipt_html = paths["receipt_html"]
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    r1 = subprocess.run(
        [
            sys.executable,
            "-m",
            "evidence_engine.cli",
            "eval",
            "--trace",
            str(trace_path),
            "--policy-source",
            "start_here_loaded_trace",
            "--out",
            str(receipt_json),
        ],
        cwd=str(_EE),
        env=env,
        capture_output=True,
        text=True,
        **hidden_run_kwargs(),
    )
    if r1.returncode not in (0, 1) or not receipt_json.is_file():
        return {
            "eval_ok": False,
            "returncode": r1.returncode,
            "stderr": (r1.stderr or "")[-500:],
        }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "evidence_engine.cli",
            "report",
            str(receipt_json),
            "--out",
            str(receipt_html),
        ],
        cwd=str(_EE),
        env=env,
        check=False,
        **hidden_run_kwargs(),
    )
    # Also point shell Receipt tab at session receipt when loaded
    shutil.copy2(receipt_html, _TWIN / "start_here_receipt.html")
    receipt = json.loads(receipt_json.read_text(encoding="utf-8"))
    return {
        "eval_ok": True,
        "verdict": "VERIFY_OK",
        "steps": (receipt.get("counters") or {}).get("steps"),
        "vetoes": (receipt.get("counters") or {}).get("vetoes"),
        "per_rule": (receipt.get("counters") or {}).get("per_rule"),
        "chain_final_hash": (receipt.get("chain_final_hash") or "")[:24],
        "receipt_html": SESSION_RECEIPT_HTML,
    }


def load_trace_text(text: str, *, filename: str = "uploaded.jsonl") -> dict[str, Any]:
    """Engineer path — bring your policy JSONL into the Start here desk."""
    from production_gate.start_here_replay_v1 import dump_sha256_text

    rows = _parse_jsonl_text(text)
    paths = session_paths()
    trace_path = paths["trace"]
    # Persist canonical JSONL (no comments)
    canonical = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    trace_path.write_text(canonical, encoding="utf-8")
    summary = _trace_summary(rows)
    eval_info = _eval_trace_to_receipt(trace_path)
    dump_sha = dump_sha256_text(canonical)
    if isinstance(eval_info, dict):
        eval_info = {**eval_info, "dump_sha256": dump_sha}

    doc = {
        "session_id": "start_here_session_v1",
        "kind": "loaded_trace",
        "label": filename,
        "timestamp_utc": _now(),
        "rev": 0,
        "preset_id": None,
        "robot": None,
        "trace": {
            "filename": filename,
            "path": LOADED_TRACE_NAME,
            "summary": summary,
            "eval": eval_info,
            "sample": rows[:3],
            "dump_sha256": dump_sha,
        },
        "pane_hints": {
            "policies": (
                f"Loaded {summary['steps']} steps from {filename}. "
                f"Commands: {summary['commands']}. This is YOUR dump. "
                f"sha={dump_sha[:12]}…"
            ),
            "mission": "Mission still shows cinema carrier; policies/receipt bound to loaded trace.",
            "receipt": (
                "Receipt regenerated from YOUR trace via Evidence Engine eval "
                if eval_info and eval_info.get("eval_ok")
                else "Trace loaded; EE eval unavailable — summary only."
            ),
        },
        "cta": {
            "novice": "Trace loaded. Open Receipt for veto timeline · Policies for command mix.",
            "engineer": "Swap file anytime · or Start robot for a body preset.",
        },
        "presets": default_demo_session()["presets"],
        "honesty": {
            "not_full_builder": True,
            "trace_replay": True,
            "your_artifact": True,
            "not_measured": True,
            "dump_sha256": dump_sha,
        },
    }
    write_session(doc)
    return doc


def load_trace_bytes(data: bytes, *, filename: str = "uploaded.jsonl") -> dict[str, Any]:
    text = data.decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    return load_trace_text(text, filename=filename)
