"""Non-interactive OpenSTA build + Clifford STA smoke + receipt refresh."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_BASH = Path(r"C:\msys64\usr\bin\bash.exe")
_BUILD_SH = _REPO / "scripts" / "chip" / "build_opensta_msys2_v0.sh"
_STA_BIN = _REPO / "tools" / "opensta" / "bin" / "sta.exe"
_RECEIPT_P59 = _CHIP / "CHIP_CLIFFORD_ALU_P5_9_RECEIPT_v1.json"
_RECEIPT_P511 = _CHIP / "CHIP_CLIFFORD_ALU_P5_11_RECEIPT_v1.json"


def _run_build() -> dict:
    if not _BASH.is_file():
        return {"status": "SKIPPED", "reason": "msys bash missing"}
    env = os.environ.copy()
    env["MSYSTEM"] = "MINGW64"
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        proc = subprocess.run(
            [str(_BASH), "-lc", f"cd '{_REPO.as_posix()}' && bash scripts/chip/build_opensta_msys2_v0.sh"],
            capture_output=True,
            text=True,
            timeout=3600,
            env=env,
        )
        tail = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0 and _STA_BIN.is_file()
        return {
            "status": "PASS" if ok else "FAIL",
            "exit_code": proc.returncode,
            "sta_exe": str(_STA_BIN) if _STA_BIN.is_file() else "",
            "stdout_tail": tail[-1200:],
        }
    except subprocess.TimeoutExpired:
        return {"status": "FAIL", "reason": "build timeout 1h"}


def _run_smoke() -> dict:
    sys.path.insert(0, str(_REPO))
    from scripts.chip.run_clifford_alu_opensta_smoke_v0 import run_clifford_alu_opensta_smoke

    return run_clifford_alu_opensta_smoke()


def _patch_receipts(build: dict, smoke: dict) -> None:
    opensta_cli = smoke.get("opensta_cli", {})
    patch = {
        "opensta_build": build,
        "opensta_cli_last": opensta_cli,
        "opensta_run": bool(opensta_cli.get("opensta_run")),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    for path in (_RECEIPT_P59, _RECEIPT_P511):
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "sta_smoke" in data:
            data["sta_smoke"] = smoke
            data["sta_smoke"]["honesty"]["opensta_run"] = bool(opensta_cli.get("opensta_run"))
        if "opensta_build" in data:
            data["opensta_build"] = build
        data["opensta_automation"] = patch
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    build = _run_build()
    smoke = _run_smoke()
    _patch_receipts(build, smoke)
    print(json.dumps({"build": build, "smoke": smoke}, indent=2))
    ok = build.get("status") == "PASS" and smoke.get("opensta_cli", {}).get("status") == "PASS"
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
