"""CIRCT emit + netlist diff vs hand SV (T4.3–T4.5)."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_PIN = _REPO / "toolchain" / "CIRCT_PIN_v1.json"
_MLIR = _REPO / "mlir" / "clifford" / "lower" / "geo_prod_cayley_hw.mlir"
_HAND = _REPO / "fixtures" / "chip" / "clifford_geo_prod_v0.v"
_EMIT = _REPO / "fixtures" / "chip" / "clifford_geo_prod_circt_emit_v0.sv"


def _load_pin() -> dict[str, Any]:
    return json.loads(_PIN.read_text(encoding="utf-8"))


def _ssh_cmd(pin: dict[str, Any], remote_script: str) -> tuple[int, str, str]:
    vps = pin["vps"]
    key = Path(vps["key"])
    host = vps["host"]
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-i", str(key), host, remote_script],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _extract_verilog(circt_out: str) -> str:
    lines: list[str] = []
    in_mod = False
    for line in circt_out.splitlines():
        if line.startswith("module ") and "{" not in line:
            in_mod = True
        if in_mod:
            lines.append(line)
            if line.strip() == "endmodule":
                break
    return "\n".join(lines) + "\n"


def run_circt_emit(*, write: bool = True) -> dict[str, Any]:
    from scripts.chip.gen_clifford_geo_prod_circt_mlir_v1 import main as gen_mlir

    gen_mlir()
    pin = _load_pin()
    circt_opt = pin["vps"]["circt_opt"]
    mlir_remote = "/tmp/clifford_geo_prod_cayley_hw.mlir"
    key = str(Path(pin["vps"]["key"]))
    host = pin["vps"]["host"]
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", "-i", key, str(_MLIR), f"{host}:{mlir_remote}"],
        check=True,
        timeout=120,
    )
    upload = f"{circt_opt} {mlir_remote} --export-verilog 2>/dev/null"
    rc, out, err = _ssh_cmd(pin, upload)
    verilog = _extract_verilog(out) if rc == 0 else ""

    if write and verilog:
        _EMIT.write_text(verilog, encoding="utf-8")

    return {
        "emit_id": "clifford_circt_emit_v1",
        "verdict": "EMIT_PASS" if rc == 0 and verilog else "EMIT_FAIL",
        "circt_opt_rc": rc,
        "emit_path": str(_EMIT.relative_to(_REPO)).replace("\\", "/") if verilog else "",
        "mlir_path": str(_MLIR.relative_to(_REPO)).replace("\\", "/"),
        "firtool": pin["firtool_version"],
        "stderr_tail": err[-400:],
        "verilog_lines": len(verilog.splitlines()) if verilog else 0,
    }


def _count_muls_sv(text: str) -> int:
    if "blade_real_" in text:
        return len(re.findall(r"blade_real_\d+\([^)]+\)\s*\*\s*blade_real_\d+\([^)]+\)", text))
    return text.count("*")


def _yosys_stat_vps(path: Path, pin: dict[str, Any]) -> dict[str, Any]:
    remote_dir = "/tmp/clifford_yosys_diff"
    key = str(Path(pin["vps"]["key"]))
    host = pin["vps"]["host"]
    remote_path = f"{remote_dir}/{path.name}"
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-i", key, host, f"mkdir -p {remote_dir}"],
        check=True,
        timeout=60,
    )
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", "-i", key, str(path), f"{host}:{remote_path}"],
        check=True,
        timeout=120,
    )
    script = f"cd {remote_dir} && yosys -p 'read_verilog -sv {path.name}; stat' 2>&1"
    rc, out, _ = _ssh_cmd(pin, script)
    if rc != 0:
        return {"host": "vps_fallback", "cells": None, "mul_cells": None, "status": "FAIL"}
    cells_m = re.search(r"Number of cells:\s+(\d+)", out)
    mul_m = re.search(r"\$mul\s+(\d+)", out)
    return {
        "host": "vps_fallback",
        "status": "PASS" if cells_m else "FAIL",
        "cells": int(cells_m.group(1)) if cells_m else None,
        "mul_cells": int(mul_m.group(1)) if mul_m else None,
    }


def _yosys_stat(path: Path, pin: dict[str, Any]) -> dict[str, Any]:
    from scripts.chip.clifford_msys_toolchain_v1 import msys_available, run_yosys_stat

    if msys_available():
        local = run_yosys_stat(path, cwd=_REPO)
        if local.get("status") == "PASS":
            local["host"] = "local_msys"
            return local
    return _yosys_stat_vps(path, pin)


def run_netlist_diff(*, write: bool = False) -> dict[str, Any]:
    pin = _load_pin()
    emit_path = _EMIT
    if not emit_path.is_file():
        run_circt_emit(write=True)
    hand = _HAND.read_text(encoding="utf-8")
    emit = emit_path.read_text(encoding="utf-8")
    from scripts.chip.clifford_cayley_graph_v1 import count_rtl_gp_mul_terms

    hand_mul = count_rtl_gp_mul_terms(_HAND)["rtl_mul_terms"]
    emit_mul = _count_muls_sv(emit)
    hand_stat: dict[str, Any] = {"host": "regex_only", "mul_cells": hand_mul, "cells": None}
    emit_stat = _yosys_stat(emit_path, pin)
    yosys_host = emit_stat.get("host", "unknown")

    checks = [
        {"id": "emit_file_present", "pass": emit_path.is_file()},
        {"id": "hand_mul_terms_64", "pass": hand_mul == 64, "detail": str(hand_mul)},
        {"id": "emit_mul_terms_64", "pass": emit_mul >= 64, "detail": str(emit_mul)},
        {
            "id": "yosys_emit_mul_cells_64",
            "pass": emit_stat.get("mul_cells") == 64,
            "detail": str(emit_stat.get("mul_cells")),
        },
        {
            "id": "yosys_emit_cells",
            "pass": (emit_stat.get("cells") or 0) > 0,
            "detail": str(emit_stat.get("cells")),
        },
    ]
    verdict = "NETLIST_DIFF_PASS" if all(c["pass"] for c in checks) else "NETLIST_DIFF_FAIL"

    doc = {
        "diff_id": "clifford_netlist_diff_v1",
        "verdict": verdict,
        "yosys_host": yosys_host,
        "hand_rtl": {"path": str(_HAND.name), "mul_terms": hand_mul, "yosys": hand_stat},
        "circt_emit": {"path": str(_EMIT.name), "mul_terms": emit_mul, "yosys": emit_stat},
        "checks": checks,
        "honesty": {
            "functional_bf16_match": False,
            "structural_emit_diff": True,
            "hand_sv_crown": True,
        },
    }
    if write:
        out = _REPO / "fixtures" / "chip" / "clifford_netlist_diff_v1.json"
        out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def run_cayley_regen_diff() -> dict[str, Any]:
    from scripts.chip.gen_clifford_geo_prod_v0_sv import main as regen

    before = _HAND.read_text(encoding="utf-8")
    regen()
    after = _HAND.read_text(encoding="utf-8")
    identical = before == after
    if not identical:
        _HAND.write_text(before, encoding="utf-8")
    return {
        "verdict": "REGEN_IDENTICAL" if identical else "REGEN_DRIFT",
        "bytes": len(before),
    }
