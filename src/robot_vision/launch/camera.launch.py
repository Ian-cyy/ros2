"""启动 C70 摄像头节点的 launch 文件。

默认值与比赛单体一致（640x480 @ 30fps，MJPG）。
笔记本摄像头若虚报分辨率，用：
    ros2 launch robot_vision camera.launch.py strict_resolution:=false
换设备就用：
    ros2 launch robot_vision camera.launch.py video_device:=/dev/video1
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        # ---------- 1. 声明命令行参数（默认值都是字符串）----------
        DeclareLaunchArgument("video_device", default_value="/dev/video0"),
        DeclareLaunchArgument("width", default_value="640"),
        DeclareLaunchArgument("height", default_value="480"),
        DeclareLaunchArgument("fps", default_value="30"),
        DeclareLaunchArgument("frame_id", default_value="c70_camera"),
        DeclareLaunchArgument("strict_resolution", default_value="true"),

        # ---------- 2. 启动 camera_node ----------
        # 注意：命令行传进来的是字符串，数字/布尔要用 ParameterValue 指定类型，
        # 否则节点里 declare 成 int/bool 会类型不符报错。
        Node(
            package="robot_vision",
            executable="camera_node",
            name="camera_node",
            output="screen",
            parameters=[{
                "video_device": LaunchConfiguration("video_device"),
                "width": ParameterValue(LaunchConfiguration("width"), value_type=int),
                "height": ParameterValue(LaunchConfiguration("height"), value_type=int),
                "fps": ParameterValue(LaunchConfiguration("fps"), value_type=int),
                "frame_id": LaunchConfiguration("frame_id"),
                "strict_resolution": ParameterValue(
                    LaunchConfiguration("strict_resolution"), value_type=bool
                ),
            }],
        ),
    ])
