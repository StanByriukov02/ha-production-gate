"""P5.21 — yosys area probe (sandwich ex_pipe · dual vs sim-only vs synth-only)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_STA = _CHIP / "sta"

_MODES = {
    "dual": _REPO / "scripts" / "chip" / "clifford_area_sandwich_probe_dual_v0.ys",
    "sim_only": _REPO / "scripts" / "chip" / "clifford_area_sandwich_probe_sim_v0.ys",
    "synth_only": _REPO / "scripts" / "chip" / "clifford_area_sandwich_probe_synth_v0.ys",
}

_MSYS_BIN = Path(r"C:\msys64") / "mingw64" / "bin"


def _mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{_MSYS_BIN};{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(_REPO)
    return env


def _yosys_path() -> str | None:
    for name in ("yosys", "yosys.exe"):
        p = shutil.which(name) or (_MSYS_BIN / name if (_MSYS_BIN / name).is_file() else None)
        if p:
            return str(p)
    return None


def _parse_stat_cells(out: str) -> int:
    matches = [int(m) for m in re.findall(r"^\s+(\d+)\s+cells\s*$", out, re.MULTILINE)]
    return max(matches) if matches else 0


def _run_mode(mode: str, ys: Path) -> dict[str, Any]:
    yosys = _yosys_path()
    if not yosys:
        return {"status": "SKIPPED", "mode": mode, "reason": "yosys missing"}
    try:
        proc = subprocess.run(
            [yosys, str(ys)],
            cwd=str(_REPO),
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
            env=_mingw_env(),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        cells = _parse_stat_cells(out)
        return {
            "status": "PASS" if cells > 0 else "FAIL",
            "mode": mode,
            "cells": cells,
            "stdout_tail": out[-500:],
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        tail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            tail = (exc.stdout or exc.stderr or str(exc))[-600:]
        return {"status": "FAIL", "mode": mode, "reason": tail[-300:]}


def run_clifford_alu_area_probe() -> dict[str, Any]:
    results = {mode: _run_mode(mode, ys) for mode, ys in _MODES.items()}
    dual = results.get("dual", {}).get("cells", 0) or 0
    sim = results.get("sim_only", {}).get("cells", 0) or 0
    syn = results.get("synth_only", {}).get("cells", 0) or 0

    ratio_sim = round(sim / dual, 4) if dual > 0 and sim > 0 else None
    ratio_synth = round(syn / dual, 4) if dual > 0 and syn > 0 else None

    all_ok = all(r.get("status") == "PASS" for r in results.values())
    gated_ok = all_ok and dual > 0 and sim > 0 and syn > 0 and sim < dual and syn < dual

    report: dict[str, Any] = {
        "verdict": "AREA_PROBE_PASS" if gated_ok else "AREA_PROBE_FAIL",
        "probe_top": "clifford_area_sandwich_probe_top_v0",
        "modes": results,
        "cells": {"dual": dual, "sim_only": sim, "synth_only": syn},
        "ratios_vs_dual": {"sim_only": ratio_sim, "synth_only": ratio_synth},
        "honesty": {
            "scope": "yosys synth stat on sandwich ex_pipe — elaboration gate honesty",
            "not_pd_area": True,
            "not_timing_signoff": True,
            "dual_elaboration_penalty": dual > 0 and sim < dual and syn < dual,
        },
    }

    _STA.mkdir(parents=True, exist_ok=True)
    (_STA / "clifford_alu_area_probe_report_v0.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run_clifford_alu_area_probe(), indent=2))
