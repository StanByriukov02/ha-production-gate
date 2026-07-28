"""CLI entry for ros2 run ha_dual_ros2 dual_from_description."""
from __future__ import annotations

import sys
from pathlib import Path


def _ensure_repo_on_path() -> None:
    """Allow running from source tree without installing ha-production-gate editable."""
    here = Path(__file__).resolve()
    # .../ros2/ha_dual_ros2/ha_dual_ros2/cli.py → repo root is parents[3]
    repo = here.parents[3]
    if (repo / "production_gate").is_dir():
        root = str(repo)
        if root not in sys.path:
            sys.path.insert(0, root)


def main(argv: list[str] | None = None) -> int:
    _ensure_repo_on_path()
    from production_gate.ros2_dual_bridge_v1 import main as bridge_main

    return bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
