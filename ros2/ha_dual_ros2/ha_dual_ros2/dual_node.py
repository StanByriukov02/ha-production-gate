"""Optional rclpy node — params → Dual. Degrades loudly if ROS2 not installed."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _ensure_repo_on_path() -> None:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    if (repo / "production_gate").is_dir():
        root = str(repo)
        if root not in sys.path:
            sys.path.insert(0, root)


def main(argv: list[str] | None = None) -> int:
    _ensure_repo_on_path()
    try:
        import rclpy
        from rclpy.node import Node
    except ImportError:
        print(
            "HA_DUAL_ROS2_NODE: rclpy not installed — use `ha-dual-ros2 --urdf …` "
            "or `ros2 run ha_dual_ros2 dual_from_description` after sourcing ROS2.",
            file=sys.stderr,
        )
        return 2

    from production_gate.ros2_dual_bridge_v1 import run_dual_from_robot_description

    class DualFromDescriptionNode(Node):
        def __init__(self) -> None:
            super().__init__("ha_dual_ros2")
            self.declare_parameter("urdf_path", "")
            self.declare_parameter("robot_description", "")
            self.declare_parameter("soils_path", "")
            self.declare_parameter("root_link", "base_link")
            self.declare_parameter("ee_link", "")
            self.declare_parameter("model_kind", "wheeled_base")
            self.declare_parameter("run_once", True)

            urdf_path = str(self.get_parameter("urdf_path").value or "").strip()
            robot_description = str(
                self.get_parameter("robot_description").value or ""
            ).strip()
            # Prefer explicit param; else try standard /robot_description on this node
            if not robot_description and self.has_parameter("robot_description"):
                pass
            if not urdf_path and not robot_description:
                # Common pattern: robot_state_publisher puts XML on /robot_description
                # as a parameter on another node — operator can remap via launch.
                self.get_logger().error(
                    "Set urdf_path or robot_description (URDF XML). "
                    "Example: ros2 run ha_dual_ros2 dual_node --ros-args "
                    "-p urdf_path:=/path/robot.urdf"
                )
                raise SystemExit(2)

            soils = str(self.get_parameter("soils_path").value or "").strip() or None
            ee = str(self.get_parameter("ee_link").value or "").strip() or None
            doc = run_dual_from_robot_description(
                urdf_path=urdf_path or None,
                robot_description=robot_description or None,
                soils=soils,
                root_link=str(self.get_parameter("root_link").value or "base_link"),
                ee_link=ee,
                model_kind=str(self.get_parameter("model_kind").value or "wheeled_base"),
                source_label="ha_dual_ros2_node",
            )
            self.get_logger().info(
                f"verdict={doc.get('verdict')} dual={((doc.get('dual_socket') or {}).get('verdict'))}"
            )
            self.get_logger().info(json.dumps({"verdict": doc.get("verdict")}))
            self._ok = doc.get("verdict") == "HA_DUAL_ROS2_PASS"
            if bool(self.get_parameter("run_once").value):
                raise SystemExit(0 if self._ok else 1)

    rclpy.init(args=argv)
    node = DualFromDescriptionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
