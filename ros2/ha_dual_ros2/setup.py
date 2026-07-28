from setuptools import setup

package_name = "ha_dual_ros2"

setup(
    name=package_name,
    version="0.2.1",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/dual_urdf.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Stanislav Byriukov",
    maintainer_email="stanislav@hardwareatom.local",
    description="Thin ROS2 wrapper: robot_description / URDF → HA Dual socket (T5)",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "dual_from_description = ha_dual_ros2.cli:main",
            "dual_node = ha_dual_ros2.dual_node:main",
        ],
    },
)
