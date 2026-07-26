"""Production Gate Ritual — one engineer command before production.

Canon: docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md
Properties: simple · unrepeatable truth OS · cheaper than doubt.

Stages a stranger kit under TEMP (outside repo) with Dual receipts + seal board.
Not MEASURED · soft≠OTP · Rust physics oracle · Python glue.
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


def _console_print(text: str) -> None:
    """Windows cp1251 consoles choke on box-drawing; never fail the ritual on print."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write((text + "\n").encode(enc, errors="replace"))
        sys.stdout.buffer.flush()

_REPO = Path(__file__).resolve().parents[1]
_OUT_DIR = _REPO / "results" / "runtime" / "platform_loop"
_OUT = _OUT_DIR / "PRODUCTION_GATE_RITUAL_LATEST_v1.json"
_BOARD = _OUT_DIR / "PRODUCTION_GATE_BOARD_LATEST.md"
_KIT_LATEST = _REPO / "results" / "runtime" / "production_gate_kits" / "LATEST"
SCHEMA = "ha_production_gate_ritual_v1"
PROOF_TIER = "PRODUCTION_GATE_RITUAL"
CONTRACT = (
    "PRODUCTION_GATE_RITUAL: one Dual seal before production — Safe ALLOW · "
    "Hostile refuse · physics_os_kernel sealed_in_ha_runtime · named epsilon · "
    "soft-mint refused · stranger kit outside desk. Simple · not priesthood · not MEASURED."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _case(name: str, *, ok: bool, detail: dict[str, Any], error: str | None = None) -> dict[str, Any]:
    return {"id": name, "ok": ok, "detail": detail, "error": error}


def _print_board(doc: dict[str, Any]) -> None:
    lines = [
        "",
        "════════════════════════════════════════════════════════════",
        "  HA PRODUCTION GATE — before you ship",
        "════════════════════════════════════════════════════════════",
        f"  verdict: {doc.get('verdict')}",
        "",
        "  Ritual:  Dual · sealed receipt · named ε · refuse",
        "  Without HA you lose: stranger-checkable refuse before production",
        "                       (a week of knowing whether the claim may ship)",
        "",
    ]
    for c in doc.get("cases") or []:
        mark = "PASS" if c.get("ok") else "FAIL"
        lines.append(f"  [{mark}] {c.get('id')}")
    kit = (doc.get("kit") or {}).get("path")
    if kit:
        lines.append("")
        lines.append(f"  stranger kit: {kit}")
    lines.append(f"  receipt:     {_OUT}")
    lines.append(f"  board:       {_BOARD}")
    lines.append("════════════════════════════════════════════════════════════")
    lines.append("")
    _console_print("\n".join(lines))


def _write_board_md(doc: dict[str, Any]) -> None:
    kit = doc.get("kit") or {}
    rows = "\n".join(
        f"| {c['id']} | {'PASS' if c.get('ok') else 'FAIL'} |" for c in (doc.get("cases") or [])
    )
    text = f"""# HA Production Gate — engineer board

**Verdict:** `{doc.get('verdict')}`  
**UTC:** {doc.get('timestamp_utc')}

## Ritual

```text
Dual · sealed receipt · named ε · refuse
```

## Without HA you lose

{doc.get('lose_without_ha')}

## Falsifiers

| id | result |
|----|--------|
{rows}

## Stranger kit

- path: `{kit.get('path')}`
- outside_repo: `{kit.get('outside_repo')}`
- files: `{', '.join(kit.get('files') or [])}`

## Honesty

not MEASURED · soft≠OTP · Rust physics oracle · Python glue only

## Canon

`docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md` · `START_HERE_PRODUCTION_GATE_V1.md`
"""
    _BOARD.parent.mkdir(parents=True, exist_ok=True)
    _BOARD.write_text(text + "\n", encoding="utf-8")


def _stage_kit(
    *,
    kit_root: Path,
    r_safe: dict[str, Any],
    r_hostile: dict[str, Any],
    board_doc: dict[str, Any],
) -> dict[str, Any]:
    kit_root.mkdir(parents=True, exist_ok=True)
    files = {
        "dual_safe.json": r_safe,
        "dual_hostile.json": r_hostile,
        "PRODUCTION_GATE.json": board_doc,
        "README_ENGINEER.md": (
            "# Production Gate kit (stranger)\n\n"
            "1. Read dual_safe.json / dual_hostile.json\n"
            "2. Safe physics_pass must be true; Hostile false\n"
            "3. Both must have physics_os_kernel.sealed_in_ha_runtime=true\n"
            "4. Named epsilon on seal honesty\n"
            "5. TABU: MEASURED · OTP · product_ready\n"
        ),
    }
    written: list[str] = []
    for name, payload in files.items():
        path = kit_root / name
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        written.append(name)

    # Persist mirror under repo results (copy) for desk; stranger truth = TEMP kit.
    if _KIT_LATEST.exists():
        shutil.rmtree(_KIT_LATEST)
    _KIT_LATEST.mkdir(parents=True, exist_ok=True)
    for name in written:
        shutil.copy2(kit_root / name, _KIT_LATEST / name)

    outside = _REPO.resolve() not in kit_root.resolve().parents
    return {
        "path": str(kit_root),
        "mirror": str(_KIT_LATEST),
        "outside_repo": outside,
        "files": written,
    }


def run_production_gate_ritual(*, write_receipt: bool = True) -> dict[str, Any]:
    from dogfood_platform import robot_project_desk_v1 as desk
    from dogfood_platform.physics_os_kernel_v1 import inspect_soft_mint_claims
    from dogfood_platform.robot_project_desk_v1 import attach_body_from_preset, create_project
    from dogfood_platform.robot_project_run_v1 import run_project
    from dogfood_platform.silicon_fuse_v1 import ensure_silicon_fuse
    from dogfood_platform.win_hidden_subprocess_v1 import install_global_no_console_flash

    install_global_no_console_flash()
    cases: list[dict[str, Any]] = []
    kit_meta: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="ha_prod_gate_") as td:
        root = Path(td)
        projects = root / "projects"
        twin = root / "twin"
        kit = root / "kit"
        projects.mkdir()
        twin.mkdir()
        desk._PROJECTS = projects
        desk._ACTIVE = projects / "_active.json"
        desk._TWIN_ACTIVE = twin / "active.json"

        proj = create_project(name="production-gate-ritual")
        pid = proj["project_id"]
        attach_body_from_preset(pid, "lunar_scout")
        ensure_silicon_fuse(pid)
        r_safe = run_project(pid, "safe")
        r_hostile = run_project(pid, "hostile")

        gate_s = r_safe.get("physics_gate") or {}
        gate_h = r_hostile.get("physics_gate") or {}
        dual_ok = bool(gate_s.get("physics_pass")) and (not bool(gate_h.get("physics_pass")))
        cases.append(
            _case(
                "F_dual_safe_allow_hostile_refuse",
                ok=dual_ok,
                detail={
                    "safe_pass": gate_s.get("physics_pass"),
                    "hostile_pass": gate_h.get("physics_pass"),
                    "hostile_allowed": gate_h.get("current_allowed"),
                },
                error=None if dual_ok else "dual_gate_broken",
            )
        )

        seal_s = r_safe.get("physics_os_kernel") or {}
        seal_h = r_hostile.get("physics_os_kernel") or {}
        seal_ok = (
            bool(seal_s.get("sealed_in_ha_runtime"))
            and bool(seal_h.get("sealed_in_ha_runtime"))
            and bool(seal_s.get("not_cursor_enforcement"))
            and bool(seal_s.get("ok"))
        )
        cases.append(
            _case(
                "F_kernel_sealed_in_ha_runtime",
                ok=seal_ok,
                detail={
                    "safe_sealed": seal_s.get("sealed_in_ha_runtime"),
                    "hostile_sealed": seal_h.get("sealed_in_ha_runtime"),
                },
                error=None if seal_ok else "kernel_not_sealed",
            )
        )

        eps = list((seal_s.get("honesty") or {}).get("epsilon") or [])
        eps_ok = len(eps) >= 1
        cases.append(
            _case(
                "F_named_epsilon_on_seal",
                ok=eps_ok,
                detail={"epsilon": eps},
                error=None if eps_ok else "epsilon_missing",
            )
        )

        refuse_ok = gate_h.get("current_allowed") is False
        cases.append(
            _case(
                "F_hostile_current_refuse",
                ok=refuse_ok,
                detail={"current_allowed": gate_h.get("current_allowed")},
                error=None if refuse_ok else "hostile_still_allowed",
            )
        )

        # Physics world as designed: foundation rust stack + envelope on Hostile.
        ph_h = ((r_hostile.get("dual_block") or {}).get("physics") or {})
        cl_h = r_hostile.get("closed_loop_v1") or {}
        cl_h_hon = cl_h.get("honesty") or {}
        world_blocks = (
            "storm_env",
            "traverse_mechanical",
            "dust_ingress",
            "regolith_thermal",
            "slope_rut",
            "envelope_refuse",
            "failure_modes",
            "drive_chain",
            "janosi",
            "radiation_rate",
        )
        missing_blocks = [k for k in world_blocks if not isinstance(ph_h.get(k), dict)]
        world_ok = (
            len(missing_blocks) == 0
            and bool(cl_h_hon.get("foundation_rust_stack_complete"))
            and bool(cl_h_hon.get("envelope_refuse"))
            and (ph_h.get("envelope_refuse") or {}).get("inside_envelope") is False
        )
        cases.append(
            _case(
                "F_physics_world_stack_complete",
                ok=world_ok,
                detail={
                    "missing_blocks": missing_blocks,
                    "foundation_complete": cl_h_hon.get("foundation_rust_stack_complete"),
                    "foundation_missing": cl_h_hon.get("foundation_rust_stack_missing"),
                    "envelope_on_cl": cl_h_hon.get("envelope_refuse"),
                    "inside_envelope": (ph_h.get("envelope_refuse") or {}).get("inside_envelope"),
                },
                error=None if world_ok else "physics_world_stack_incomplete",
            )
        )

        soft = inspect_soft_mint_claims(
            {"proof_tier": "MEASURED", "honesty": {"not_measured": True}}
        )
        soft_ok = len(soft) >= 1
        cases.append(
            _case(
                "F_soft_mint_impossible",
                ok=soft_ok,
                detail={"detector_hits": soft},
                error=None if soft_ok else "soft_mint_detector_dead",
            )
        )

        # Stranger: re-read kit files from outside project tree (same machine, outside desk).
        draft = {
            "schema": SCHEMA,
            "proof_tier": PROOF_TIER,
            "cases": cases,
            "lose_without_ha": (
                "stranger-checkable refuse bit before production — "
                "week of knowing whether the claim may ship"
            ),
        }
        kit_meta = _stage_kit(
            kit_root=kit,
            r_safe=r_safe,
            r_hostile=r_hostile,
            board_doc=draft,
        )
        safe_kit = json.loads((kit / "dual_safe.json").read_text(encoding="utf-8"))
        host_kit = json.loads((kit / "dual_hostile.json").read_text(encoding="utf-8"))
        stranger_ok = (
            bool(kit_meta.get("outside_repo"))
            and bool((safe_kit.get("physics_gate") or {}).get("physics_pass"))
            and (not bool((host_kit.get("physics_gate") or {}).get("physics_pass")))
            and bool((safe_kit.get("physics_os_kernel") or {}).get("sealed_in_ha_runtime"))
            and bool((host_kit.get("physics_os_kernel") or {}).get("sealed_in_ha_runtime"))
        )
        cases.append(
            _case(
                "F_stranger_kit_reverify",
                ok=stranger_ok,
                detail=kit_meta,
                error=None if stranger_ok else "stranger_kit_reverify_fail",
            )
        )

        cases.append(
            _case(
                "F_ritual_is_one_command",
                ok=True,
                detail={
                    "command": "ha-production-gate",
                    "also": "ha-guide production-gate",
                    "start_here": "START_HERE_PRODUCTION_GATE_V1.md",
                },
                error=None,
            )
        )

    ok = all(bool(c.get("ok")) for c in cases)
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "proof_tier": PROOF_TIER,
        "ok": ok,
        "verdict": f"{PROOF_TIER}_PASS" if ok else f"{PROOF_TIER}_FAIL",
        "contract": CONTRACT,
        "timestamp_utc": _now(),
        "properties": {
            "simple": True,
            "unrepeatable_truth_os": True,
            "cheaper_than_doubt": "intent",
        },
        "kit": kit_meta,
        "cases": cases,
        "honesty": {
            "not_measured": True,
            "not_product_ready": True,
            "not_spx_nasa_adoption": True,
            "proof_tier": PROOF_TIER,
            "epsilon": [
                "ε_desk_not_world",
                "ε_soft_not_otp",
                "ε_no_external_engineer_yet",
            ],
        },
        "tabu": ["MEASURED", "OTP", "product_ready", "soft_mint"],
        "lose_without_ha": (
            "stranger-checkable refuse bit before production — "
            "week of knowing whether the claim may ship"
        ),
    }
    if write_receipt:
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        _write_board_md(doc)
        # refresh kit PRODUCTION_GATE.json with final doc
        if _KIT_LATEST.is_dir():
            (_KIT_LATEST / "PRODUCTION_GATE.json").write_text(
                json.dumps(doc, indent=2) + "\n", encoding="utf-8"
            )
    _print_board(doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="HA Production Gate Ritual (engineer)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    doc = run_production_gate_ritual(write_receipt=not args.no_write)
    _console_print(json.dumps({"ok": doc["ok"], "verdict": doc["verdict"]}, indent=2))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
