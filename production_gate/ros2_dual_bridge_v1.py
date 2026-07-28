"""T5 thin ros2 bridge — robot_description / URDF path → Dual socket.

Does not require rclpy. Optional ROS2 node lives in ros2/ha_dual_ros2.
Honesty: soft teaching Dual · not MEASURED · not full Gazebo stack.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_OUT = _REPO / "results" / "runtime" / "platform_loop"
_RECEIPT = _OUT / "HA_DUAL_ROS2_LATEST_v1.json"
_BOARD = _OUT / "HA_DUAL_ROS2_BOARD_LATEST.md"

SCHEMA = "ha_dual_ros2_v1"
PROOF_TIER = "HA_DUAL_ROS2_SLICE"
CELL_ID = "ros2_dual_bridge_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _console(text: str) -> None:
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write((text + "\n").encode(enc, errors="replace"))
        sys.stdout.buffer.flush()


def materialize_robot_description(
    *,
    urdf_path: str | Path | None = None,
    robot_description: str | None = None,
    scratch_dir: Path | None = None,
) -> Path:
    """Resolve either a URDF file path or inline robot_description XML to a file."""
    if urdf_path and robot_description:
        raise ValueError("pass urdf_path XOR robot_description, not both")
    if not urdf_path and not robot_description:
        raise ValueError("pass urdf_path or robot_description XML")

    if urdf_path:
        src = Path(urdf_path).expanduser().resolve()
        if not src.is_file():
            raise FileNotFoundError(f"urdf not found: {src}")
        return src

    xml = str(robot_description or "").strip()
    if not xml:
        raise ValueError("robot_description is empty")
    if "<robot" not in xml.lower():
        raise ValueError("robot_description must be URDF XML containing <robot …>")

    root = scratch_dir or (_REPO / "results" / "runtime" / "ros2_robot_description")
    root.mkdir(parents=True, exist_ok=True)
    dest = root / "robot_description.urdf"
    dest.write_text(xml + ("" if xml.endswith("\n") else "\n"), encoding="utf-8")
    return dest


def run_dual_from_robot_description(
    *,
    urdf_path: str | Path | None = None,
    robot_description: str | None = None,
    soils: str | Path | None = None,
    root_link: str = "base_link",
    ee_link: str | None = None,
    model_kind: str = "wheeled_base",
    world_id: str | None = None,
    write_receipt: bool = True,
    source_label: str = "cli",
) -> dict[str, Any]:
    """Thin wrapper: robot_description|urdf → production_gate dual_socket."""
    from production_gate.dual_socket_v1 import run_dual_socket

    with tempfile.TemporaryDirectory(prefix="ha_dual_ros2_") as td:
        urdf = materialize_robot_description(
            urdf_path=urdf_path,
            robot_description=robot_description,
            scratch_dir=Path(td) if robot_description else None,
        )
        # If XML was written into td, copy to durable scratch so dual_socket staging works
        if robot_description:
            durable = _REPO / "results" / "runtime" / "ros2_robot_description"
            durable.mkdir(parents=True, exist_ok=True)
            durable_urdf = durable / "robot_description.urdf"
            durable_urdf.write_text(urdf.read_text(encoding="utf-8"), encoding="utf-8")
            urdf = durable_urdf

        dual = run_dual_socket(
            urdf=urdf,
            soils=soils,
            root_link=root_link,
            ee_link=ee_link,
            model_kind=model_kind,
            world_id=world_id,
            write_receipt=write_receipt,
        )

    mode = "robot_description_xml" if robot_description else "urdf_path"
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "proof_tier": PROOF_TIER,
        "cell_id": CELL_ID,
        "timestamp_utc": _now(),
        "verdict": (
            "HA_DUAL_ROS2_PASS"
            if dual.get("verdict") == "DUAL_SOCKET_PASS"
            else "HA_DUAL_ROS2_FAIL"
        ),
        "source": {
            "label": source_label,
            "mode": mode,
            "urdf_path": None if robot_description else str(urdf_path),
            "robot_description_chars": len(robot_description or ""),
            "soils": str(soils) if soils else None,
            "root_link": root_link,
            "model_kind": model_kind,
        },
        "dual_socket": {
            "verdict": dual.get("verdict"),
            "contact": dual.get("contact"),
            "soils": dual.get("soils"),
            "safe": dual.get("safe"),
            "hostile": dual.get("hostile"),
            "dual_ok": dual.get("dual_ok"),
            "body": dual.get("body"),
            "receipt_path": dual.get("receipt_path"),
            "board_path": dual.get("board_path"),
        },
        "honesty": {
            "thin_ros2_wrapper": True,
            "not_full_gazebo_stack": True,
            "not_measured": True,
            "not_discourse": True,
            "calls_dual_socket": True,
            "rclpy_optional": True,
            "product_task": "T5",
        },
        "ros2_package": "ros2/ha_dual_ros2",
    }

    if write_receipt:
        _OUT.mkdir(parents=True, exist_ok=True)
        _RECEIPT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        contact = (dual.get("contact") or {})
        safe = dual.get("safe") or {}
        hostile = dual.get("hostile") or {}
        board = f"""# HA Dual ros2 board (T5)

