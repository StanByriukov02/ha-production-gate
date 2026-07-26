"""Lunar plateau factory batch — run signoffs + pytest (loop/automation entry).

Usage:
  python scripts/chip/run_lunar_plateau_factory_batch_v1.py
  python scripts/chip/run_lunar_plateau_factory_batch_v1.py --write
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _run_signoffs(*, write: bool) -> list[dict]:
    import os

    os.chdir(_REPO)
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))

    from dogfood_platform.chip_material_factory_dual_wear_closure_v1 import (
        run_chip_material_factory_dual_wear_closure,
    )
    from dogfood_platform.chip_material_factory_learning_loop_v1 import (
        run_chip_material_factory_learning_loop,
    )
    from dogfood_platform.chip_plateau_g_mapped_structural_factory_signoff_v1 import (
        run_plateau_g_mapped_structural_signoff,
    )
    from dogfood_platform.chip_plateau_h_compute_carrier_factory_signoff_v1 import (
        run_plateau_h_compute_carrier_signoff,
    )
    from dogfood_platform.chip_plateau_i_isru_o2_stub_factory_signoff_v1 import (
        run_plateau_i_isru_o2_stub_signoff,
    )
    from dogfood_platform.dogfood_mission_day_compose_v1 import run_mission_day_compose
    from dogfood_platform.dogfood_mission_sustained_work_loop_v1 import run_mission_sustained_work_loop
    from dogfood_platform.dogfood_spine_smoke_fast_v1 import run_dogfood_spine_smoke_fast

    results = [
        ("material_learning_loop", run_chip_material_factory_learning_loop(write=write)),
        ("material_dual_wear_closure", run_chip_material_factory_dual_wear_closure(write=write)),
        ("plateau_g", run_plateau_g_mapped_structural_signoff(write=write, run_iron=True)),
        ("plateau_h", run_plateau_h_compute_carrier_signoff(write=write, run_iron=True)),
        ("plateau_i", run_plateau_i_isru_o2_stub_signoff(write=write, run_iron=True)),
        ("mission_day_compose", run_mission_day_compose(write=write, run_live=False)),
        ("sustained_work_loop", run_mission_sustained_work_loop(write=write, run_live_ticks=False)),
        ("spine_smoke_fast", run_dogfood_spine_smoke_fast(write=write)),
    ]
    return [{"name": n, "verdict": r["verdict"]} for n, r in results]


def main() -> int:
    write = "--write" in sys.argv
    signoffs = _run_signoffs(write=write)
    fail_signoffs = [s for s in signoffs if not str(s["verdict"]).endswith("PASS")]

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_chip_plateau_g_mapped_structural_v1.py",
            "tests/test_chip_plateau_h_compute_carrier_v1.py",
            "tests/test_chip_plateau_i_isru_o2_stub_v1.py",
            "tests/test_chip_material_factory_learning_loop_v1.py",
            "tests/test_chip_material_factory_dual_wear_closure_v1.py",
            "tests/test_dogfood_mission_day_compose_v1.py",
            "tests/test_dogfood_mission_sustained_work_loop_v1.py",
            "tests/test_dogfood_spine_smoke_fast_v1.py",
            "-q",
            "--timeout=360",
        ],
        cwd=str(_REPO),
        env={**dict(__import__("os").environ), "PYTHONPATH": str(_REPO)},
        capture_output=True,
        text=True,
    )

    summary = {
        "signoffs": signoffs,
        "signoff_fail": fail_signoffs,
        "pytest_exit": proc.returncode,
        "pytest_tail": (proc.stdout or "")[-800:],
    }
    print(json.dumps(summary, indent=2))
    return 0 if not fail_signoffs and proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
