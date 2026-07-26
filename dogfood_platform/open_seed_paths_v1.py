"""Resolve open-seed paths for materials (lean earth lab) before moon platform_bpass.

Order: HA_* env override → fixtures/open_seed → legacy moon / corpus paths.
"""
from __future__ import annotations

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def moon_bind_path(name: str, repo: Path | None = None) -> Path:
    """Generic resolver: fixtures/open_seed/<name> then legacy moon platform_bpass."""
    root = repo or _REPO
    fname = Path(name).name
    env_key = f"HA_BIND_{fname.upper().replace('.', '_').replace('-', '_')}"
    env = (os.environ.get(env_key) or "").strip()
    if env:
        return Path(env)
    open_seed = root / "fixtures" / "open_seed" / fname
    if open_seed.is_file():
        return open_seed
    return root / "results" / "platform_bpass" / "moon" / fname


def materials_registry_path(repo: Path | None = None) -> Path:
    root = repo or _REPO
    env = (os.environ.get("HA_MATERIALS_REGISTRY") or "").strip()
    if env:
        return Path(env)
    open_seed = root / "fixtures" / "open_seed" / "ROBOT_MATERIALS_REGISTRY_v1.json"
    if open_seed.is_file():
        return open_seed
    return moon_bind_path("ROBOT_MATERIALS_REGISTRY_v1.json", root)


def dust_ingress_bind_path(repo: Path | None = None) -> Path:
    root = repo or _REPO
    env = (os.environ.get("HA_DUST_INGRESS_BIND") or "").strip()
    if env:
        return Path(env)
    return moon_bind_path("DUST_INGRESS_BIND_v1.json", root)


def kls1_bevameter_bind_path(repo: Path | None = None) -> Path:
    root = repo or _REPO
    env = (os.environ.get("HA_KLS1_BEVAMETER_BIND") or "").strip()
    if env:
        return Path(env)
    return moon_bind_path("KLS1_BEVAMETER_BIND_v1.json", root)


def radiation_fet_coeff_bind_path(repo: Path | None = None) -> Path:
    root = repo or _REPO
    env = (os.environ.get("HA_RADIATION_FET_COEFF_BIND") or "").strip()
    if env:
        return Path(env)
    return moon_bind_path("RADIATION_FET_COEFF_BIND_v1.json", root)


def albedo_dose_fraction_bind_path(repo: Path | None = None) -> Path:
    root = repo or _REPO
    env = (os.environ.get("HA_ALBEDO_DOSE_BIND") or "").strip()
    if env:
        return Path(env)
    return moon_bind_path("ALBEDO_DOSE_FRACTION_BIND_v1.json", root)


def gap_mr11_adapt_closure_path(repo: Path | None = None) -> Path:
    root = repo or _REPO
    env = (os.environ.get("HA_GAP_MR11_CLOSURE") or "").strip()
    if env:
        return Path(env)
    open_seed = root / "fixtures" / "open_seed" / "GAP_MR_11_ADAPT_CLOSURE_v1.json"
    if open_seed.is_file():
        return open_seed
    return (
        root
        / "data"
        / "dogfood_corpus"
        / "moon-world"
        / "W_MOON_STUDY_V1"
        / "GAP_MR_11_ADAPT_CLOSURE_v1.json"
    )
