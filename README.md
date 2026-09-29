# ROS2 Workspace

个人 ROS2 工程工作区，后续 ROS2 功能包统一放在 `src/` 下。

## 当前包

- `src/robot_interfaces`：救援机器人自定义 ROS2 接口
- `src/robot_vision`：C70 相机节点、球检测节点和相关学习文档

## 构建

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

`build/`、`install/`、`log/` 是编译生成目录，不进入 Git。新的 ROS2 包使用：

```bash
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_python <package_name>
# 或
ros2 pkg create --build-type ament_cmake <package_name>
```
