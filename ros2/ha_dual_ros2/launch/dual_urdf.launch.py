"""Launch Dual against a URDF path (no Gazebo)."""
from __future__ import annotations

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument("urdf_path", description="Absolute path to robot URDF"),
            DeclareLaunchArgument("soils_path", default_value="", description="Owned soils JSON"),
            DeclareLaunchArgument("root_link", default_value="base_link"),
            DeclareLaunchArgument("model_kind", default_value="wheeled_base"),
            Node(
                package="ha_dual_ros2",
                executable="dual_node",
                name="ha_dual_ros2",
                output="screen",
                parameters=[
                    {
                        "urdf_path": LaunchConfiguration("urdf_path"),
                        "soils_path": LaunchConfiguration("soils_path"),
                        "root_link": LaunchConfiguration("root_link"),
                        "model_kind": LaunchConfiguration("model_kind"),
                        "run_once": True,
                    }
                ],
            ),
        ]
    )
