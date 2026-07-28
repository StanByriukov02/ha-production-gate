"""T5 thin ros2 bridge smoke — no rclpy required."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_URDF = _ROOT / "fixtures" / "open_registry" / "urdf" / "ros_skidsteer_v1.urdf"
_SOILS = (
    _ROOT / "fixtures" / "open_registry" / "terramech" / "dual_owned_soils_skidsteer_v1.json"
)


@pytest.mark.skipif(not _URDF.is_file(), reason="skidsteer fixture missing")
def test_bridge_from_urdf_path() -> None:
    from production_gate.ros2_dual_bridge_v1 import run_dual_from_robot_description

    doc = run_dual_from_robot_description(
        urdf_path=_URDF,
        soils=_SOILS,
        model_kind="wheeled_base",
        write_receipt=True,
        source_label="pytest_urdf",
    )
    assert doc["schema"] == "ha_dual_ros2_v1"
    assert doc["verdict"] == "HA_DUAL_ROS2_PASS", doc.get("dual_socket")
    assert doc["source"]["mode"] == "urdf_path"
    assert doc["honesty"]["thin_ros2_wrapper"] is True
    assert doc["honesty"]["not_full_gazebo_stack"] is True
    contact = (doc.get("dual_socket") or {}).get("contact") or {}
    src = str(contact.get("source") or "")
    assert src.startswith("urdf") or src.startswith("override"), src


@pytest.mark.skipif(not _URDF.is_file(), reason="skidsteer fixture missing")
def test_bridge_from_robot_description_xml() -> None:
    from production_gate.ros2_dual_bridge_v1 import run_dual_from_robot_description

    xml = _URDF.read_text(encoding="utf-8")
    doc = run_dual_from_robot_description(
        robot_description=xml,
        soils=_SOILS,
        model_kind="wheeled_base",
        write_receipt=False,
        source_label="pytest_robot_description",
    )
    assert doc["verdict"] == "HA_DUAL_ROS2_PASS", doc.get("dual_socket")
    assert doc["source"]["mode"] == "robot_description_xml"
    assert doc["source"]["robot_description_chars"] == len(xml)


def test_materialize_rejects_empty_xml() -> None:
    from production_gate.ros2_dual_bridge_v1 import materialize_robot_description

    with pytest.raises(ValueError, match="empty"):
        materialize_robot_description(robot_description="   ")


def test_ros2_package_layout() -> None:
    pkg = _ROOT / "ros2" / "ha_dual_ros2"
    assert (pkg / "package.xml").is_file()
    assert (pkg / "setup.py").is_file()
    assert (pkg / "ha_dual_ros2" / "cli.py").is_file()
    assert (pkg / "ha_dual_ros2" / "dual_node.py").is_file()
    assert (pkg / "launch" / "dual_urdf.launch.py").is_file()
    assert (pkg / "resource" / "ha_dual_ros2").is_file()
    xml = (pkg / "package.xml").read_text(encoding="utf-8")
    assert "<name>ha_dual_ros2</name>" in xml
    assert "ament_python" in xml


def test_cli_module_entrypoint() -> None:
    from production_gate.ros2_dual_bridge_v1 import main

    assert callable(main)
