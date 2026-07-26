"""URDF → kinematic chain IR compiler v1 — fixed + actuated tree flatten.

Actuated = revolute | continuous | prismatic (serial path).
TABU: claim full URDF spec · claim mesh collision truth · claim branched FK complete.
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]

PROOF_TIER = "URDF_CHAIN_IR_SLICE"
ORACLE = "URDF_COMPILER_V1"
_ACTUATED = frozenset({"revolute", "continuous", "prismatic"})


def _parse_xyz(text: str | None) -> list[float]:
    if not text:
        return [0.0, 0.0, 0.0]
    return [float(x) for x in text.split()]


def _parse_rpy(text: str | None) -> list[float]:
    return _parse_xyz(text)


def _parse_axis(text: str | None) -> list[float]:
    parts = _parse_xyz(text)
    n = math.sqrt(sum(x * x for x in parts))
    if n <= 1e-12:
        return [0.0, 0.0, 1.0]
    return [x / n for x in parts]


def parse_urdf_tree(urdf_path: Path) -> dict[str, Any]:
    root = ET.parse(urdf_path).getroot()
    joints: list[dict[str, Any]] = []
    for joint in root.findall("joint"):
        jtype = str(joint.get("type") or "fixed")
        name = str(joint.get("name") or "")
        parent = joint.find("parent")
        child = joint.find("child")
        origin = joint.find("origin")
        axis = joint.find("axis")
        limit = joint.find("limit")
        xyz = _parse_xyz(origin.get("xyz") if origin is not None else None)
        rpy = _parse_rpy(origin.get("rpy") if origin is not None else None)
        row: dict[str, Any] = {
            "name": name,
            "type": jtype,
            "parent": parent.get("link") if parent is not None else "",
            "child": child.get("link") if child is not None else "",
            "origin_xyz": xyz,
            "origin_rpy": rpy,
        }
        if jtype in ("revolute", "continuous"):
            row["axis_xyz"] = _parse_axis(axis.get("xyz") if axis is not None else None)
            if jtype == "revolute":
                row["lower"] = float(limit.get("lower", 0)) if limit is not None else -math.pi
                row["upper"] = float(limit.get("upper", 0)) if limit is not None else math.pi
                row["effort_nm"] = float(limit.get("effort", 1.0)) if limit is not None else 1.0
            else:
                # continuous: no hard stops; slice stores ±π placeholders
                row["lower"] = -math.pi
                row["upper"] = math.pi
                row["effort_nm"] = float(limit.get("effort", 1.0)) if limit is not None else 1.0
        elif jtype == "prismatic":
            row["axis_xyz"] = _parse_axis(axis.get("xyz") if axis is not None else None)
            row["lower"] = float(limit.get("lower", 0)) if limit is not None else 0.0
            row["upper"] = float(limit.get("upper", 0)) if limit is not None else 0.5
            row["effort_nm"] = float(limit.get("effort", 1.0)) if limit is not None else 1.0
        joints.append(row)
    return {"robot": root.get("name"), "joints": joints}


def _child_map(joints: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for j in joints:
        out.setdefault(str(j["parent"]), []).append(j)
    return out


def infer_urdf_root_link(tree: dict[str, Any], *, preferred: str = "base_link") -> str:
    """Pick a link that is a parent but never a child (URDF tree root).

    Prefers ``preferred`` when it works; else the root with the longest revolute chain.
    """
    joints = list(tree.get("joints") or [])
    children = {str(j["child"]) for j in joints if j.get("child")}
    parents = {str(j["parent"]) for j in joints if j.get("parent")}
    roots = sorted(parents - children)
    candidates: list[str] = []
    if preferred and preferred not in children:
        candidates.append(preferred)
    for r in roots:
        if r not in candidates:
            candidates.append(r)
    if not candidates:
        raise ValueError("no URDF root link candidates")
    best: str | None = None
    best_dof = -1
    for root in candidates:
        try:
            flat = flatten_revolute_chain(tree, root_link=root)
        except ValueError:
            continue
        dof = int(flat.get("dof") or 0)
        if dof > best_dof:
            best, best_dof = root, dof
    if best is None:
        raise ValueError(f"no actuated chain from candidates {candidates}")
    return best


def _path_to_link(
    joints: list[dict[str, Any]],
    *,
    root_link: str,
    target_link: str,
) -> list[dict[str, Any]] | None:
    by_parent = _child_map(joints)
    queue: list[tuple[str, list[dict[str, Any]]]] = [(root_link, [])]
    seen: set[str] = set()
    while queue:
        link, path = queue.pop(0)
        if link in seen:
            continue
        seen.add(link)
        if link == target_link:
            return path
        for joint in by_parent.get(link, []):
            queue.append((str(joint["child"]), path + [joint]))
    return None


def flatten_revolute_chain(
    tree: dict[str, Any],
    *,
    root_link: str = "base_link",
    ee_link: str | None = None,
) -> dict[str, Any]:
    """Serial flatten of actuated joints (revolute/continuous/prismatic).

    Name kept for callers; continuous + prismatic included (engineer-entry honesty).
    """
    joints = list(tree.get("joints") or [])
    if ee_link:
        if ee_link == root_link:
            raise ValueError(
                f"ee_link must differ from root_link ({root_link}) for serial flatten"
            )
        path = _path_to_link(joints, root_link=root_link, target_link=ee_link)
        if not path:
            raise ValueError(f"no path from {root_link} to {ee_link}")
        active = [j for j in path if j["type"] in _ACTUATED]
        if not active:
            raise ValueError(f"no actuated joints on path to {ee_link}")
        return _chain_from_active(active, root_link=root_link, ee_link=ee_link)

    by_parent = _child_map(joints)
    active: list[dict[str, Any]] = []
    link = root_link
    visited: set[str] = set()
    while link not in visited:
        visited.add(link)
        children = by_parent.get(link, [])
        if not children:
            break
        actuated = [c for c in children if c["type"] in _ACTUATED]
        fixed = [c for c in children if c["type"] == "fixed"]
        pick = actuated[0] if actuated else (fixed[0] if fixed else children[0])
        if pick["type"] in _ACTUATED:
            active.append(pick)
        link = str(pick["child"])
    if not active:
        raise ValueError(f"no actuated chain from {root_link}")
    return _chain_from_active(active, root_link=root_link, ee_link=link)


def _chain_from_active(
    active: list[dict[str, Any]],
    *,
    root_link: str,
    ee_link: str,
) -> dict[str, Any]:
    return {
        "root_link": root_link,
        "ee_link": ee_link,
        "dof": len(active),
        "revolute_joints": active,  # historical key; may include continuous/prismatic
        "joint_types": [j["type"] for j in active],
        "se3_joints": [
            {
                "name": j["name"],
                "type": j["type"],
                "origin_xyz": j["origin_xyz"],
                "origin_rpy": j["origin_rpy"],
                "axis_xyz": j["axis_xyz"],
            }
            for j in active
        ],
        "joint_limits_rad": {
            # prismatic limits are meters; named _rad for legacy desk consumers
            "min": [j["lower"] for j in active],
            "max": [j["upper"] for j in active],
        },
        "joint_torque_max_nm": [j["effort_nm"] for j in active],
    }


def compile_urdf_to_chain_spec(
    urdf_rel: str,
    *,
    chain_id: str,
    geometry_class: str = "serial_revolute_se3",
    appendage_role: str = "bench_joint",
    actuator_backend_default: str = "lc2_iron_teaching",
    root_link: str = "base_link",
    ee_link: str | None = None,
    derived: dict[str, Any] | None = None,
) -> dict[str, Any]:
    urdf_path = Path(urdf_rel)
    if not urdf_path.is_file():
        urdf_path = _REPO / urdf_rel.replace("\\", "/")
    tree = parse_urdf_tree(urdf_path)
    used_root = root_link
    try:
        flat = flatten_revolute_chain(tree, root_link=root_link, ee_link=ee_link)
    except ValueError:
        if ee_link is not None:
            raise
        used_root = infer_urdf_root_link(tree, preferred=root_link)
        flat = flatten_revolute_chain(tree, root_link=used_root, ee_link=ee_link)
    spec: dict[str, Any] = {
        "chain_id": chain_id,
        "geometry_class": geometry_class,
        "dof": flat["dof"],
        "ee_frame": flat["ee_link"],
        "appendage_role": appendage_role,
        "actuator_backend_default": actuator_backend_default,
        "source": urdf_rel,
        "root_link": used_root,
        "se3_joints": flat["se3_joints"],
        "joint_limits_rad": flat["joint_limits_rad"],
        "joint_torque_max_nm": flat["joint_torque_max_nm"],
        "proof_tier": PROOF_TIER,
        "oracle": ORACLE,
    }
    if derived:
        spec.update(derived)
    return spec


def validate_urdf_compiler_falsifiers() -> dict[str, Any]:
    urdf = "fixtures/cad/lc2_bench_1dof_v1.urdf"
    tree = parse_urdf_tree(_REPO / urdf)
    flat = flatten_revolute_chain(tree, ee_link="hip_output_link")
    compiled = compile_urdf_to_chain_spec(
        urdf,
        chain_id="lc2_bench_hip_1dof_v1",
        ee_link="hip_output_link",
    )
    revolute_count = sum(1 for j in tree["joints"] if j["type"] == "revolute")
    checks = {
        "F_urdf_revolute_count": revolute_count == 1,
        "F_flat_dof1": flat["dof"] == 1,
        "F_hip_joint_named": flat["revolute_joints"][0]["name"] == "hip_joint",
        "F_axis_y": abs(flat["se3_joints"][0]["axis_xyz"][1] - 1.0) < 1e-6,
        "F_compile_chain_id": compiled["chain_id"] == "lc2_bench_hip_1dof_v1",
    }
    fail = [k for k, v in checks.items() if not v]
    return {"checks": checks, "fail": fail, "pass": not fail, "compiled": compiled}


def run_urdf_chain_ir_smoke() -> dict[str, Any]:
    fals = validate_urdf_compiler_falsifiers()
    return {
        "verdict": "URDF_CHAIN_IR_SLICE_PASS" if fals["pass"] else "URDF_CHAIN_IR_SLICE_FAIL",
        "falsifiers": fals,
    }