**Verdict:** `{doc["verdict"]}`  
**Dual socket:** `{dual.get("verdict")}`  
**UTC:** {doc["timestamp_utc"]}  
**Source:** `{mode}` · `{source_label}`

## Contact

```json
{json.dumps(contact, indent=2)}
```

## Sinkage Dual

| Lane | soil | sinkage_mm | pass | allowed |
|------|------|------------|------|---------|
| Safe | {safe.get("soil_id")} | {safe.get("sinkage_mm")} | {safe.get("physics_pass")} | {safe.get("current_allowed")} |
| Hostile | {hostile.get("soil_id")} | {hostile.get("sinkage_mm")} | {hostile.get("physics_pass")} | {hostile.get("current_allowed")} |

## Honesty

thin ros2 wrapper · calls Dual on URDF / robot_description · not MEASURED · not full Gazebo
"""
        _BOARD.write_text(board + "\n", encoding="utf-8")
        doc["board_path"] = str(_BOARD)
        doc["receipt_path"] = str(_RECEIPT)

    return doc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ha-dual-ros2",
        description="T5 thin ros2 bridge: URDF path or robot_description XML → Dual",
    )
    p.add_argument("--urdf", type=str, default=None, help="Path to URDF")
    p.add_argument(
        "--robot-description",
        type=str,
        default=None,
        help="Inline URDF XML (same as ROS robot_description)",
    )
    p.add_argument(
        "--robot-description-file",
        type=str,
        default=None,
        help="File whose contents are robot_description XML",
    )
    p.add_argument("--soils", type=str, default=None)
    p.add_argument("--root-link", default="base_link")
    p.add_argument("--ee-link", default=None)
    p.add_argument("--kind", dest="model_kind", default="wheeled_base")
    p.add_argument("--world-id", default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    xml = args.robot_description
    if args.robot_description_file:
        xml = Path(args.robot_description_file).expanduser().resolve().read_text(
            encoding="utf-8"
        )

    try:
        doc = run_dual_from_robot_description(
            urdf_path=args.urdf,
            robot_description=xml,
            soils=args.soils,
            root_link=args.root_link,
            ee_link=args.ee_link,
            model_kind=args.model_kind,
            world_id=args.world_id,
            source_label="ha-dual-ros2-cli",
        )
    except Exception as exc:  # noqa: BLE001 — CLI surface
        _console(f"HA_DUAL_ROS2_ERROR: {exc}")
        return 2

    if args.json:
        _console(json.dumps(doc, indent=2))
    else:
        dual = doc.get("dual_socket") or {}
        contact = dual.get("contact") or {}
        _console(
            "\n".join(
                [
                    "",
                    "════════════════════════════════════════",
                    "  HA DUAL ROS2 (T5) — thin wrapper",
                    "════════════════════════════════════════",
                    f"  verdict: {doc.get('verdict')}",
                    f"  dual:    {dual.get('verdict')}",
                    f"  mode:    {(doc.get('source') or {}).get('mode')}",
                    f"  contact: src={contact.get('source')} mass={contact.get('mass_kg')}",
                    f"  board:   {doc.get('board_path')}",
                    "════════════════════════════════════════",
                    "",
                ]
            )
        )
    return 0 if doc.get("verdict") == "HA_DUAL_ROS2_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
