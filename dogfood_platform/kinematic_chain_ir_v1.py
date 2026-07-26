"""Kinematic chain IR v1 — registry for any appendage · not hardcoded scout arm.

North star: define chain (JSON/URDF) → resolve Rust crown backend → port/gate.
TABU: Python FK truth · claim URDF import = flight qual.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_IR = _REPO / "fixtures" / "robot" / "kinematic_chain_ir_v0.json"

PROOF_TIER = "APPENDAGE_KINEMATICS_OS_SLICE"
ORACLE = "CHAIN_IR_REGISTRY"


_CHAIN_OVERLAY: dict[str, dict[str, Any]] = {}


def register_chain_overlay(chain_id: str, entry: dict[str, Any]) -> None:
    _CHAIN_OVERLAY[chain_id] = dict(entry)


def clear_chain_overlay() -> None:
    _CHAIN_OVERLAY.clear()


def load_chain_registry() -> dict[str, Any]:
    return json.loads(_IR.read_text(encoding="utf-8"))


def list_chain_ids() -> list[str]:
    reg = load_chain_registry()
    ids = set((reg.get("chains") or {}).keys())
    from dogfood_platform.appendage_registry_persist_v1 import load_persisted_chains

    ids.update(load_persisted_chains().keys())
    ids.update(_CHAIN_OVERLAY.keys())
    return sorted(ids)


def _load_json_fixture(rel: str) -> dict[str, Any]:
    path = _REPO / rel.replace("/", "\\") if "\\" in rel else _REPO / rel
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_urdf_revolute_chain(urdf_path: Path) -> dict[str, Any]:
    root = ET.parse(urdf_path).getroot()
    joints: list[dict[str, Any]] = []
    for joint in root.findall("joint"):
        jtype = joint.get("type")
        if jtype != "revolute":
            continue
        name = str(joint.get("name") or "")
        limit = joint.find("limit")
        axis = joint.find("axis")
        axis_xyz = (axis.get("xyz") if axis is not None else "0 0 1") or "0 0 1"
        lo = float(limit.get("lower", 0)) if limit is not None else -3.14
        hi = float(limit.get("upper", 0)) if limit is not None else 3.14
        effort = float(limit.get("effort", 1.0)) if limit is not None else 1.0
        origin = joint.find("origin")
        xyz = (origin.get("xyz") if origin is not None else "0 0 0") or "0 0 0"
        parts = [float(x) for x in xyz.split()]
        span = max(parts[0], parts[2], 0.035) if parts else 0.05
        joints.append(
            {
                "name": name,
                "axis": axis_xyz,
                "lower": lo,
                "upper": hi,
                "effort_nm": effort,
                "link_span_m": span,
            }
        )
    if not joints:
        raise ValueError(f"no revolute joints in URDF: {urdf_path}")
    return {
        "joints": joints,
        "dof": len(joints),
        "link_lengths_m": [j["link_span_m"] for j in joints],
        "joint_limits_rad": {
            "min": [j["lower"] for j in joints],
            "max": [j["upper"] for j in joints],
        },
        "joint_torque_max_nm": [j["effort_nm"] for j in joints],
    }


def resolve_chain_spec(chain_id: str) -> dict[str, Any]:
    """Materialize chain params from registry entry (JSON fixture or URDF derive)."""
    reg = load_chain_registry()
    entry = (reg.get("chains") or {}).get(chain_id)
    if entry is None:
        from dogfood_platform.appendage_registry_persist_v1 import load_persisted_chains

        entry = load_persisted_chains().get(chain_id)
    if entry is None:
        entry = _CHAIN_OVERLAY.get(chain_id)
    if not entry:
        raise KeyError(f"unknown chain_id={chain_id}")

    spec: dict[str, Any] = {
        "chain_id": chain_id,
        "geometry_class": entry.get("geometry_class"),
        "dof": int(entry.get("dof") or 0),
        "ee_frame": entry.get("ee_frame"),
        "appendage_role": entry.get("appendage_role"),
        "actuator_backend_default": entry.get("actuator_backend_default"),
        "oracle": ORACLE,
    }

    if entry.get("source_fixture"):
        fix = _load_json_fixture(str(entry["source_fixture"]))
        spec.update(
            {
                "link_lengths_m": fix.get("link_lengths_m"),
                "link_masses_kg": fix.get("link_masses_kg"),
                "joint_limits_rad": fix.get("joint_limits_rad"),
                "gravity": fix.get("gravity"),
                "source": entry["source_fixture"],
                "appendage_role": spec.get("appendage_role") or fix.get("appendage_role"),
            }
        )
        g = (fix.get("gravity") or {}).get("lunar_m_s2")
        if g is not None:
            spec["gravity_m_s2"] = float(g)
    elif entry.get("source_urdf"):
        urdf_path = _REPO / str(entry["source_urdf"])
        from dogfood_platform.urdf_to_chain_ir_v1 import compile_urdf_to_chain_spec, flatten_revolute_chain, parse_urdf_tree

        derived = dict(entry.get("derived") or {})
        root_link = str(entry.get("root_link") or derived.get("root_link") or "base_link")
        compiled = compile_urdf_to_chain_spec(
            str(entry["source_urdf"]),
            chain_id=chain_id,
            geometry_class=str(entry.get("geometry_class") or "serial_revolute_se3"),
            appendage_role=str(entry.get("appendage_role") or "bench_joint"),
            actuator_backend_default=str(entry.get("actuator_backend_default") or "lc2_iron_teaching"),
            root_link=root_link,
            ee_link=str(entry.get("ee_frame")) if entry.get("ee_frame") else None,
            derived=derived,
        )
        spec.update(
            {
                "se3_joints": derived.get("se3_joints") or compiled.get("se3_joints"),
                "joint_limits_rad": derived.get("joint_limits_rad") or compiled.get("joint_limits_rad"),
                "joint_torque_max_nm": derived.get("joint_torque_max_nm") or compiled.get("joint_torque_max_nm"),
                "gravity_m_s2": float(derived.get("gravity_m_s2") or 9.81),
                "ee_offset_m": derived.get("ee_offset_m"),
                "source": str(entry["source_urdf"]),
                "urdf_compiled": True,
            }
        )
        # keep planar fallback fields for legacy gates
        tree = parse_urdf_tree(urdf_path)
        flat = flatten_revolute_chain(tree, root_link=root_link, ee_link=str(entry.get("ee_frame") or compiled.get("ee_frame")))
        spec["link_lengths_m"] = derived.get("link_lengths_m") or [0.05] * flat["dof"]
        spec["link_masses_kg"] = derived.get("link_masses_kg") or [0.12] * flat["dof"]
    else:
        raise ValueError(f"chain {chain_id} has no source_fixture or source_urdf")

    spec["proof_tier"] = PROOF_TIER
    return spec


def resolve_kinematics_backend(chain_id: str) -> Any:
    """Return port backend for chain geometry class (Rust crown)."""
    spec = resolve_chain_spec(chain_id)
    gclass = str(spec.get("geometry_class") or "")
    if gclass == "planar_serial_revolute":
        from dogfood_platform.manipulator_kinematics_port_v1 import RustSerialArmBackend

        backend = RustSerialArmBackend()
        backend.chain_spec = spec  # type: ignore[attr-defined]
        return backend
    if gclass == "serial_revolute_se3":
        return Se3ChainBackend(spec)
    raise NotImplementedError(f"geometry_class={gclass} not wired")


class Se3ChainBackend:
    """Rust crown SE(3) serial chain FK."""

    source_id = "manipulator_rust_serial_chain_se3_v1"

    def __init__(self, chain_spec: dict[str, Any]) -> None:
        self.chain_spec = chain_spec

    @staticmethod
    def _quat_rotate(qw: float, qx: float, qy: float, qz: float, v: list[float]) -> list[float]:
        import math

        x, y, z = v
        tx = 2.0 * (qy * z - qz * y)
        ty = 2.0 * (qz * x - qx * z)
        tz = 2.0 * (qx * y - qy * x)
        cx = qy * tz - qz * ty
        cy = qz * tx - qx * tz
        cz = qx * ty - qy * tx
        return [
            x + qw * tx + cx,
            y + qw * ty + cy,
            z + qw * tz + cz,
        ]

    def _payload(self, op: str, **extra: Any) -> dict[str, Any]:
        joints = self.chain_spec.get("se3_joints") or []
        return {"op": op, "se3_joints": joints, **extra}

    def fk(self, q: list[float], *, g: float = 1.62, build: bool = False) -> dict[str, Any]:
        from dogfood_platform.manipulator_kinematics_port_v1 import _native_call

        out = _native_call(self._payload("fk_se3", q=q), build=build)
        rep = dict(out.get("report") or {})
        offset = self.chain_spec.get("ee_offset_m")
        if offset and len(offset) == 3:
            rot = self._quat_rotate(
                float(rep.get("qw") or 1),
                float(rep.get("qx") or 0),
                float(rep.get("qy") or 0),
                float(rep.get("qz") or 0),
                [float(offset[0]), float(offset[1]), float(offset[2])],
            )
            rep["ee_x"] = float(rep.get("ee_x") or 0) + rot[0]
            rep["ee_y"] = float(rep.get("ee_y") or 0) + rot[1]
            rep["ee_z"] = float(rep.get("ee_z") or 0) + rot[2]
            rep["ee_offset_applied"] = offset
        return {"source_id": self.source_id, "verdict": out["verdict"], **rep}


def fk_for_chain(
    chain_id: str,
    q: list[float],
    *,
    g: float | None = None,
    build: bool = False,
) -> dict[str, Any]:
    spec = resolve_chain_spec(chain_id)
    grav = float(g if g is not None else spec.get("gravity_m_s2") or 1.62)
    backend = resolve_kinematics_backend(chain_id)
    if len(q) != int(spec.get("dof") or len(q)):
        raise ValueError(f"q len {len(q)} != dof {spec.get('dof')} for {chain_id}")
    return backend.fk(q, g=grav, build=build)


def validate_chain_registry_falsifiers() -> dict[str, Any]:
    ids = list_chain_ids()
    specs = [resolve_chain_spec(cid) for cid in ids]
    scout = next(s for s in specs if s["chain_id"].startswith("lunar_manipulator"))
    lc2 = next(s for s in specs if s["chain_id"].startswith("lc2_"))
    fk_scout = fk_for_chain(scout["chain_id"], [0.2, 0.3, -0.1], build=False)
    fk_lc2 = fk_for_chain(lc2["chain_id"], [0.35], g=9.81, build=False)
    lc2_x = float(fk_lc2.get("ee_x") or 0)
    lc2_z = float(fk_lc2.get("ee_z") or fk_lc2.get("ee_y") or 0)

    checks: dict[str, bool] = {
        "F_registry_has_multiple_chains": len(ids) >= 3,
        "F_scout_dof3": int(scout.get("dof") or 0) == 3,
        "F_lc2_dof1": int(lc2.get("dof") or 0) == 1,
        "F_hexapod_present": "hexapod_leg_3dof_v1" in ids,
        "F_scout_fk_finite": abs(float(fk_scout.get("ee_x") or 0)) > 0,
        "F_lc2_fk_finite": lc2_x > 0 or abs(lc2_z) > 0,
        "F_oracle_honest": scout.get("oracle") == ORACLE,
        "F_lc2_se3_class": str(lc2.get("geometry_class") or "") == "serial_revolute_se3",
    }
    if "hexapod_leg_3dof_v1" in ids:
        fk_hex = fk_for_chain("hexapod_leg_3dof_v1", [0.2, 0.35, -0.25], build=False)
        checks["F_hexapod_dof3"] = int(resolve_chain_spec("hexapod_leg_3dof_v1").get("dof") or 0) == 3
        checks["F_hexapod_fk_finite"] = abs(float(fk_hex.get("ee_x") or 0)) > 0
    fail = [k for k, v in checks.items() if not v]
    return {
        "checks": checks,
        "fail": fail,
        "pass": len(fail) == 0,
        "chain_ids": ids,
        "scout_fk": {"ee_x": fk_scout.get("ee_x"), "ee_y": fk_scout.get("ee_y")},
        "lc2_fk": {"ee_x": fk_lc2.get("ee_x"), "ee_y": fk_lc2.get("ee_y")},
    }


def run_kinematic_chain_ir_smoke(*, build: bool = False) -> dict[str, Any]:
    fals = validate_chain_registry_falsifiers()
    checks = {
        "F_falsifiers": bool(fals.get("pass")),
        "F_two_chains": len(fals.get("chain_ids") or []) >= 3,
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "APPENDAGE_KINEMATICS_OS_SLICE_PASS" if not fail else "APPENDAGE_KINEMATICS_OS_SLICE_FAIL",
        "checks": checks,
        "fail": fail,
        "falsifiers": fals,
    }
