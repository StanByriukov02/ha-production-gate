"""LC2 host DRAM behavioral HIL — iverilog iron (L1) for DRAM_OFF_CHIP_GB sprint.

REPLACE: memory vendor signoff slice → txn log + effective Mbps + readback.
TABU: invent BOM GB · pytest without sim stdout.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_FIX = _REPO / "fixtures" / "chip"
_TXN_LOG = _CHIP / "CHIP_DRAM_HOST_HIL_TXN_LOG_v1.json"
_IRON_RECEIPT = _CHIP / "CHIP_DRAM_HOST_HIL_IRON_RECEIPT_v1.json"

_RTL = ("lc2_host_dram_behavioral_v0.v", "lc2_host_dram_hil_tb_v0.v")
_PASS = "TB_PASS"


def _parse_hil_summary(stdout: str) -> dict[str, Any]:
    m = re.search(
        r"HIL_SUMMARY bytes=(\d+) cycles=(\d+) eff_mbps=(\d+) peak_mbps=(\d+) txn=(\d+)",
        stdout,
    )
    if not m:
        return {}
    return {
        "bytes": int(m.group(1)),
        "cycles": int(m.group(2)),
        "eff_mbps": int(m.group(3)),
        "peak_mbps": int(m.group(4)),
        "txn_count": int(m.group(5)),
    }


def _parse_txn_log(stdout: str, *, limit: int = 32) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("TXN_LOG "):
            continue
        we = re.search(r"we=(\d+)", line)
        addr = re.search(r"addr=0x([0-9a-fA-F]+)", line)
        data = re.search(r"data=0x([0-9a-fA-F]+)", line)
        lat = re.search(r"lat=(\d+)", line)
        rows.append(
            {
                "we": int(we.group(1)) if we else None,
                "addr": addr.group(1) if addr else None,
                "data": data.group(1) if data else None,
                "lat": int(lat.group(1)) if lat else None,
            }
        )
    return rows[:limit]


def run_lc2_host_dram_hil(
    *,
    write: bool = True,
    quick: bool = False,
    transfer_bytes: int | None = None,
) -> dict[str, Any]:
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from dogfood_platform.chip_clifford_rtl_sim_v1 import sim_iverilog

    xfer = transfer_bytes or (4096 if quick else 51392)
    defines = (f"TRANSFER_BYTES={xfer}",)
    iron = sim_iverilog(
        "lc2_host_dram_hil_tb_v0",
        _RTL,
        _PASS,
        defines=defines,
        timeout=180 if quick else 300,
    )
    stdout = (iron.get("stdout_tail") or "") + str(iron.get("reason") or "")
    summary = _parse_hil_summary(stdout)
    txn_sample = _parse_txn_log(stdout)

    payload: dict[str, Any] = {
        "iron_id": "CHIP_DRAM_HOST_HIL_IRON_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": iron.get("backend"),
        "status": iron.get("status"),
        "transfer_bytes": xfer,
        "quick": quick,
        "hil_summary": summary,
        "txn_sample": txn_sample,
        "txn_sample_count": len(txn_sample),
        "rtl": [f"fixtures/chip/{r}" for r in _RTL],
        "replace": "memory vendor capacity/BW signoff slice → behavioral host DRAM HIL",
        "verdict": "DRAM_HOST_HIL_IRON_PASS" if iron.get("status") == "PASS" and summary else "DRAM_HOST_HIL_IRON_FAIL",
    }

    if write:
        _CHIP.mkdir(parents=True, exist_ok=True)
        _IRON_RECEIPT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _TXN_LOG.write_text(
            json.dumps(
                {
                    "log_id": "CHIP_DRAM_HOST_HIL_TXN_LOG_v1",
                    "timestamp_utc": payload["timestamp_utc"],
                    "summary": summary,
                    "txn_sample": txn_sample,
                    "full_txn_count": summary.get("txn_count"),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    return payload


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    doc = run_lc2_host_dram_hil(quick=quick)
    print(json.dumps({"verdict": doc["verdict"], "hil_summary": doc.get("hil_summary")}, indent=2))
    raise SystemExit(0 if doc["verdict"] == "DRAM_HOST_HIL_IRON_PASS" else 1)
