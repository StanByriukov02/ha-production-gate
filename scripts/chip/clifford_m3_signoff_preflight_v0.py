"""M3 signoff preflight — structural ref cache + vectors hash (no iverilog)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_CHIP = _REPO / "results" / "platform_bpass" / "chip"
_CACHE = _CHIP / "clifford_structural_ref_ticks_v0.json"
_VEC = _REPO / "fixtures" / "chip" / "clifford_world_motion_vectors_v1.json"


def evaluate_m3_preflight(*, write: bool = False) -> dict[str, Any]:
    vec_hash = _VEC.stat().st_mtime_ns if _VEC.is_file() else 0
    cached_ticks = 0
    cache_ok = False
    if _CACHE.is_file():
        doc = json.loads(_CACHE.read_text(encoding="utf-8"))
        cached_ticks = len(doc.get("ticks") or [])
        cache_ok = doc.get("vectors_mtime_ns") == vec_hash and cached_ticks >= 50
    verdict = "M3_PREFLIGHT_PASS" if cache_ok else "M3_PREFLIGHT_WARN"
    out: dict[str, Any] = {
        "verdict": verdict,
        "structural_ref_cache": str(_CACHE.relative_to(_REPO)).replace("\\", "/"),
        "cached_ticks": cached_ticks,
        "vectors_hash_ns": vec_hash,
        "cache_vectors_match": cache_ok,
        "note": "M3 compares mapped_full_alu_mmio vs structural_synth_mmio (gp_synth=1)",
    }
    if write:
        path = _CHIP / "CHIP_CLIFFORD_M3_PREFLIGHT_RECEIPT_v1.json"
        path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(evaluate_m3_preflight(), indent=2))
    raise SystemExit(0)
