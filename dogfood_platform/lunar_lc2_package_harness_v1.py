"""LC-2 polar package — L1 harness (stack + workload bind) · not thermal solver."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Literal

from dogfood_platform.lunar_materials_l1_v1 import MATERIALS_L1, material_snapshot
from dogfood_platform.lunar_site_burial_v1 import burial_column, burial_thickness_m

_REPO = Path(__file__).resolve().parents[1]
_LC2_WORKLOAD = _REPO / "results" / "platform_bpass" / "w0_workload_lc2_foc_bound_v1.json"

_FGM_BRANCH = Literal["A", "B"]
_REGOLITH_RHO_BRANCH = Literal["A", "B"]

FGM_SHELL_VARIANTS: dict[str, dict[str, Any]] = {
    "A": {
        "material_id": "fgm_lhs_sintered",
        "model": "LHS-1 SPS 1050C",
        "simulant_class": "LHS-1",
        "l0_cites": ["FGRM-L0-10", "FGRM-L0-09"],
    },
    "B": {
        "material_id": "fgm_eac_sintered",
        "model": "EAC-1A SPS 1075C class",
        "simulant_class": "EAC-1A",
        "l0_cites": ["FGRM-Table5", "FGRM-L0-09"],
    },
}

REGOLITH_RHO_VARIANTS: dict[str, dict[str, Any]] = {
    "A": {
        "material_id": "highland_regolith_loose",
        "model": "highland_surface_15cm",
        "depth_class": "top_15cm",
        "thickness_m": 0.10,
        "l0_cites": ["HEIKEN-L0-03"],
    },
    "B": {
        "material_id": "highland_regolith_compact",
        "model": "highland_depth_60cm",
        "depth_class": "60cm_compact",
        "thickness_m": 0.10,
        "l0_cites": ["HEIKEN-L0-02"],
    },
}

LC2_PACKAGE_HARNESS_V1: dict[str, Any] = {
    "harness_id": "lc2_polar_fgm_harness_v1",
    "oracle": "L1_HARNESS_NOT_SOLVER",
    "die_role": "SAMD21RT class 48 MHz FOC joint MCU",
    "footprint_m2": 1.0e-4,
    "stack_ambient_to_die": [
        {
            "layer_id": "fgm_habitat_shell",
            "material_id": "fgm_lhs_sintered",
            "thickness_m": 0.05,
            "function": "ISRU FGM radiation/thermal shell",
        },
        {
            "layer_id": "metal_substrate",
            "material_id": "ti6al4v_substrate",
            "thickness_m": 0.002,
            "function": "FGM metal tier / spreader",
        },
        {
            "layer_id": "tim",
            "material_id": "tim_silicone_class",
            "thickness_m": 50.0e-6,
            "function": "die attach TIM",
        },
    ],
    "workload_bind": "results/platform_bpass/w0_workload_lc2_foc_bound_v1.json",
    "l0_cites": ["FGRM-L0-09", "LC2-qual-passport"],
    "default_fgm_branch": "A",
    "default_regolith_rho_branch": "A",
    "outer_regolith_layer_id": "regolith_burial_outer",
}


def harness_for_stack(
    *,
    fgm_branch: _FGM_BRANCH = "A",
    regolith_rho_branch: _REGOLITH_RHO_BRANCH = "A",
    include_outer_regolith: bool = True,
    embed_class: str = "lc2_micro_package",
) -> dict[str, Any]:
    if fgm_branch not in FGM_SHELL_VARIANTS:
        raise KeyError(fgm_branch)
    if regolith_rho_branch not in REGOLITH_RHO_VARIANTS:
        raise KeyError(regolith_rho_branch)
    h = copy.deepcopy(LC2_PACKAGE_HARNESS_V1)
    reg_variant = REGOLITH_RHO_VARIANTS[regolith_rho_branch]
    fgm_variant = FGM_SHELL_VARIANTS[fgm_branch]
    burial = burial_thickness_m(embed_class)  # type: ignore[arg-type]
    outer_layer = {
        "layer_id": str(h["outer_regolith_layer_id"]),
        "material_id": reg_variant["material_id"],
        "thickness_m": float(burial["thickness_m"]),
        "function": "unconsolidated regolith burial outer shell",
        "embed_class": embed_class,
        "site_zone": burial.get("site_zone"),
    }
    stack = list(h["stack_ambient_to_die"])
    stack[0]["material_id"] = fgm_variant["material_id"]
    if include_outer_regolith:
        h["stack_ambient_to_die"] = [outer_layer, *stack]
    else:
        h["stack_ambient_to_die"] = stack
    h["include_outer_regolith"] = include_outer_regolith
    h["fgm_branch"] = fgm_branch
    h["regolith_rho_branch"] = regolith_rho_branch
    h["fgm_shell_variant"] = fgm_variant
    h["regolith_rho_variant"] = reg_variant
    h["site_burial"] = burial
    return h


def harness_for_fgm_branch(fgm_branch: _FGM_BRANCH) -> dict[str, Any]:
    return harness_for_stack(fgm_branch=fgm_branch, regolith_rho_branch="A")


def fgm_shell_variant_dict(fgm_branch: _FGM_BRANCH) -> dict[str, Any]:
    variant = FGM_SHELL_VARIANTS[fgm_branch]
    mat = material_snapshot(str(variant["material_id"]))
    return {
        "fgm_branch": fgm_branch,
        "material_id": mat.material_id,
        "model": variant["model"],
        "simulant_class": variant["simulant_class"],
        "rho_g_cm3": round(mat.rho_kg_m3 / 1000.0, 4),
        "rho_kg_m3": mat.rho_kg_m3,
        "k_w_mk": mat.k_w_mk,
        "l0_cites": list(dict.fromkeys(list(variant.get("l0_cites") or []) + list(mat.l0_cites))),
    }


def regolith_rho_variant_dict(regolith_rho_branch: _REGOLITH_RHO_BRANCH) -> dict[str, Any]:
    from dogfood_platform.lunar_regolith_psd_v1 import effective_k_with_psd

    variant = REGOLITH_RHO_VARIANTS[regolith_rho_branch]
    mat = material_snapshot(str(variant["material_id"]))
    burial = burial_column("lc2_micro_package")
    psd_class = "EAC-1A" if regolith_rho_branch == "B" else "LHS-1"
    k_psd = effective_k_with_psd(str(variant["material_id"]), psd_class=psd_class)  # type: ignore[arg-type]
    return {
        "regolith_rho_branch": regolith_rho_branch,
        "material_id": mat.material_id,
        "model": variant["model"],
        "depth_class": variant["depth_class"],
        "thickness_m": float(burial["thickness_m"]),
        "embed_class": burial.get("embed_class"),
        "areal_density_g_cm2": burial.get("areal_density_g_cm2"),
        "rho_g_cm3": round(mat.rho_kg_m3 / 1000.0, 4),
        "rho_kg_m3": mat.rho_kg_m3,
        "k_w_mk": mat.k_w_mk,
        "k_psd_w_mk": k_psd["k_w_mk"],
        "psd_class": psd_class,
        "phi_eff": k_psd.get("phi_eff"),
        "l0_cites": list(
            dict.fromkeys(
                list(variant.get("l0_cites") or [])
                + list(mat.l0_cites)
                + list(burial.get("l0_cites") or [])
                + list(k_psd.get("l0_cites") or [])
            )
        ),
    }


def load_lc2_workload_bind() -> dict[str, Any]:
    if not _LC2_WORKLOAD.is_file():
        raise FileNotFoundError(_LC2_WORKLOAD)
    return json.loads(_LC2_WORKLOAD.read_text(encoding="utf-8"))


def resolve_stack_layers(harness: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    h = harness or LC2_PACKAGE_HARNESS_V1
    out: list[dict[str, Any]] = []
    for layer in h.get("stack_ambient_to_die") or []:
        mat_id = str(layer["material_id"])
        mat = MATERIALS_L1[mat_id]
        out.append(
            {
                **layer,
                "rho_kg_m3": float(mat["rho_kg_m3"]),
                "k_w_mk": float(mat["k_w_mk"]),
                "l0_cites": list(mat.get("l0_cites") or []),
            }
        )
    return out


def harness_receipt(
    *,
    fgm_branch: _FGM_BRANCH = "A",
    regolith_rho_branch: _REGOLITH_RHO_BRANCH = "A",
) -> dict[str, Any]:
    bind = load_lc2_workload_bind()
    harness = harness_for_stack(fgm_branch=fgm_branch, regolith_rho_branch=regolith_rho_branch)
    return {
        "harness_id": harness["harness_id"],
        "oracle": harness["oracle"],
        "die_role": harness["die_role"],
        "fgm_branch": fgm_branch,
        "regolith_rho_branch": regolith_rho_branch,
        "fgm_shell_variant": harness["fgm_shell_variant"],
        "regolith_rho_variant": harness["regolith_rho_variant"],
        "f_clock_hz": bind.get("f_clock_hz"),
        "guardband_delta_vth_mv": bind.get("guardband_delta_vth_mv"),
        "stack_layers": resolve_stack_layers(harness),
        "workload_id": bind.get("workload_id"),
    }
