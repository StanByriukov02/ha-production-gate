"""Robot carrier sim runtime v1 — L5 · kernel + HAL + live state.

Run: python -m production_gate.robot_carrier_sim_runtime_v1 --carrier scout_A
TABU: claim full robot OS · MEASURED.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from typing import Any

from production_gate.fleet_live_state_v1 import DEFAULT_STATE, read_state, update_state
from production_gate.fleet_relay_plan_v1 import terminal_carrier
from production_gate.robot_os_hal_sim_v1 import attach_sim_hal_to_kernel
from production_gate.robot_os_kernel_v1 import PROOF_TIER, RobotOsKernel

_TICK_SLEEP_S = 0.04


def _tick_via_kernel(carrier_id: str, state: dict[str, Any]) -> dict[str, Any]:
    kernel = RobotOsKernel(carrier_id)
    radiation_enabled = bool((state.get("radiation_bind") or {}).get("enabled"))
    governance_enabled = bool((state.get("governance") or {}).get("enabled"))
    use_lunar_hal = (
        bool((state.get("lunar_hal") or {}).get("enabled"))
        or radiation_enabled
        or governance_enabled
    )
    if use_lunar_hal:
        from production_gate.robot_os_hal_lunar_profile_v1 import attach_lunar_hal_to_kernel

        attach_lunar_hal_to_kernel(kernel, state, radiation_enabled=radiation_enabled)
    else:
        attach_sim_hal_to_kernel(kernel, state)
    return kernel.tick_state(state)


def run_carrier_loop(
    carrier_id: str,
    *,
    state_path: Path,
    max_seconds: float = 25.0,
) -> int:
    t0 = time.monotonic()
    while time.monotonic() - t0 < max_seconds:
        state = read_state(state_path)
        coord = state["coordinator"]
        if coord.get("phase") in ("complete", "fail"):
            return 0 if coord.get("verdict") == "PASS" else 1

        c = state["carriers"].get(carrier_id)
        if not c:
            return 2

        terminal_id = coord.get("terminal_carrier_id") or terminal_carrier(
            str(state.get("profile_id", "lunar_crater_5km"))
        )

        if c.get("command") == "traverse" or c.get("phase") in ("armed", "traverse"):
            update_state(
                lambda s, cid=carrier_id: _tick_via_kernel(cid, s),
                path=state_path,
            )

        c = read_state(state_path)["carriers"][carrier_id]
        if carrier_id == terminal_id and c.get("phase") == "done":
            return 0

        if c.get("phase") == "relay":
            st = read_state(state_path)
            if st["coordinator"].get("phase") in ("complete", "fail"):
                return 0 if st["coordinator"].get("verdict") == "PASS" else 1
            time.sleep(_TICK_SLEEP_S)
            continue

        time.sleep(_TICK_SLEEP_S)
    return 3


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Robot carrier sim runtime v1")
    ap.add_argument("--carrier", required=True)
    ap.add_argument("--state", type=Path, default=DEFAULT_STATE)
    ap.add_argument("--max-seconds", type=float, default=25.0)
    args = ap.parse_args(argv)
    rc = run_carrier_loop(args.carrier, state_path=args.state, max_seconds=args.max_seconds)
    print(json.dumps({"carrier": args.carrier, "exit": rc, "proof_tier": PROOF_TIER}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
