"""Bekker pressure–sinkage terramech grounded in ON (Wong / Bekker corpus).

Equation (classic Bekker, Wong §2.4.1 — VPS ON OCR):
  p = (kc/b + k_phi) * z^n
  z = (p / (kc/b + k_phi)) ** (1/n)

Shear / drawbar (Wong Janosi–Hanamoto):
  τ = (c + p tanφ)(1 − e^{−j/K})
  H = τ · A

Oracle: Rust `ha-physics-gate bekker-eval` (Python is glue only).

ON sources live on VPS under data/gate_corpus/moon-world/... (gate-moon-study).

TABU: MEASURED field bevameter · product_ready · lunar flight claim · Python as oracle.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_SOILS = _REPO / "fixtures" / "open_registry" / "terramech" / "bekker_soils_on_v1.json"
_BIN_STEM = "ha-physics-gate"
# Process-wide catalog for owned Dual runs (embeds call physics_row_for_dual without catalog=).
_CATALOG_OVERRIDE: Path | None = None

PROOF_TIER = "TERRAMECH_BEKKER_ON_SLICE"
ORACLE = "ha_physics_gate_bekker"
# Dual oracle surface — ingress heuristic is NOT on this list.
ORACLE_SURFACE_KEYS = frozenset(
    {
        "oracle",
        "soil_id",
        "sinkage_mm",
        "sinkage_risk",
        "traverse_feasible",
        "compaction_resistance_n",
        "shear_tau_kpa",
        "drawbar_pull_n",
        "bekker",
        "g_mps2",
        "ground_pressure_kpa",
        "contact_width_b_m",
        "contact_area_m2",
    }
)


def _exe_name() -> str:
    return _BIN_STEM + (".exe" if sys.platform == "win32" else "")


def find_ha_physics_gate_bin() -> Path:
    env = (os.environ.get("HA_PHYSICS_GATE_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(f"HA_PHYSICS_GATE_BIN set but not a file: {p}")
        return p.resolve()
    name = _exe_name()
    for candidate in (
        _REPO / "target" / "release" / name,
        _REPO / "target" / "debug" / name,
    ):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "ha-physics-gate binary missing — set HA_PHYSICS_GATE_BIN or "
        "cargo build -p ha_physics_gate --release "
        "(no pure-Python Bekker oracle)"
    )


def set_bekker_catalog_override(path: Path | None) -> Path | None:
    """Set/clear process catalog override. Returns previous path."""
    global _CATALOG_OVERRIDE
    prev = _CATALOG_OVERRIDE
    _CATALOG_OVERRIDE = path.resolve() if path is not None else None
    return prev


def active_bekker_catalog() -> Path:
    return _CATALOG_OVERRIDE or _SOILS


def load_bekker_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or active_bekker_catalog()
    return json.loads(p.read_text(encoding="utf-8"))


def evaluate_soil(
    soil_id: str,
    *,
    catalog: dict[str, Any] | Path | None = None,
    ground_pressure_kpa: float | None = None,
    contact_width_b_m: float | None = None,
    contact_area_m2: float | None = None,
) -> dict[str, Any]:
    """Rust Bekker eval — catalog path preferred; inline dict written to temp if needed."""
    import tempfile

    bin_path = find_ha_physics_gate_bin()
    if isinstance(catalog, Path):
        catalog_path = catalog
        tmp: Path | None = None
    elif isinstance(catalog, dict):
        tmp_f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        tmp_f.write(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
        tmp_f.close()
        catalog_path = Path(tmp_f.name)
        tmp = catalog_path
    else:
        catalog_path = active_bekker_catalog()
        tmp = None

    args = [
        str(bin_path),
        "bekker-eval",
        f"--catalog={catalog_path}",
        f"--soil-id={soil_id}",
    ]
    if ground_pressure_kpa is not None:
        args.append(f"--p-kpa={float(ground_pressure_kpa)}")
    if contact_width_b_m is not None:
        args.append(f"--b-m={float(contact_width_b_m)}")
    if contact_area_m2 is not None:
        args.append(f"--area-m2={float(contact_area_m2)}")
    try:
        from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

        proc = subprocess.run(
            args,
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            timeout=60.0,
            check=False,
            **hidden_run_kwargs(),
        )
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-physics-gate bekker-eval FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("schema") != "ha_bekker_soil_eval_v1":
        raise RuntimeError("bad bekker eval schema from Rust oracle")
    if doc.get("oracle") != ORACLE:
        raise RuntimeError("bekker eval missing Rust oracle id")
    return doc


def evaluate_pressure_from_z(
    soil_id: str,
    z_m: float,
    *,
    contact_width_b_m: float | None = None,
    catalog: Path | None = None,
) -> dict[str, Any]:
    """Rust Bekker p(z) — inverse of evaluate_soil z(p)."""
    bin_path = find_ha_physics_gate_bin()
    catalog_path = catalog or active_bekker_catalog()
    args = [
        str(bin_path),
        "bekker-from-z",
        f"--catalog={catalog_path}",
        f"--soil-id={soil_id}",
        f"--z-m={float(z_m)}",
    ]
    if contact_width_b_m is not None:
        args.append(f"--b-m={float(contact_width_b_m)}")
    from production_gate.win_hidden_subprocess_v1 import hidden_run_kwargs

    proc = subprocess.run(
        args,
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=60.0,
        check=False,
        **hidden_run_kwargs(),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-physics-gate bekker-from-z FAIL: {err}")
    doc = json.loads(proc.stdout)
    if doc.get("oracle") != ORACLE:
        raise RuntimeError("bekker-from-z missing Rust oracle id")
    return doc


def physics_row_for_dual(
    soil_id: str,
    *,
    g_mps2: float = 9.81,
    ground_pressure_kpa: float | None = None,
    contact_width_b_m: float | None = None,
    contact_area_m2: float | None = None,
    catalog: dict[str, Any] | Path | None = None,
) -> dict[str, Any]:
    """Shape expected by Newton-X Dual probe — Bekker + shear + drawbar from Rust."""
    ev = evaluate_soil(
        soil_id,
        catalog=catalog,
        ground_pressure_kpa=ground_pressure_kpa,
        contact_width_b_m=contact_width_b_m,
        contact_area_m2=contact_area_m2,
    )
    # Quarantined heuristic — NOT Bekker / NOT Wong / NOT on oracle surface.
    ingress_heuristic = {
        "schema": "ingress_disturbance_heuristic_v0",
        "ingress_disturbance_mult": 2.15 if ev["sinkage_risk"] else 1.05,
        "honesty": {
            "not_bekker": True,
            "not_wong": True,
            "not_measured": True,
            "magic_constant": True,
            "quarantined_from_oracle_surface": True,
            "note": "compat sidecar for material/wear lanes — never cite as terramech oracle",
        },
    }
    shear = ev.get("shear") if isinstance(ev.get("shear"), dict) else None
    drawbar = ev.get("drawbar_pull_n")
    if drawbar is None and shear:
        drawbar = shear.get("drawbar_pull_n")
    out = {
        "traverse_feasible": bool(ev["traverse_feasible"]),
        "sinkage_risk": bool(ev["sinkage_risk"]),
        "sinkage_mm": float(ev["sinkage_mm"]),
        "compaction_resistance_n": float(ev.get("compaction_resistance_n") or 0.0),
        "oracle": ORACLE,
        "g_mps2": g_mps2,
        "soil_id": soil_id,
        "bekker": ev,
        "source": "ON:Wong/Bekker · Rust ha-physics-gate bekker-eval · fixtures/.../bekker_soils_on_v1.json",
        "honesty": {
            "bekker_from_rust": True,
            "ingress_is_heuristic_not_bekker": True,
            "ingress_quarantined_from_oracle": True,
            "shear_from_rust": bool(shear and shear.get("model") == "janosi_hanamoto"),
            "drawbar_from_rust": drawbar is not None,
            "no_magic_sinkage_mm": True,
            "oracle_surface_keys": sorted(ORACLE_SURFACE_KEYS),
        },
        # Compat only — consumers of wear/material must read heuristic honesty.
        "ingress_disturbance_mult": float(ingress_heuristic["ingress_disturbance_mult"]),
        "ingress_disturbance_heuristic": ingress_heuristic,
    }
    if shear and shear.get("model") == "janosi_hanamoto":
        out["shear"] = shear
        out["shear_tau_kpa"] = float(shear.get("tau_kpa") or 0.0)
        out["shear_model"] = "janosi_hanamoto"
    if drawbar is not None:
        out["drawbar_pull_n"] = float(drawbar)
        out["drawbar_model"] = "janosi_hanamoto_H_eq_tau_A"
    if ground_pressure_kpa is not None:
        out["ground_pressure_kpa"] = float(ground_pressure_kpa)
    if contact_width_b_m is not None:
        out["contact_width_b_m"] = float(contact_width_b_m)
    if contact_area_m2 is not None:
        out["contact_area_m2"] = float(contact_area_m2)
    elif isinstance(ev.get("params"), dict) and ev["params"].get("contact_area_m2") is not None:
        out["contact_area_m2"] = float(ev["params"]["contact_area_m2"])
    return out


def safe_bekker_physics() -> dict[str, Any]:
    return physics_row_for_dual("firm_lab")


def hostile_bekker_physics() -> dict[str, Any]:
    return physics_row_for_dual("soft_hostile")


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Bekker ON terramech — Rust oracle glue")
    ap.add_argument("--soil-id", default="firm_lab")
    ap.add_argument("--catalog", type=Path, default=_SOILS)
    args = ap.parse_args(argv)
    doc = evaluate_soil(args.soil_id, catalog=args.catalog)
    print(json.dumps(doc, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
