"""启动 vision_node，并从安装空间加载视觉参数 YAML。"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory("robot_vision"), "config", "vision.yaml"
    )
    return LaunchDescription([
        DeclareLaunchArgument("active_id", default_value="1"),
        DeclareLaunchArgument("ball_color", default_value="red"),
        Node(
            package="robot_vision",
            executable="vision_node",
            name="vision_node",
            output="screen",
            parameters=[
                config,
                {
                    "active_id": ParameterValue(
                        LaunchConfiguration("active_id"), value_type=int
                    ),
                    "ball_color": LaunchConfiguration("ball_color"),
                },
            ],
        ),
    ])
