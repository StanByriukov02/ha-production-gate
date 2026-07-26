#!/usr/bin/env python3
"""JSON stdin/stdout Verilator MMIO session for Rust clifford_device — iron crown H3."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def run_verilator_mmio_request(req: dict) -> dict:
    from scripts.chip.clifford_verilator_mmio_build_v0 import verilator_mmio_exe

    exe = verilator_mmio_exe()
    if exe is None:
        return {"error": "verilator_mmio_session_missing"}
    proc = subprocess.run(
        [str(exe)],
        input=json.dumps(req),
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(_REPO),
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-400:]
        return {"error": f"verilator_mmio_fail: {tail}"}
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"error": f"bad_json: {(proc.stdout or '')[-200:]}"}


def main() -> int:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    req = json.loads(sys.stdin.read())
    out = run_verilator_mmio_request(req)
    sys.stdout.write(json.dumps(out))
    return 0 if "rd_hex" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
