"""Soft-release engineer pack — stage what a stranger runs for Production Gate.

Not product_ready · not MEASURED · Rust physics oracle · Python glue.
TABU: vault paths · draft tone · agent notes in the pack.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_OUT_ROOT = _REPO / "results" / "runtime" / "release_engineer"
_LATEST = _OUT_ROOT / "LATEST"
SCHEMA = "ha_release_engineer_pack_v1"
PROOF_TIER = "RELEASE_ENGINEER_SOFT"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy(src: Path, dst: Path) -> bool:
    if not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def build_release_engineer_pack(*, write: bool = True) -> dict[str, Any]:
    from dogfood_platform.prove_production_gate_ritual_v1 import run_production_gate_ritual
    from dogfood_platform.win_hidden_subprocess_v1 import install_global_no_console_flash

    install_global_no_console_flash()
    gate = run_production_gate_ritual(write_receipt=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pack_dir = _OUT_ROOT / f"ha-production-gate-{stamp}"
    if write:
        if _LATEST.exists():
            shutil.rmtree(_LATEST)
        pack_dir.mkdir(parents=True, exist_ok=True)
        _LATEST.mkdir(parents=True, exist_ok=True)

    files_ok: dict[str, bool] = {}
    # Engineer surface only — no vault, no journal, no compass.
    copies = {
        "START_HERE.md": _REPO / "START_HERE_PRODUCTION_GATE_V1.md",
        "PRODUCTION_GATE_RITUAL.md": _REPO / "docs" / "agent_workflow" / "PRODUCTION_GATE_RITUAL_V1.md",
        "README.md": _REPO / "README.md",
        "PRODUCTION_GATE.json": _REPO
        / "results"
        / "runtime"
        / "platform_loop"
        / "PRODUCTION_GATE_RITUAL_LATEST_v1.json",
        "PRODUCTION_GATE_BOARD.md": _REPO
        / "results"
        / "runtime"
        / "platform_loop"
        / "PRODUCTION_GATE_BOARD_LATEST.md",
    }
    kit_src = _REPO / "results" / "runtime" / "production_gate_kits" / "LATEST"
    if write:
        for name, src in copies.items():
            files_ok[name] = _copy(src, pack_dir / name)
            if files_ok[name]:
                shutil.copy2(pack_dir / name, _LATEST / name)
        if kit_src.is_dir():
            dest = pack_dir / "kit"
            shutil.copytree(kit_src, dest, dirs_exist_ok=True)
            shutil.copytree(kit_src, _LATEST / "kit", dirs_exist_ok=True)
            files_ok["kit/"] = True
        else:
            files_ok["kit/"] = False

        how = (
            "# How to run (engineer soft release)\n\n"
            "1. From this `ha-production-gate` clone:\n"
            "   Unix: `./scripts/bootstrap.sh`\n"
            "   Windows: `.\\scripts\\bootstrap.ps1`\n"
            "2. Or: build the five Rust bins (see README), `pip install -e .`, then `ha-production-gate`\n"
            "3. Expect `PRODUCTION_GATE_RITUAL_PASS` and read PRODUCTION_GATE_BOARD.md\n\n"
            "Honesty: soft teaching Dual · not MEASURED · soft≠OTP · "
            "Rust physics oracle · Python glue only.\n"
        )
        (pack_dir / "HOW_TO_RUN.md").write_text(how, encoding="utf-8")
        shutil.copy2(pack_dir / "HOW_TO_RUN.md", _LATEST / "HOW_TO_RUN.md")
        files_ok["HOW_TO_RUN.md"] = True

        manifest = {
            "schema": SCHEMA,
            "proof_tier": PROOF_TIER,
            "timestamp_utc": _now(),
            "gate_verdict": gate.get("verdict"),
            "gate_ok": bool(gate.get("ok")),
            "files": files_ok,
            "pack_dir": str(pack_dir),
            "latest": str(_LATEST),
            "honesty": {
                "not_measured": True,
                "not_product_ready": True,
                "soft_release": True,
                "epsilon": ["ε_desk_not_world", "ε_no_external_engineer_yet"],
            },
            "tabu": ["MEASURED", "OTP", "product_ready", "soft_mint", "vault paths"],
        }
        (pack_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(pack_dir / "MANIFEST.json", _LATEST / "MANIFEST.json")
        (_OUT_ROOT / "RELEASE_ENGINEER_LATEST_v1.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    else:
        manifest = {
            "schema": SCHEMA,
            "ok": bool(gate.get("ok")),
            "gate_verdict": gate.get("verdict"),
        }

    ok = bool(gate.get("ok")) and (not write or all(files_ok.values()))
    manifest["ok"] = ok
    manifest["verdict"] = f"{PROOF_TIER}_PASS" if ok else f"{PROOF_TIER}_FAIL"
    print(f"release pack: {_LATEST if write else '(dry)'}")
    print(f"  gate: {gate.get('verdict')}")
    print(f"  verdict: {manifest['verdict']}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage soft-release engineer pack")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    doc = build_release_engineer_pack(write=not args.no_write)
    print(json.dumps({"ok": doc.get("ok"), "verdict": doc.get("verdict")}, indent=2))
    return 0 if doc.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
