# Example 10 — Thin ros2 Dual wrapper (T5)

## Goal

Insert Dual into a ROS2 workspace without a Gazebo stack: pass `robot_description` XML or a URDF path → Safe ALLOW / Hostile REFUSE board.

## Without ROS2 (CI / desk)

```bash
pip install -e ".[smoke]"
ha-ensure-bins
ha-dual-ros2 \
  --urdf fixtures/open_registry/urdf/ros_skidsteer_v1.urdf \
  --kind wheeled_base \
  --soils fixtures/open_registry/terramech/dual_owned_soils_skidsteer_v1.json
```

Or inline `robot_description` (same string ROS would publish):

```bash
ha-dual-ros2 \
  --robot-description-file fixtures/open_registry/urdf/ros_skidsteer_v1.urdf \
  --kind wheeled_base \
  --soils fixtures/open_registry/terramech/dual_owned_soils_skidsteer_v1.json
```

## With ROS2

```bash
# from ha-production-gate repo
cd ros2
colcon build --packages-select ha_dual_ros2
source install/setup.bash

ros2 run ha_dual_ros2 dual_from_description -- \
  --urdf /abs/path/robot.urdf --kind wheeled_base --soils /abs/path/soils.json

# or node params
ros2 launch ha_dual_ros2 dual_urdf.launch.py \
  urdf_path:=/abs/path/robot.urdf \
  soils_path:=/abs/path/soils.json
```

## Expect

```text
verdict: HA_DUAL_ROS2_PASS
dual:    DUAL_SOCKET_PASS
mode:    urdf_path | robot_description_xml
```

Board: `results/runtime/platform_loop/HA_DUAL_ROS2_BOARD_LATEST.md`

## Honesty

thin wrapper · calls Dual socket · contact from URDF extract when complete · **not** MEASURED · **not** full Gazebo · **not** Discourse.

Prev: [09 External Fetch](09_external_fetch_owned_soils.md) · [07 Dual socket](07_dual_socket.md)
